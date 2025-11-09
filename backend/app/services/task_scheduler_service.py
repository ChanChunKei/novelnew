"""自动生成任务调度服务 - 智能计算启动时间和生成间隔"""
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.novel import NovelProject
from ..models.auto_generator import AutoGeneratorTask


class TaskSchedulerService:
    """任务调度服务 - 智能管理任务启动时间"""

    # SQLite 最佳并发数
    SQLITE_OPTIMAL_CONCURRENT = 3

    # 生成一章的平均时长（秒）
    AVERAGE_GENERATION_TIME = 120  # 2分钟

    # 最小启动间隔（秒）
    MIN_START_INTERVAL = 300  # 5分钟

    # 预设的生成间隔选项（秒）
    GENERATION_INTERVAL_PRESETS = {
        "30min": 1800,      # 30分钟
        "1hour": 3600,      # 1小时
        "2hour": 7200,      # 2小时
        "3hour": 10800,     # 3小时
        "6hour": 21600,     # 6小时
        "12hour": 43200,    # 12小时
        "24hour": 86400,    # 24小时
    }

    # 预设的启动延迟选项（秒）
    START_DELAY_PRESETS = {
        "now": 0,           # 立即
        "5min": 300,        # 5分钟
        "10min": 600,       # 10分钟
        "30min": 1800,      # 30分钟
        "1hour": 3600,      # 1小时
        "3hour": 10800,     # 3小时
        "6hour": 21600,     # 6小时
        "12hour": 43200,    # 12小时
        "24hour": 86400,    # 24小时
    }

    @classmethod
    def calculate_optimal_intervals(
        cls,
        num_projects: int,
        max_concurrent: int = SQLITE_OPTIMAL_CONCURRENT
    ) -> Dict[str, int]:
        """计算最佳启动间隔和生成间隔

        Args:
            num_projects: 项目数量
            max_concurrent: 最大并发数（SQLite 建议 3）

        Returns:
            {
                "start_interval": 启动间隔（秒），
                "generation_interval": 生成间隔（秒）
            }
        """
        # 1. 计算启动间隔
        # 目标：让任务错开启动，避免同时生成
        # 策略：启动间隔 = 生成时长 * 安全系数
        safety_factor = 2.0  # 安全系数
        start_interval = max(
            cls.MIN_START_INTERVAL,
            int(cls.AVERAGE_GENERATION_TIME * safety_factor)
        )

        # 2. 计算生成间隔
        # 目标：确保同时运行的任务数 <= max_concurrent
        # 策略：根据项目数量动态调整
        if num_projects <= max_concurrent:
            # 少量项目：可以频繁生成（1小时）
            generation_interval = 3600
        elif num_projects <= max_concurrent * 2:
            # 中等数量：适当延长（2小时）
            generation_interval = 7200
        elif num_projects <= max_concurrent * 3:
            # 较多项目：延长间隔（4小时）
            generation_interval = 14400
        else:
            # 大量项目：大幅延长（6小时）
            generation_interval = 21600

        return {
            "start_interval": start_interval,
            "generation_interval": generation_interval,
            "max_concurrent": max_concurrent,
            "num_projects": num_projects,
            "estimated_cycle_time": start_interval * num_projects,  # 完成一轮启动的时间
        }

    @classmethod
    async def create_batch_tasks(
        cls,
        db: AsyncSession,
        user_id: int,
        project_ids: Optional[List[str]] = None,
        generation_interval: Optional[int] = None,
        auto_start: bool = True,
        auto_upload: bool = False,
        fanqie_account: Optional[str] = None,
    ) -> Dict:
        """批量创建任务（智能错开启动时间）

        Args:
            db: 数据库会话
            user_id: 用户ID
            project_ids: 项目ID列表（None表示所有项目）
            generation_interval: 生成间隔（秒），None表示自动计算
            auto_start: 是否自动启动（如果False，任务保持pending状态）
            auto_upload: 是否自动上传到番茄
            fanqie_account: 番茄账号

        Returns:
            {
                "batch_id": "批次ID",
                "tasks_created": 创建的任务数,
                "start_interval": 启动间隔,
                "generation_interval": 生成间隔,
                "schedule": [
                    {
                        "project_id": "项目ID",
                        "task_id": 任务ID,
                        "scheduled_start_time": "启动时间",
                        "delay_seconds": 延迟秒数
                    },
                    ...
                ]
            }
        """
        from .auto_generator_service import AutoGeneratorService

        # 1. 获取项目列表（并预加载章节大纲）
        from sqlalchemy.orm import selectinload
        from ..models.novel import ChapterOutline

        if project_ids:
            # 指定项目
            result = await db.execute(
                select(NovelProject)
                .where(
                    NovelProject.id.in_(project_ids),
                    NovelProject.user_id == user_id
                )
                .options(selectinload(NovelProject.outlines))
            )
        else:
            # 所有项目
            result = await db.execute(
                select(NovelProject)
                .where(NovelProject.user_id == user_id)
                .options(selectinload(NovelProject.outlines))
            )

        all_projects = result.scalars().all()

        if not all_projects:
            raise ValueError("没有找到可用的项目")

        # ✅ 验证：只允许已命名的项目创建任务
        # 过滤掉未命名的灵感项目
        projects = [
            p for p in all_projects
            if p.title and p.title.strip() != '' and
            p.title.strip().lower() not in ['未命名', '新项目', 'untitled', 'new project', '未命名灵感']
        ]

        if not projects:
            raise ValueError("没有找到已命名的项目（所有项目都是未命名灵感，请先完成灵感阶段并命名）")

        if len(projects) < len(all_projects):
            skipped = len(all_projects) - len(projects)
            from logging import getLogger
            logger = getLogger(__name__)
            logger.info(f"跳过 {skipped} 个未命名的灵感项目")

        # 2. 计算最佳间隔
        num_projects = len(projects)
        optimal = cls.calculate_optimal_intervals(num_projects)

        start_interval = optimal["start_interval"]
        if generation_interval is None:
            generation_interval = optimal["generation_interval"]

        # 3. 生成批次ID
        batch_id = str(uuid.uuid4())

        # 4. 创建任务
        tasks_created = []
        current_time = datetime.now(timezone.utc)

        for idx, project in enumerate(projects):
            # 计算启动延迟
            delay_seconds = start_interval * idx
            scheduled_start_time = current_time + timedelta(seconds=delay_seconds)

            # 创建任务
            task = await AutoGeneratorService.create_task(
                db=db,
                project_id=project.id,
                user_id=user_id,
                target_chapters=None,  # 自动从大纲推断
                chapters_per_batch=1,
                interval_seconds=generation_interval,
                auto_select_version=True,
                auto_upload=auto_upload,
                fanqie_account=fanqie_account,
                generation_config={
                    "batch_id": batch_id,
                    "scheduled_start_time": scheduled_start_time.isoformat(),
                    "delay_seconds": delay_seconds,
                }
            )

            # 更新任务的定时启动字段
            task.scheduled_start_time = scheduled_start_time
            task.delay_seconds = delay_seconds
            task.batch_id = batch_id
            await db.commit()
            await db.refresh(task)

            tasks_created.append({
                "project_id": project.id,
                "project_title": project.title,
                "task_id": task.id,
                "scheduled_start_time": scheduled_start_time.isoformat(),
                "delay_seconds": delay_seconds,
                "interval_seconds": generation_interval,
            })

            # 如果auto_start=True，立即启动任务（但任务内部会等待scheduled_start_time）
            if auto_start:
                await AutoGeneratorService.start_task(db, task.id)

        return {
            "batch_id": batch_id,
            "tasks_created": len(tasks_created),
            "start_interval": start_interval,
            "generation_interval": generation_interval,
            "max_concurrent": optimal["max_concurrent"],
            "estimated_cycle_time": optimal["estimated_cycle_time"],
            "schedule": tasks_created,
        }

    @classmethod
    def get_generation_interval_options(cls) -> List[Dict]:
        """获取生成间隔预设选项"""
        return [
            {"value": v, "label": k, "display": cls._format_duration(v)}
            for k, v in cls.GENERATION_INTERVAL_PRESETS.items()
        ]

    @classmethod
    def get_start_delay_options(cls) -> List[Dict]:
        """获取启动延迟预设选项"""
        return [
            {"value": v, "label": k, "display": cls._format_duration(v)}
            for k, v in cls.START_DELAY_PRESETS.items()
        ]

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """格式化时长显示"""
        if seconds == 0:
            return "立即"
        elif seconds < 3600:
            return f"{seconds // 60}分钟"
        elif seconds < 86400:
            return f"{seconds // 3600}小时"
        else:
            return f"{seconds // 86400}天"
