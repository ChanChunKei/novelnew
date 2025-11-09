"""
异步分析处理器

后台定时扫描pending_analysis表，执行增强分析
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Callable
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from ..models.async_task import PendingAnalysis, AnalysisNotification
from ..models.novel import Chapter, NovelBlueprint, BlueprintCharacter
from ..services.super_analysis_service import SuperAnalysisService
from ..services.llm_service import LLMService
from ..utils.metrics import (
    record_success, record_failure,
    track_duration, enhanced_analysis_duration,
    record_token_usage
)

logger = logging.getLogger(__name__)


class AsyncAnalysisProcessor:
    """异步分析处理器

    ✅ 修复：使用session_maker而不是单个session，避免并发冲突
    """

    def __init__(self, session_maker: async_sessionmaker, llm_service_factory: Callable):
        """
        参数:
            session_maker: AsyncSession工厂，用于为每个任务创建独立session
            llm_service_factory: LLMService工厂函数，接受db参数返回LLMService实例
        """
        self.session_maker = session_maker
        self.llm_service_factory = llm_service_factory
        self.is_running = False
        self.max_concurrent = 3  # 最大并发数
        self.poll_interval = 10  # 轮询间隔（秒）
        self.processing_timeout = 600  # 处理超时（秒）
    
    async def start(self):
        """启动处理器"""
        if self.is_running:
            logger.warning("处理器已在运行中")
            return
        
        self.is_running = True
        logger.info("异步分析处理器已启动")
        
        try:
            while self.is_running:
                await self._process_batch()
                await asyncio.sleep(self.poll_interval)
        except Exception as e:
            logger.error(f"处理器异常退出: {e}", exc_info=True)
            self.is_running = False
    
    async def stop(self):
        """停止处理器"""
        self.is_running = False
        logger.info("异步分析处理器已停止")
    
    async def _process_batch(self):
        """处理一批待处理任务

        ✅ 修复：为每个任务创建独立session，避免并发冲突
        """
        try:
            # 1. 查询待处理任务（使用临时session）
            async with self.session_maker() as db:
                pending_tasks = await self._get_pending_tasks(db, limit=self.max_concurrent)

            if not pending_tasks:
                return

            logger.info(f"找到 {len(pending_tasks)} 个待处理任务")

            # 2. 并发处理（每个任务使用独立session）
            tasks = [self._process_single_task(task.id) for task in pending_tasks]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"批量处理失败: {e}", exc_info=True)

    async def _get_pending_tasks(self, db: AsyncSession, limit: int = 10) -> List[PendingAnalysis]:
        """获取待处理任务

        参数:
            db: 数据库session
            limit: 最大返回数量
        """
        # 查询条件：
        # 1. status = 'pending'
        # 2. 或者 status = 'processing' 但超时（started_at < now - timeout）
        timeout_threshold = datetime.now(timezone.utc) - timedelta(seconds=self.processing_timeout)

        stmt = select(PendingAnalysis).where(
            or_(
                PendingAnalysis.status == 'pending',
                and_(
                    PendingAnalysis.status == 'processing',
                    PendingAnalysis.started_at < timeout_threshold
                )
            )
        ).order_by(
            PendingAnalysis.priority.desc(),
            PendingAnalysis.created_at.asc()
        ).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())
    
    async def _process_single_task(self, pending_id: int):
        """处理单个任务

        ✅ 修复：使用独立session，避免并发冲突
        ✅ 修复：预加载关系，避免MissingGreenlet错误

        参数:
            pending_id: 待处理任务ID
        """
        # 为每个任务创建独立的session
        async with self.session_maker() as db:
            try:
                # 1. 加载任务（✅ 预加载chapter、task和selected_version关系）
                from ..models.novel import ChapterVersion
                stmt = (
                    select(PendingAnalysis)
                    .where(PendingAnalysis.id == pending_id)
                    .options(
                        selectinload(PendingAnalysis.chapter).selectinload(Chapter.selected_version),
                        selectinload(PendingAnalysis.task)
                    )
                )
                result = await db.execute(stmt)
                pending = result.scalar_one_or_none()

                if not pending:
                    logger.warning(f"任务 {pending_id} 不存在")
                    return

                # 2. 更新状态为processing
                pending.status = 'processing'
                pending.started_at = datetime.now(timezone.utc)
                await db.commit()

                # 3. 发送开始通知
                await self._send_notification(
                    db=db,
                    pending=pending,
                    notification_type='started',
                    title=f'第 {pending.chapter.chapter_number} 章增强分析已开始',
                    message='正在进行角色追踪、世界观扩展等分析...'
                )

                # 4. 执行增强分析
                with track_duration(enhanced_analysis_duration, mode='enhanced', feature='async_full'):
                    result = await self._execute_analysis(db, pending)

                # 5. 保存结果
                if result:
                    pending.status = 'completed'
                    pending.result = result
                    pending.completed_at = datetime.now(timezone.utc)
                    pending.duration_seconds = pending.elapsed_seconds

                    # 发送完成通知
                    await self._send_notification(
                        db=db,
                        pending=pending,
                        notification_type='completed',
                        title=f'第 {pending.chapter.chapter_number} 章增强分析已完成',
                        message='角色状态、世界观等信息已更新',
                        data=result
                    )

                    await db.commit()
                    record_success('enhanced', 'async_analysis')
                    logger.info(f"任务 {pending_id} 处理成功")

                    # ✅ 6. 记录剧情指标（用于自动分卷）
                    await self._record_story_metrics(db, pending, result)

                    # ✅ 7. 评估是否需要自动分卷
                    await self._evaluate_volume_split(db, pending)
                else:
                    raise Exception("分析结果为空")

            except Exception as e:
                # 处理失败
                pending.status = 'failed'
                pending.error_message = str(e)
                pending.error_type = type(e).__name__
                pending.retry_count += 1
                pending.completed_at = datetime.now(timezone.utc)

                # 发送失败通知
                await self._send_notification(
                    db=db,
                    pending=pending,
                    notification_type='failed',
                    title=f'第 {pending.chapter.chapter_number} 章增强分析失败',
                    message=f'错误: {str(e)}'
                )

                record_failure('enhanced', 'async_analysis', e)
                logger.error(f"任务 {pending_id} 处理失败: {e}", exc_info=True)

                # 如果可以重试，重置为pending
                if pending.can_retry:
                    pending.status = 'pending'
                    logger.info(f"任务 {pending_id} 将重试 ({pending.retry_count}/{pending.max_retries})")

                await db.commit()
    
    async def _execute_analysis(self, db: AsyncSession, pending: PendingAnalysis) -> Optional[dict]:
        """执行增强分析

        参数:
            db: 数据库session
            pending: 待处理任务
        """
        try:
            # 1. 获取章节内容
            chapter = pending.chapter
            if not chapter.selected_version:
                raise Exception("章节没有选中版本")

            content = chapter.selected_version.content

            # 2. 获取蓝图
            stmt = select(NovelBlueprint).where(
                NovelBlueprint.project_id == pending.project_id
            )
            result = await db.execute(stmt)
            blueprint_obj = result.scalar_one_or_none()

            if not blueprint_obj:
                raise Exception("未找到项目蓝图")

            # 3. 构建蓝图字典
            stmt = select(BlueprintCharacter).where(
                BlueprintCharacter.project_id == pending.project_id
            )
            result = await db.execute(stmt)
            characters = result.scalars().all()

            # ✅ 修复：使用正确的字段名
            blueprint = {
                "characters": [
                    {
                        "name": char.name,
                        "identity": char.identity or "",
                        "personality": char.personality or "",
                        "goals": char.goals or "",
                        "abilities": char.abilities or "",
                        "relationship_to_protagonist": char.relationship_to_protagonist or ""
                    }
                    for char in characters
                ],
                "world_setting": blueprint_obj.world_setting or {}
            }

            # 4. 执行超级分析（创建独立的LLM服务）
            llm_service = self.llm_service_factory(db)
            super_analysis = SuperAnalysisService(db, llm_service)
            
            basic_result, enhanced_result = await super_analysis.analyze_chapter(
                chapter_number=chapter.chapter_number,
                chapter_content=content,
                blueprint=blueprint,
                user_id=pending.user_id
            )
            
            # 5. 增强分析结果处理已移除（角色和世界观现在保存在 Volume 快照中）
            # 直接返回分析结果
            return {
                "basic": basic_result,
                "enhanced": enhanced_result if enhanced_result else None
            }
            
        except Exception as e:
            logger.error(f"执行分析失败: {e}", exc_info=True)
            raise
    
    async def _send_notification(
        self,
        db: AsyncSession,
        pending: PendingAnalysis,
        notification_type: str,
        title: str,
        message: str = None,
        data: dict = None
    ):
        """发送通知

        参数:
            db: 数据库session
            pending: 待处理任务
            notification_type: 通知类型
            title: 标题
            message: 消息
            data: 附加数据
        """
        try:
            notification = AnalysisNotification(
                pending_analysis_id=pending.id,
                user_id=pending.user_id,
                chapter_id=pending.chapter_id,
                notification_type=notification_type,
                title=title,
                message=message,
                data=data
            )
            db.add(notification)
            await db.commit()

            logger.info(f"已发送通知: {title}")
        except Exception as e:
            logger.error(f"发送通知失败: {e}", exc_info=True)

    async def _record_story_metrics(
        self,
        db: AsyncSession,
        pending: PendingAnalysis,
        result: dict
    ):
        """
        记录剧情指标（用于自动分卷）

        参数:
            db: 数据库session
            pending: 待处理任务
            result: 分析结果
        """
        try:
            from .story_metrics_service import StoryMetricsService

            chapter = pending.chapter
            enhanced_result = result.get("enhanced", {})
            basic_result = result.get("basic", {})

            # 获取字数
            word_count = len(chapter.selected_version.content) if chapter.selected_version else 0

            # 记录指标
            await StoryMetricsService.record_metrics(
                db=db,
                project_id=pending.project_id,
                chapter_id=pending.chapter_id,
                chapter_number=chapter.chapter_number,
                enhanced_result=enhanced_result,
                summary_result=basic_result,
                word_count=word_count,
                config=pending.generation_config
            )

            logger.info(f"章节 {chapter.chapter_number} 剧情指标已记录")

        except Exception as e:
            logger.error(f"记录剧情指标失败: {e}", exc_info=True)
            # 不阻塞主流程

    async def _evaluate_volume_split(
        self,
        db: AsyncSession,
        pending: PendingAnalysis
    ):
        """
        评估是否需要自动分卷

        参数:
            db: 数据库session
            pending: 待处理任务
        """
        try:
            from .volume_split_service import VolumeSplitService

            # 获取配置
            config = pending.generation_config.get("volume_split") if pending.generation_config else None

            # 如果配置禁用，直接返回
            if config and not config.get("enabled", True):
                return

            # 创建LLM服务
            llm_service = self.llm_service_factory(db)

            # 评估分卷
            split_service = VolumeSplitService(db, llm_service)
            new_volume = await split_service.evaluate_project(
                project_id=pending.project_id,
                task_id=pending.task_id,
                config=config
            )

            if new_volume:
                logger.info(f"已自动创建新卷: {new_volume.title}")

        except Exception as e:
            logger.error(f"评估自动分卷失败: {e}", exc_info=True)
            # 不阻塞主流程

