"""
定时自动生成器调度服务

功能：
- 使用APScheduler实现定时调度（太平洋时间PT）
- 管理书籍生成队列
- 并发控制和自动切换
- 集成现有的AutoGeneratorService和番茄上传
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone as pytz_timezone

from ..models.scheduled_generator import (
    ScheduledGeneratorConfig,
    ScheduledGeneratorQueue,
    ScheduledGeneratorLog,
    ScheduledGeneratorStatus,
    GenerationMode,
    QueueItemStatus,
)
from ..models.auto_generator import AutoGeneratorTask
from .auto_generator_service import AutoGeneratorService
from .novel_service import novelApi

logger = logging.getLogger(__name__)

# 太平洋时区
PACIFIC_TZ = pytz_timezone("America/Los_Angeles")


class ScheduledGeneratorService:
    """定时生成器调度服务"""

    # 全局调度器实例
    _scheduler: Optional[AsyncIOScheduler] = None
    _running_tasks: Dict[int, asyncio.Task] = {}  # config_id -> asyncio.Task
    _task_locks: Dict[int, asyncio.Lock] = {}  # config_id -> Lock

    @classmethod
    def get_scheduler(cls) -> AsyncIOScheduler:
        """获取调度器实例（单例）"""
        if cls._scheduler is None:
            cls._scheduler = AsyncIOScheduler(timezone=PACIFIC_TZ)
            cls._scheduler.start()
            logger.info("APScheduler started with Pacific timezone")
        return cls._scheduler

    @classmethod
    async def create_config(
        cls,
        session: AsyncSession,
        user_id: int,
        name: str,
        trigger_hour: int,
        trigger_minute: int,
        generation_mode: str = "basic",
        auto_upload_fanqie: bool = False,
        upload_interval_seconds: int = 20,
        concurrent_books: int = 1,
        max_duration_per_book: int = 120,
    ) -> ScheduledGeneratorConfig:
        """创建定时配置"""
        config = ScheduledGeneratorConfig(
            user_id=user_id,
            name=name,
            trigger_hour=trigger_hour,
            trigger_minute=trigger_minute,
            generation_mode=generation_mode,
            auto_upload_fanqie=auto_upload_fanqie,
            upload_interval_seconds=upload_interval_seconds,
            concurrent_books=concurrent_books,
            max_duration_per_book=max_duration_per_book,
        )
        session.add(config)
        await session.commit()
        await session.refresh(config)
        logger.info(f"Created scheduled generator config {config.id} for user {user_id}")
        return config

    @classmethod
    async def get_config(cls, session: AsyncSession, config_id: int) -> Optional[ScheduledGeneratorConfig]:
        """获取配置"""
        result = await session.execute(
            select(ScheduledGeneratorConfig).where(ScheduledGeneratorConfig.id == config_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_user_config(cls, session: AsyncSession, user_id: int) -> Optional[ScheduledGeneratorConfig]:
        """获取用户的配置（通常一个用户一个配置）"""
        result = await session.execute(
            select(ScheduledGeneratorConfig)
            .where(ScheduledGeneratorConfig.user_id == user_id)
            .order_by(ScheduledGeneratorConfig.created_at.desc())
        )
        return result.scalar_one_or_none()

    @classmethod
    async def update_config(
        cls,
        session: AsyncSession,
        config_id: int,
        **kwargs
    ) -> ScheduledGeneratorConfig:
        """更新配置"""
        config = await cls.get_config(session, config_id)
        if not config:
            raise ValueError(f"Config {config_id} not found")

        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        await session.commit()
        await session.refresh(config)

        # 如果更新了定时时间且配置已启用，重新注册定时任务
        if config.enabled and ('trigger_hour' in kwargs or 'trigger_minute' in kwargs):
            await cls._register_scheduled_job(session, config)

        logger.info(f"Updated scheduled generator config {config_id}")
        return config

    @classmethod
    async def add_to_queue(
        cls,
        session: AsyncSession,
        config_id: int,
        novel_ids: List[str],
        priority: int = 0,
    ) -> List[ScheduledGeneratorQueue]:
        """添加书籍到队列"""
        config = await cls.get_config(session, config_id)
        if not config:
            raise ValueError(f"Config {config_id} not found")

        # 获取当前最大position
        result = await session.execute(
            select(ScheduledGeneratorQueue)
            .where(ScheduledGeneratorQueue.config_id == config_id)
            .order_by(ScheduledGeneratorQueue.position.desc())
        )
        max_position = 0
        first_item = result.scalar_one_or_none()
        if first_item:
            max_position = first_item.position

        # 创建队列项
        queue_items = []
        for idx, novel_id in enumerate(novel_ids):
            # 检查是否已存在
            existing = await session.execute(
                select(ScheduledGeneratorQueue).where(
                    and_(
                        ScheduledGeneratorQueue.config_id == config_id,
                        ScheduledGeneratorQueue.novel_id == novel_id,
                        ScheduledGeneratorQueue.status.in_([
                            QueueItemStatus.PENDING.value,
                            QueueItemStatus.RUNNING.value
                        ])
                    )
                )
            )
            if existing.scalar_one_or_none():
                logger.warning(f"Novel {novel_id} already in queue for config {config_id}")
                continue

            item = ScheduledGeneratorQueue(
                config_id=config_id,
                novel_id=novel_id,
                priority=priority,
                position=max_position + idx + 1,
            )
            session.add(item)
            queue_items.append(item)

        await session.commit()
        logger.info(f"Added {len(queue_items)} books to queue for config {config_id}")
        return queue_items

    @classmethod
    async def remove_from_queue(cls, session: AsyncSession, queue_item_id: int) -> None:
        """从队列中移除书籍"""
        result = await session.execute(
            select(ScheduledGeneratorQueue).where(ScheduledGeneratorQueue.id == queue_item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError(f"Queue item {queue_item_id} not found")

        if item.status == QueueItemStatus.RUNNING.value:
            raise ValueError("Cannot remove running item from queue")

        await session.delete(item)
        await session.commit()
        logger.info(f"Removed queue item {queue_item_id}")

    @classmethod
    async def get_queue(cls, session: AsyncSession, config_id: int) -> List[ScheduledGeneratorQueue]:
        """获取队列列表"""
        result = await session.execute(
            select(ScheduledGeneratorQueue)
            .where(ScheduledGeneratorQueue.config_id == config_id)
            .order_by(
                ScheduledGeneratorQueue.priority.desc(),
                ScheduledGeneratorQueue.position.asc()
            )
        )
        return list(result.scalars().all())

    @classmethod
    async def start_scheduler(cls, session: AsyncSession, config_id: int) -> None:
        """启动定时任务"""
        config = await cls.get_config(session, config_id)
        if not config:
            raise ValueError(f"Config {config_id} not found")

        config.enabled = True
        config.status = ScheduledGeneratorStatus.IDLE.value
        await session.commit()

        # 注册定时任务
        await cls._register_scheduled_job(session, config)
        logger.info(f"Started scheduler for config {config_id}")

    @classmethod
    async def pause_scheduler(cls, session: AsyncSession, config_id: int) -> None:
        """暂停定时任务"""
        config = await cls.get_config(session, config_id)
        if not config:
            raise ValueError(f"Config {config_id} not found")

        config.status = ScheduledGeneratorStatus.PAUSED.value
        await session.commit()

        # 停止正在运行的任务
        if config_id in cls._running_tasks:
            task = cls._running_tasks[config_id]
            task.cancel()
            logger.info(f"Cancelled running task for config {config_id}")

        logger.info(f"Paused scheduler for config {config_id}")

    @classmethod
    async def resume_scheduler(cls, session: AsyncSession, config_id: int) -> None:
        """恢复定时任务"""
        config = await cls.get_config(session, config_id)
        if not config:
            raise ValueError(f"Config {config_id} not found")

        if config.status != ScheduledGeneratorStatus.PAUSED.value:
            raise ValueError("Scheduler is not paused")

        config.status = ScheduledGeneratorStatus.IDLE.value
        await session.commit()
        logger.info(f"Resumed scheduler for config {config_id}")

    @classmethod
    async def stop_scheduler(cls, session: AsyncSession, config_id: int) -> None:
        """停止定时任务"""
        config = await cls.get_config(session, config_id)
        if not config:
            raise ValueError(f"Config {config_id} not found")

        config.enabled = False
        config.status = ScheduledGeneratorStatus.IDLE.value
        await session.commit()

        # 从调度器中移除任务
        scheduler = cls.get_scheduler()
        job_id = f"scheduled_gen_{config_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f"Removed scheduled job {job_id}")

        # 停止正在运行的任务
        if config_id in cls._running_tasks:
            task = cls._running_tasks[config_id]
            task.cancel()

        logger.info(f"Stopped scheduler for config {config_id}")

    @classmethod
    async def trigger_now(cls, session: AsyncSession, config_id: int) -> None:
        """立即触发一次生成"""
        config = await cls.get_config(session, config_id)
        if not config:
            raise ValueError(f"Config {config_id} not found")

        if config.status == ScheduledGeneratorStatus.RUNNING.value:
            raise ValueError("Scheduler is already running")

        # 异步执行生成任务
        task = asyncio.create_task(cls._execute_generation(config_id, trigger_type="manual"))
        cls._running_tasks[config_id] = task
        logger.info(f"Manually triggered generation for config {config_id}")

    @classmethod
    async def _register_scheduled_job(cls, session: AsyncSession, config: ScheduledGeneratorConfig) -> None:
        """注册定时任务到APScheduler"""
        scheduler = cls.get_scheduler()
        job_id = f"scheduled_gen_{config.id}"

        # 移除旧任务（如果存在）
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        # 创建Cron触发器（太平洋时间）
        trigger = CronTrigger(
            hour=config.trigger_hour,
            minute=config.trigger_minute,
            timezone=PACIFIC_TZ
        )

        # 添加任务
        scheduler.add_job(
            cls._execute_generation,
            trigger=trigger,
            id=job_id,
            args=[config.id, "scheduled"],
            replace_existing=True,
        )

        # 计算下次运行时间
        next_run = trigger.get_next_fire_time(None, datetime.now(PACIFIC_TZ))
        config.next_run_at = next_run
        await session.commit()

        logger.info(
            f"Registered scheduled job {job_id} at {config.trigger_hour:02d}:{config.trigger_minute:02d} PT, "
            f"next run: {next_run}"
        )

    @classmethod
    async def _execute_generation(cls, config_id: int, trigger_type: str = "scheduled") -> None:
        """执行生成任务（核心调度逻辑）"""
        # 导入在这里避免循环依赖
        from ..db.session import get_session_maker

        async_session_maker = get_session_maker()
        async with async_session_maker() as session:
            try:
                config = await cls.get_config(session, config_id)
                if not config:
                    logger.error(f"Config {config_id} not found")
                    return

                # 检查状态
                if config.status == ScheduledGeneratorStatus.PAUSED.value:
                    logger.info(f"Config {config_id} is paused, skipping execution")
                    return

                if config.status == ScheduledGeneratorStatus.RUNNING.value:
                    logger.warning(f"Config {config_id} is already running, skipping")
                    return

                # 更新状态为运行中
                config.status = ScheduledGeneratorStatus.RUNNING.value
                config.last_run_at = datetime.now(timezone.utc)
                config.total_runs += 1
                await session.commit()

                # 创建执行日志
                log = ScheduledGeneratorLog(
                    config_id=config_id,
                    trigger_type=trigger_type,
                    trigger_time=datetime.now(timezone.utc),
                    status="running",
                )
                session.add(log)
                await session.commit()
                await session.refresh(log)

                logger.info(f"Started scheduled generation for config {config_id}, trigger: {trigger_type}")

                # 执行队列处理
                await cls._process_queue(session, config, log)

                # 更新日志状态
                log.status = "success"
                log.completed_at = datetime.now(timezone.utc)
                await session.commit()

            except Exception as e:
                logger.exception(f"Error executing scheduled generation for config {config_id}: {e}")
                # 更新日志错误
                if 'log' in locals():
                    log.status = "failed"
                    log.error_message = str(e)
                    log.completed_at = datetime.now(timezone.utc)
                    await session.commit()

            finally:
                # 恢复状态为空闲
                if 'config' in locals():
                    config.status = ScheduledGeneratorStatus.IDLE.value
                    await session.commit()

                # 移除运行中的任务记录
                if config_id in cls._running_tasks:
                    del cls._running_tasks[config_id]

    @classmethod
    async def _process_queue(
        cls,
        session: AsyncSession,
        config: ScheduledGeneratorConfig,
        log: ScheduledGeneratorLog
    ) -> None:
        """处理队列（并发控制+自动切换）"""
        concurrent_books = config.concurrent_books
        max_duration_minutes = config.max_duration_per_book

        while True:
            # 检查是否暂停
            await session.refresh(config)
            if config.status == ScheduledGeneratorStatus.PAUSED.value:
                logger.info(f"Config {config.id} paused, stopping queue processing")
                break

            # 获取待处理的队列项
            result = await session.execute(
                select(ScheduledGeneratorQueue)
                .where(
                    and_(
                        ScheduledGeneratorQueue.config_id == config.id,
                        ScheduledGeneratorQueue.status == QueueItemStatus.PENDING.value
                    )
                )
                .order_by(
                    ScheduledGeneratorQueue.priority.desc(),
                    ScheduledGeneratorQueue.position.asc()
                )
                .limit(concurrent_books)
            )
            pending_items = list(result.scalars().all())

            if not pending_items:
                logger.info(f"No more pending items in queue for config {config.id}")
                break

            # 并发处理多本书
            tasks = []
            for item in pending_items:
                task = asyncio.create_task(
                    cls._generate_single_book(session, config, item, log, max_duration_minutes)
                )
                tasks.append(task)

            # 等待所有任务完成
            await asyncio.gather(*tasks, return_exceptions=True)

    @classmethod
    async def _generate_single_book(
        cls,
        session: AsyncSession,
        config: ScheduledGeneratorConfig,
        queue_item: ScheduledGeneratorQueue,
        log: ScheduledGeneratorLog,
        max_duration_minutes: int
    ) -> None:
        """生成单本书"""
        try:
            # 更新队列项状态
            queue_item.status = QueueItemStatus.RUNNING.value
            queue_item.started_at = datetime.now(timezone.utc)
            await session.commit()

            logger.info(f"Starting generation for novel {queue_item.novel_id}")

            # 调用现有的AutoGeneratorService启动任务
            auto_task = await AutoGeneratorService.create_task(
                db=session,
                project_id=queue_item.novel_id,
                enable_enhanced_mode=(config.generation_mode == GenerationMode.ENHANCED.value),
                auto_upload=False,  # 先不自动上传，生成完再手动上传
            )

            queue_item.auto_generator_task_id = auto_task.id
            await session.commit()

            # 启动自动生成器
            await AutoGeneratorService.start_task(session, auto_task.id)

            # 监控任务进度，带超时控制
            start_time = datetime.now(timezone.utc)
            timeout_seconds = max_duration_minutes * 60

            while True:
                await asyncio.sleep(10)  # 每10秒检查一次

                # 刷新任务状态
                await session.refresh(auto_task)

                # 检查是否完成
                if auto_task.status in ["completed", "failed", "cancelled"]:
                    logger.info(f"AutoGenerator task {auto_task.id} finished with status: {auto_task.status}")
                    break

                # 检查是否超时
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed > timeout_seconds:
                    logger.warning(f"Task {auto_task.id} timed out after {max_duration_minutes} minutes")
                    # 暂停任务
                    await AutoGeneratorService.pause_task(session, auto_task.id)
                    break

                # 检查配置是否被暂停
                await session.refresh(config)
                if config.status == ScheduledGeneratorStatus.PAUSED.value:
                    logger.info(f"Config {config.id} paused, stopping task {auto_task.id}")
                    await AutoGeneratorService.pause_task(session, auto_task.id)
                    break

            # 更新队列项统计
            queue_item.chapters_generated = auto_task.current_chapter
            queue_item.chapters_target = auto_task.target_chapters
            queue_item.completed_at = datetime.now(timezone.utc)
            queue_item.duration_seconds = int((queue_item.completed_at - queue_item.started_at).total_seconds())

            if auto_task.status == "completed":
                queue_item.status = QueueItemStatus.COMPLETED.value
                log.books_success += 1

                # 如果配置了自动上传番茄
                if config.auto_upload_fanqie:
                    await cls._upload_to_fanqie(session, queue_item, config)

            elif auto_task.status == "failed":
                queue_item.status = QueueItemStatus.FAILED.value
                queue_item.error_message = "AutoGenerator task failed"
                log.books_failed += 1

            else:
                queue_item.status = QueueItemStatus.SKIPPED.value
                log.books_skipped += 1

            log.books_processed += 1
            log.total_chapters += queue_item.chapters_generated
            log.total_duration_seconds += queue_item.duration_seconds

            await session.commit()

        except Exception as e:
            logger.exception(f"Error generating book {queue_item.novel_id}: {e}")
            queue_item.status = QueueItemStatus.FAILED.value
            queue_item.error_message = str(e)
            queue_item.completed_at = datetime.now(timezone.utc)
            log.books_failed += 1
            log.books_processed += 1
            await session.commit()

    @classmethod
    async def _upload_to_fanqie(
        cls,
        session: AsyncSession,
        queue_item: ScheduledGeneratorQueue,
        config: ScheduledGeneratorConfig
    ) -> None:
        """上传到番茄小说"""
        try:
            logger.info(f"Uploading novel {queue_item.novel_id} to Fanqie")

            # 调用现有的番茄上传功能
            result = await novelApi.uploadToFanqie(
                projectId=queue_item.novel_id,
                headless=True,
                uploadInterval=config.upload_interval_seconds
            )

            queue_item.uploaded_to_fanqie = True
            queue_item.upload_result = json.dumps(result, ensure_ascii=False)
            await session.commit()

            logger.info(f"Successfully uploaded novel {queue_item.novel_id} to Fanqie")

        except Exception as e:
            logger.exception(f"Error uploading to Fanqie: {e}")
            queue_item.upload_result = json.dumps({"error": str(e)}, ensure_ascii=False)
            await session.commit()

    @classmethod
    async def get_status(cls, session: AsyncSession, config_id: int) -> Dict[str, Any]:
        """获取当前状态"""
        config = await cls.get_config(session, config_id)
        if not config:
            raise ValueError(f"Config {config_id} not found")

        # 获取队列统计
        result = await session.execute(
            select(ScheduledGeneratorQueue)
            .where(ScheduledGeneratorQueue.config_id == config_id)
        )
        queue_items = list(result.scalars().all())

        pending_count = sum(1 for item in queue_items if item.status == QueueItemStatus.PENDING.value)
        running_count = sum(1 for item in queue_items if item.status == QueueItemStatus.RUNNING.value)
        completed_count = sum(1 for item in queue_items if item.status == QueueItemStatus.COMPLETED.value)
        failed_count = sum(1 for item in queue_items if item.status == QueueItemStatus.FAILED.value)

        # 当前运行的书籍
        running_items = [item for item in queue_items if item.status == QueueItemStatus.RUNNING.value]

        return {
            "config_id": config.id,
            "status": config.status,
            "enabled": config.enabled,
            "next_run_at": config.next_run_at.isoformat() if config.next_run_at else None,
            "last_run_at": config.last_run_at.isoformat() if config.last_run_at else None,
            "queue_stats": {
                "pending": pending_count,
                "running": running_count,
                "completed": completed_count,
                "failed": failed_count,
                "total": len(queue_items),
            },
            "currently_running": [
                {
                    "novel_id": item.novel_id,
                    "started_at": item.started_at.isoformat() if item.started_at else None,
                    "chapters_generated": item.chapters_generated,
                    "chapters_target": item.chapters_target,
                }
                for item in running_items
            ],
            "total_stats": {
                "total_runs": config.total_runs,
                "total_books_processed": config.total_books_processed,
                "total_books_success": config.total_books_success,
                "total_books_failed": config.total_books_failed,
            },
        }
