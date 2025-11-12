"""自动生成器服务 - 完整实现版本

新增优化：
- ✅ Prometheus监控指标
- ✅ 角色匹配相似度追踪
- ✅ 章节生成耗时统计
- ✅ SQLite 并发锁重试机制
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.auto_generator import AutoGeneratorLog, AutoGeneratorTask
from ..models.novel import Chapter, ChapterOutline, NovelProject as Project, Volume
from ..schemas.novel import GenerateChapterRequest, BugFixMode
from .novel_service import NovelService
from .llm_service import LLMService
from .prompt_service import PromptService
from ..utils.metrics import (
    track_duration, chapter_generation_duration,
    chapter_generation_total
)
from ..utils.json_utils import remove_think_tags, unwrap_markdown_json
from ..db.session import retry_on_db_lock
import re

logger = logging.getLogger(__name__)


def strip_markdown_formatting(text: str) -> str:
    """
    移除文本中的Markdown格式标记，保留纯文本内容

    处理的标记：
    - 标题：## 、### 等
    - 粗体：**文本** 或 __文本__
    - 斜体：*文本* 或 _文本_
    - 代码：`文本`
    - 链接：[文本](url)
    - 其他常见标记

    Args:
        text: 包含Markdown标记的文本

    Returns:
        清理后的纯文本
    """
    if not text:
        return text

    # 移除标题标记（##、###等），保留文本
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # 移除粗体标记 **text** 或 __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)

    # 移除斜体标记 *text* 或 _text_（要在粗体之后处理）
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)

    # 移除行内代码标记 `code`
    text = re.sub(r'`(.+?)`', r'\1', text)

    # 移除链接，保留文本 [text](url) -> text
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)

    # 移除图片 ![alt](url) -> alt
    text = re.sub(r'!\[(.+?)\]\(.+?\)', r'\1', text)

    # 移除引用标记 >
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

    # 移除列表标记 - 或 * 或 数字.
    text = re.sub(r'^[\*\-\+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)

    return text


class AutoGeneratorService:
    """
    自动生成器服务

    支持双模式切换:
    - ORIGINAL: 原始模式(保留原有Bug)
    - FIXED: 修复模式(已修复Bug #1, #3, #4, #7)

    通过 generation_config["bug_fix_mode"] 控制
    """

    # 存储运行中的任务
    _running_tasks: dict[int, asyncio.Task] = {}
    # ✅ 修复：添加锁保护，避免并发修改字典时的竞态条件
    _tasks_lock = asyncio.Lock()
    # ✅ 极端并发优化：限制同时创建任务的数量（避免数据库锁死）
    _create_task_semaphore = asyncio.Semaphore(5)  # 最多5个任务同时创建

    @classmethod
    def _get_bug_fix_mode(cls, task: AutoGeneratorTask) -> BugFixMode:
        """获取Bug修复模式"""
        if not task.generation_config:
            return BugFixMode.FIXED  # 默认使用修复模式

        mode = task.generation_config.get("bug_fix_mode", "fixed")
        return BugFixMode.FIXED if mode == "fixed" else BugFixMode.ORIGINAL

    @classmethod
    @retry_on_db_lock(max_retries=10, initial_delay=0.2)
    async def create_task(
        cls,
        db: AsyncSession,
        project_id: str,
        user_id: int,
        target_chapters: Optional[int] = None,
        chapters_per_batch: int = 1,
        interval_seconds: int = 60,
        auto_select_version: bool = True,
        auto_upload: bool = False,
        fanqie_account: Optional[str] = None,
        generation_config: Optional[dict] = None,
    ) -> AutoGeneratorTask:
        """创建自动生成任务（带数据库锁重试 + 并发限流）"""

        # ✅ 极端并发优化：使用信号量限制同时创建任务的数量
        async with cls._create_task_semaphore:
            logger.info(f"Creating task for project {project_id}, semaphore acquired")

            # ✅ 修复：检查项目是否存在并验证所有权（防止水平越权）
            result = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {project_id} not found")

            # ✅ 修复：验证项目所有权，防止用户操作他人项目
            if project.user_id != user_id:
                raise ValueError(f"Unauthorized: Project {project_id} does not belong to user {user_id}")

            # 检查是否已有运行中的任务
            # ✅ 修复：使用 all() 避免多条记录导致的"Multiple rows"错误
            result = await db.execute(
                select(AutoGeneratorTask).where(
                    AutoGeneratorTask.project_id == project_id,
                    AutoGeneratorTask.status.in_(["pending", "running"])
                )
            )
            existing_tasks = result.scalars().all()
            if existing_tasks:
                # 如果有多个任务，记录警告
                if len(existing_tasks) > 1:
                    logger.warning(f"Project {project_id} has {len(existing_tasks)} running tasks, this should not happen")
                raise ValueError(f"Project {project_id} already has {len(existing_tasks)} running task(s)")

            # ✅ 移除验证：允许未命名的灵感项目使用自动生成器
            # 用户可能在灵感阶段就想开始生成章节内容

            # ✅ 如果 target_chapters 为 None，尝试从章节大纲推断
            if target_chapters is None:
                result = await db.execute(
                    select(ChapterOutline).where(
                        ChapterOutline.project_id == project_id
                    )
                )
                outlines = result.scalars().all()
                if outlines and len(outlines) > 0:
                    target_chapters = len(outlines)
                    logger.info(f"自动推断 target_chapters={target_chapters} (从 {len(outlines)} 个章节大纲)")

            # 创建任务
            task = AutoGeneratorTask(
                project_id=project_id,
                user_id=user_id,
                target_chapters=target_chapters,
                chapters_per_batch=chapters_per_batch,
                interval_seconds=interval_seconds,
                auto_select_version=auto_select_version,
                auto_upload=auto_upload,
                fanqie_account=fanqie_account,
                generation_config=generation_config or {},
                status="pending"
            )

            # ✅ 修复：添加异常处理和回滚
            try:
                db.add(task)
                await db.commit()
                await db.refresh(task)
            except Exception:
                await db.rollback()
                raise

            await cls._log(db, task.id, "info", f"自动生成任务已创建，目标章节数: {target_chapters or '无限'}")

            logger.info(f"Task {task.id} created successfully, semaphore released")
            return task

    @classmethod
    @retry_on_db_lock(max_retries=10, initial_delay=0.2)
    async def start_task(cls, db: AsyncSession, task_id: int) -> AutoGeneratorTask:
        """启动自动生成任务（带数据库锁重试）"""

        result = await db.execute(
            select(AutoGeneratorTask).where(AutoGeneratorTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task.status not in ["pending", "paused"]:
            raise ValueError(f"Task {task_id} cannot be started (status: {task.status})")

        # ✅ 验证：检查项目标题，拒绝未命名的灵感项目
        result = await db.execute(
            select(Project).where(Project.id == task.project_id)
        )
        project = result.scalar_one_or_none()

        if not project:
            task.status = "stopped"
            task.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await cls._log(db, task_id, "error", "任务启动失败：项目不存在，已自动停止任务")
            raise ValueError(f"项目 {task.project_id} 不存在")

        # ✅ 移除验证：允许未命名的灵感项目启动自动生成任务
        # 用户可以在灵感阶段就开始生成内容

        # 更新状态
        await db.execute(
            update(AutoGeneratorTask)
            .where(AutoGeneratorTask.id == task_id)
            .values(
                status="running",
                started_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
        )
        await db.commit()

        await cls._log(db, task_id, "info", "自动生成任务已启动")

        # 启动后台任务
        # ✅ 修复：使用锁保护字典操作
        asyncio_task = asyncio.create_task(cls._run_generator(task_id))
        async with cls._tasks_lock:
            cls._running_tasks[task_id] = asyncio_task

        await db.refresh(task)
        return task

    @classmethod
    @retry_on_db_lock(max_retries=10, initial_delay=0.2)
    async def pause_task(cls, db: AsyncSession, task_id: int) -> AutoGeneratorTask:
        """暂停任务（带数据库锁重试）"""

        result = await db.execute(
            select(AutoGeneratorTask).where(AutoGeneratorTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task.status != "running":
            raise ValueError(f"Task {task_id} is not running")

        await db.execute(
            update(AutoGeneratorTask)
            .where(AutoGeneratorTask.id == task_id)
            .values(status="paused", updated_at=datetime.now(timezone.utc))
        )
        await db.commit()

        await cls._log(db, task_id, "info", "自动生成任务已暂停")

        await db.refresh(task)
        return task

    @classmethod
    @retry_on_db_lock(max_retries=10, initial_delay=0.2)
    async def stop_task(cls, db: AsyncSession, task_id: int) -> AutoGeneratorTask:
        """停止任务（带数据库锁重试）"""

        result = await db.execute(
            select(AutoGeneratorTask).where(AutoGeneratorTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # ✅ 修复：重置所有 "generating" 状态的章节（使用批量UPDATE避免锁冲突）
        try:
            # 使用批量UPDATE一次性更新所有章节，避免循环修改
            result = await db.execute(
                update(Chapter)
                .where(
                    Chapter.project_id == task.project_id,
                    Chapter.status == "generating"
                )
                .values(status="not_generated")
            )
            affected_rows = result.rowcount

            if affected_rows > 0:
                await db.commit()
                logger.info(f"重置了 {affected_rows} 个章节状态: generating -> not_generated")
                await cls._log(db, task_id, "info", f"已重置 {affected_rows} 个正在生成的章节状态")
        except Exception as e:
            logger.error(f"重置章节状态失败: {e}")
            await db.rollback()  # 显式回滚，确保后续操作正常

        await db.execute(
            update(AutoGeneratorTask)
            .where(AutoGeneratorTask.id == task_id)
            .values(
                status="stopped",
                completed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
        )
        await db.commit()

        await cls._log(db, task_id, "info", "自动生成任务已停止")

        # 取消后台任务
        # ✅ 修复：使用 pop() 避免 KeyError，并使用锁保护
        async with cls._tasks_lock:
            task_obj = cls._running_tasks.pop(task_id, None)
            if task_obj:
                task_obj.cancel()

        await db.refresh(task)
        return task

    @classmethod
    @retry_on_db_lock(max_retries=10, initial_delay=0.2)
    async def recover_running_tasks(cls, db: AsyncSession) -> int:
        """恢复所有运行中的后台任务（服务器重启后调用）

        返回恢复的任务数量
        """
        logger.info("🔄 开始恢复运行中的后台任务...")

        # 查询所有状态为 running 的任务
        result = await db.execute(
            select(AutoGeneratorTask).where(
                AutoGeneratorTask.status == "running"
            )
        )
        running_tasks = result.scalars().all()

        if not running_tasks:
            logger.info("✅ 没有需要恢复的任务")
            return 0

        recovered_count = 0
        for task in running_tasks:
            # 检查是否已经在运行
            async with cls._tasks_lock:
                if task.id in cls._running_tasks:
                    logger.info(f"⏭️  任务 {task.id} 已在运行，跳过")
                    continue

            # ✅ 修复 target_chapters=None 的问题
            if task.target_chapters is None:
                result = await db.execute(
                    select(ChapterOutline).where(
                        ChapterOutline.project_id == task.project_id
                    )
                )
                outlines = result.scalars().all()
                if outlines:
                    task.target_chapters = len(outlines)
                    await db.execute(
                        update(AutoGeneratorTask)
                        .where(AutoGeneratorTask.id == task.id)
                        .values(target_chapters=task.target_chapters)
                    )
                    await db.commit()
                    logger.info(f"✅ 任务 {task.id}: 修复 target_chapters={task.target_chapters}")

            # 重新启动后台任务
            try:
                asyncio_task = asyncio.create_task(cls._run_generator(task.id))
                async with cls._tasks_lock:
                    cls._running_tasks[task.id] = asyncio_task

                await cls._log(
                    db,
                    task.id,
                    "info",
                    f"✅ 任务已恢复（重启后自动恢复，target_chapters={task.target_chapters}）"
                )

                recovered_count += 1
                logger.info(f"✅ 任务 {task.id} 已恢复运行")
            except Exception as e:
                logger.error(f"❌ 恢复任务 {task.id} 失败: {e}")
                await cls._log(db, task.id, "error", f"恢复任务失败: {str(e)}")

        logger.info(f"🎉 成功恢复 {recovered_count}/{len(running_tasks)} 个任务")
        return recovered_count

    @classmethod
    async def get_task(cls, db: AsyncSession, task_id: int) -> Optional[AutoGeneratorTask]:
        """获取任务信息"""
        result = await db.execute(
            select(AutoGeneratorTask).where(AutoGeneratorTask.id == task_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_project_tasks(
        cls,
        db: AsyncSession,
        project_id: str,
        user_id: int
    ) -> list[AutoGeneratorTask]:
        """获取项目的所有任务"""
        result = await db.execute(
            select(AutoGeneratorTask)
            .where(
                AutoGeneratorTask.project_id == project_id,
                AutoGeneratorTask.user_id == user_id
            )
            .order_by(AutoGeneratorTask.created_at.desc())
        )
        return list(result.scalars().all())

    @classmethod
    async def get_task_logs(
        cls,
        db: AsyncSession,
        task_id: int,
        limit: int = 100
    ) -> list[AutoGeneratorLog]:
        """获取任务日志"""
        result = await db.execute(
            select(AutoGeneratorLog)
            .where(AutoGeneratorLog.task_id == task_id)
            .order_by(AutoGeneratorLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @classmethod
    async def _run_generator(cls, task_id: int):
        """后台生成任务

        ✅ 修复：添加最大迭代次数和连续错误计数，避免无限循环
        """
        from ..db.session import AsyncSessionLocal

        logger.info(f"[AutoGen] Starting task {task_id}")

        # ✅ 修复：添加安全限制
        MAX_ITERATIONS = 10000  # 最大迭代次数
        MAX_CONSECUTIVE_ERRORS = 5  # 最大连续错误次数
        iteration_count = 0
        consecutive_errors = 0

        try:
            while iteration_count < MAX_ITERATIONS:
                iteration_count += 1

                try:
                    async with AsyncSessionLocal() as db:
                        # 获取任务状态
                        task = await cls.get_task(db, task_id)
                        if not task:
                            logger.error(f"Task {task_id} not found")
                            break

                        # 检查状态
                        if task.status == "stopped":
                            logger.info(f"Task {task_id} stopped")
                            break

                        if task.status == "paused":
                            logger.info(f"Task {task_id} paused, waiting...")
                            await asyncio.sleep(10)
                            continue

                        # ✅ 新增：检查定时启动时间
                        if task.scheduled_start_time:
                            now = datetime.now(timezone.utc)
                            # 确保两个 datetime 都带时区信息
                            scheduled_time = task.scheduled_start_time
                            if scheduled_time.tzinfo is None:
                                # 如果数据库中的时间没有时区信息，假设是 UTC
                                scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)
                            if now < scheduled_time:
                                # 还没到启动时间，等待
                                wait_seconds = (scheduled_time - now).total_seconds()
                                logger.info(f"Task {task_id} scheduled to start at {scheduled_time}, waiting {wait_seconds:.0f} seconds...")
                                await cls._log(
                                    db,
                                    task_id,
                                    "info",
                                    f"定时启动：将在 {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')} 开始生成（还需等待 {int(wait_seconds)} 秒）"
                                )
                                # 等待10秒后重新检查
                                await asyncio.sleep(min(10, wait_seconds))
                                continue
                            else:
                                # 已到启动时间，清除scheduled_start_time，开始正常生成
                                if task.scheduled_start_time:
                                    await cls._log(
                                        db,
                                        task_id,
                                        "info",
                                        f"定时启动时间已到，开始生成章节"
                                    )
                                    task.scheduled_start_time = None
                                    await db.commit()

                        # 检查是否达到目标
                        if task.target_chapters and task.chapters_generated >= task.target_chapters:
                            await db.execute(
                                update(AutoGeneratorTask)
                                .where(AutoGeneratorTask.id == task_id)
                                .values(
                                    status="completed",
                                    completed_at=datetime.now(timezone.utc)
                                )
                            )
                            await db.commit()
                            await cls._log(db, task_id, "success", f"已完成目标章节数: {task.target_chapters}")
                            break

                        # 生成章节
                        try:
                            await cls._generate_next_chapters(db, task)
                            consecutive_errors = 0  # 成功后重置错误计数
                        except Exception as e:
                            logger.error(f"Error generating chapters for task {task_id}: {e}")
                            await cls._handle_error(db, task_id, str(e))
                            # 检查是否因错误次数过多而停止
                            task = await cls.get_task(db, task_id)
                            if task and task.status == "error":
                                break
                            # ✅ 修复：章节生成失败后，跳过本次循环，不生成下一章
                            # 等待间隔后重试当前章节
                            await asyncio.sleep(task.interval_seconds)
                            continue

                        # 等待间隔
                        await asyncio.sleep(task.interval_seconds)

                except asyncio.CancelledError:
                    logger.info(f"Task {task_id} cancelled")
                    break
                except Exception as e:
                    # ✅ 修复：区分临时错误和永久错误
                    consecutive_errors += 1
                    logger.error(f"Unexpected error in task {task_id} (consecutive: {consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}): {e}")

                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.error(f"Task {task_id} 连续错误次数过多，停止任务")
                        break

                    await asyncio.sleep(60)  # 出错后等待1分钟再重试

            # ✅ 修复：检查是否因迭代次数过多而退出
            if iteration_count >= MAX_ITERATIONS:
                logger.warning(f"Task {task_id} 达到最大迭代次数 {MAX_ITERATIONS}，自动停止")
        finally:
            # 确保清理资源
            # ✅ 修复：使用 pop() 和锁保护
            async with cls._tasks_lock:
                cls._running_tasks.pop(task_id, None)

            logger.info(f"Auto-generator for task {task_id} finished")

    @classmethod
    async def _generate_next_chapters(cls, db: AsyncSession, task: AutoGeneratorTask):
        """生成下一批章节"""

        # 获取当前最大章节号（只查询已成功生成的章节，避免跳过失败的章节）
        result = await db.execute(
            select(Chapter.chapter_number)
            .where(
                Chapter.project_id == task.project_id,
                Chapter.selected_version_id.isnot(None)  # 只统计已选择版本的章节
            )
            .order_by(Chapter.chapter_number.desc())
            .limit(1)
        )
        last_chapter = result.scalar_one_or_none()
        next_chapter_number = (last_chapter or 0) + 1

        # 获取大纲
        result = await db.execute(
            select(ChapterOutline)
            .where(
                ChapterOutline.project_id == task.project_id,
                ChapterOutline.chapter_number == next_chapter_number
            )
        )
        outline = result.scalar_one_or_none()

        if not outline:
            await cls._log(
                db,
                task.id,
                "info",
                f"第 {next_chapter_number} 章大纲不存在，自动生成新的大纲（AI 自主决定章节数）"
            )

            # 自动生成大纲（AI 自主决定章节数）
            try:
                await cls._auto_generate_outlines(db, task, next_chapter_number)

                # 重新查询大纲
                result = await db.execute(
                    select(ChapterOutline)
                    .where(
                        ChapterOutline.project_id == task.project_id,
                        ChapterOutline.chapter_number == next_chapter_number
                    )
                )
                outline = result.scalar_one_or_none()

                if not outline:
                    await cls._log(
                        db,
                        task.id,
                        "error",
                        f"自动生成大纲失败，第 {next_chapter_number} 章大纲仍不存在"
                    )
                    raise ValueError(f"自动生成大纲失败")

                await cls._log(
                    db,
                    task.id,
                    "success",
                    f"成功自动生成第 {next_chapter_number}-{next_chapter_number + 9} 章大纲"
                )
            except Exception as e:
                await cls._log(
                    db,
                    task.id,
                    "error",
                    f"自动生成大纲失败: {str(e)}"
                )
                raise

        await cls._log(
            db,
            task.id,
            "info",
            f"开始生成第 {next_chapter_number} 章: {outline.title}"
        )

        # 调用生成服务
        novel_service = NovelService(db)

        # 构建生成请求
        request = GenerateChapterRequest(
            chapter_number=next_chapter_number,
            version_count=task.generation_config.get("version_count", 3),
            writing_notes=task.generation_config.get("writing_notes")
        )

        try:
            # 导入必要的服务和工具
            from .prompt_service import PromptService
            from .llm_service import LLMService
            from ..utils.json_utils import remove_think_tags, unwrap_markdown_json
            from ..repositories.system_config_repository import SystemConfigRepository
            import json
            import os

            prompt_service = PromptService(db)
            llm_service = LLMService(db)

            # ✅ 性能优化：只加载必要的数据，不预加载所有章节
            # 对于大型项目（200+章节），预加载所有章节会导致性能问题
            from sqlalchemy.orm import selectinload, joinedload

            result = await db.execute(
                select(Project)
                .where(Project.id == task.project_id)
                .options(
                    selectinload(Project.outlines),  # 章节大纲（轻量级）
                    selectinload(Project.conversations),  # 对话历史
                    joinedload(Project.blueprint),  # 蓝图信息
                    selectinload(Project.characters),  # 角色列表
                    selectinload(Project.relationships_),  # 人物关系
                    selectinload(Project.volumes)  # 分卷信息
                    # ❌ 不再预加载所有章节和版本，改为按需查询
                )
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {task.project_id} not found")

            # 确保基础关系已加载
            _ = project.outlines
            _ = project.conversations
            _ = project.blueprint
            _ = project.characters
            _ = project.relationships_
            _ = project.volumes

            # 准备章节
            chapter = await novel_service.get_or_create_chapter(task.project_id, next_chapter_number)
            chapter.real_summary = None
            chapter.selected_version_id = None
            chapter.status = "generating"
            await db.commit()

            # ✅ 性能优化：只查询最近N章的完整内容（而不是所有章节）
            # 对于生成新章节，只需要最近几章的上下文
            MAX_CONTEXT_CHAPTERS = 10  # 最多保留最近10章的完整内容

            outlines_map = {item.chapter_number: item for item in project.outlines}
            completed_chapters = []

            # 只查询小于当前章节号的已完成章节，按章节号降序排列，限制查询数量
            result = await db.execute(
                select(Chapter)
                .where(
                    Chapter.project_id == task.project_id,
                    Chapter.chapter_number < next_chapter_number,
                    Chapter.status == "successful"  # 只查询成功生成的章节
                )
                .options(
                    selectinload(Chapter.selected_version)  # 只加载selected_version
                )
                .order_by(Chapter.chapter_number.desc())
                .limit(MAX_CONTEXT_CHAPTERS)  # 限制查询数量
            )
            recent_chapters = list(reversed(result.scalars().all()))  # 反转为正序

            # 批量生成缺失的摘要（减少数据库提交次数）
            chapters_need_summary = []
            for existing in recent_chapters:
                if existing.selected_version is None or not existing.selected_version.content:
                    continue

                if not existing.real_summary:
                    chapters_need_summary.append(existing)

            # 批量生成摘要
            if chapters_need_summary:
                logger.info(f"需要为 {len(chapters_need_summary)} 章生成摘要")
                for existing in chapters_need_summary:
                    summary = await llm_service.get_summary(
                        existing.selected_version.content,
                        temperature=0.15,
                        user_id=task.user_id,
                        timeout=180.0,
                    )
                    existing.real_summary = remove_think_tags(summary)
                # 批量提交所有摘要更新
                await db.commit()
                logger.info(f"已批量生成 {len(chapters_need_summary)} 个章节摘要")

            # 构建completed_chapters列表
            for existing in recent_chapters:
                if existing.selected_version is None or not existing.selected_version.content:
                    continue

                existing_outline = outlines_map.get(existing.chapter_number)
                completed_chapters.append({
                    "chapter_number": existing.chapter_number,
                    "title": existing_outline.title if existing_outline else f"第{existing.chapter_number}章",
                    "summary": existing.real_summary,
                    "content": existing.selected_version.content,
                })

            # 构建蓝图
            project_schema = await novel_service._serialize_project(project)
            blueprint_dict = project_schema.blueprint.model_dump()

            # 清理蓝图
            # ✅ 保留 chapter_outline，让AI知道总章节数和整体规划
            banned_keys = {"chapter_summaries", "chapter_details", "chapter_dialogues", "chapter_events", "conversation_history", "character_timelines"}
            for key in banned_keys:
                blueprint_dict.pop(key, None)

            # ✅ 添加所有分卷的快照数据，并标注当前分卷
            # 获取当前章节所属的分卷
            current_outline = outlines_map.get(next_chapter_number)
            current_volume_id = current_outline.volume_id if current_outline else None

            volumes_snapshot = []
            for vol in sorted(project.volumes, key=lambda v: v.volume_number):
                is_current = (vol.id == current_volume_id)
                vol_data = {
                    "volume_number": vol.volume_number,
                    "title": f"{vol.title}（当前分卷）" if is_current else vol.title,
                    "characters": vol.characters or [],
                    "relationships": vol.relationships or [],
                    "world_setting": vol.world_setting or {}
                }
                volumes_snapshot.append(vol_data)

            # 将分卷快照添加到蓝图中
            blueprint_dict["volumes_snapshot"] = volumes_snapshot

            # 获取写作提示词
            writer_prompt = await prompt_service.get_prompt("writing")
            if not writer_prompt:
                raise ValueError("缺少写作提示词")

            # ✅ 新方案：不使用RAG，改用简单上下文
            # 1. 所有章节的摘要
            # 2. 上两章的完整内容

            # 构建所有章节摘要
            blueprint_text = json.dumps(blueprint_dict, ensure_ascii=False, indent=2)
            all_summaries_lines = [
                f"- 第{item['chapter_number']}章 - {item['title']}: {item['summary']}"
                for item in completed_chapters
            ]
            all_summaries_text = "\n".join(all_summaries_lines) if all_summaries_lines else "暂无已完成章节"

            # 获取上两章的完整内容
            previous_two_chapters = []
            for item in sorted(completed_chapters, key=lambda x: x['chapter_number'], reverse=True):
                previous_two_chapters.append({
                    "number": item['chapter_number'],
                    "title": item['title'],
                    "content": item['content']
                })
                if len(previous_two_chapters) >= 2:
                    break

            # 反转顺序，让最早的章节在前
            previous_two_chapters.reverse()

            # 构建上两章内容文本
            previous_chapters_text = ""
            if previous_two_chapters:
                previous_chapters_parts = []
                for ch in previous_two_chapters:
                    previous_chapters_parts.append(f"### 第{ch['number']}章 - {ch['title']}\n{ch['content']}")
                previous_chapters_text = "\n\n".join(previous_chapters_parts)
            else:
                previous_chapters_text = "暂无前序章节"

            prompt_sections = [
                ("[世界蓝图](JSON)", blueprint_text),
                ("[所有章节摘要]", all_summaries_text),
                ("[前两章完整内容]", previous_chapters_text),
                ("[当前章节目标]", f"标题：{outline.title}\n摘要：{outline.summary}"),
            ]
            prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)

            # 生成版本
            version_count = task.generation_config.get("version_count", 2)
            raw_versions = []

            # ✅ 使用AI路由系统生成章节内容
            from ..services.ai_orchestrator_helper import generate_chapter_content

            for idx in range(version_count):
                # 记录任务日志
                await cls._log(
                    db,
                    task.id,
                    "info",
                    f"正在生成第 {next_chapter_number} 章的第 {idx + 1} 个版本（使用 SiliconFlow DeepSeek-V3）..."
                )

                logger.info(
                    f"开始调用AI功能: CHAPTER_CONTENT_WRITING, 章节: {next_chapter_number}, 版本: {idx + 1}"
                )

                # ✅ 获取生成模式（支持Agent模式）
                generation_mode = task.generation_config.get("generation_mode", "basic")

                # ✅ 读取增强模式自定义温度配置
                enhanced_temp = task.generation_config.get("enhanced_temperature")
                temperature = enhanced_temp if enhanced_temp is not None else 0.9

                response = await generate_chapter_content(
                    db_session=db,
                    system_prompt=writer_prompt,
                    user_prompt=prompt_input,
                    user_id=task.user_id,
                    temperature=temperature,          # ✅ 传递温度配置
                    generation_mode=generation_mode,  # ✅ 传递生成模式
                    project_id=task.project_id,       # ✅ 传递项目ID（Agent需要）
                    chapter_number=next_chapter_number, # ✅ 传递章节号（Agent需要）
                )

                logger.info(
                    f"AI功能调用成功: CHAPTER_CONTENT_WRITING, 章节: {next_chapter_number}, 版本: {idx + 1}"
                )

                cleaned = remove_think_tags(response)
                normalized = unwrap_markdown_json(cleaned)
                try:
                    raw_versions.append(json.loads(normalized))
                except (json.JSONDecodeError, ValueError) as e:
                    logger.debug(f"Failed to parse JSON response, using raw content: {e}")
                    raw_versions.append({"content": normalized})

            # 提取full_content字段
            contents = []
            for idx, variant in enumerate(raw_versions):
                if isinstance(variant, dict):
                    # 优先提取full_content字段
                    if "full_content" in variant and variant["full_content"]:
                        full_content = variant["full_content"]

                        # ✅ 防御性处理：检查full_content是否被错误地嵌套成JSON字符串
                        if isinstance(full_content, str) and full_content.strip().startswith("{"):
                            try:
                                # 尝试解析，如果是JSON字符串，提取真正的内容
                                nested = json.loads(full_content)
                                if isinstance(nested, dict) and "full_content" in nested:
                                    logger.warning(f"第 {next_chapter_number} 章版本 {idx+1}: 检测到嵌套JSON，自动提取")
                                    full_content = nested["full_content"]
                            except json.JSONDecodeError:
                                # 不是JSON，保持原样
                                pass

                        # ✅ 处理双重转义：如果内容包含 \\n、\\t 等转义序列，进行反转义
                        if isinstance(full_content, str) and ("\\n" in full_content or "\\t" in full_content):
                            # 检测是否是错误的双重转义（不是代码块中的转义）
                            # 如果内容以 ## 开头（Markdown标题）且包含 \n，很可能是错误转义
                            if full_content.strip().startswith("#") or full_content.count("\\n") > 5:
                                try:
                                    # 使用 encode().decode('unicode_escape') 进行反转义
                                    # 但要小心处理非ASCII字符
                                    unescaped = full_content.encode().decode('unicode_escape')
                                    logger.warning(f"第 {next_chapter_number} 章版本 {idx+1}: 检测到双重转义，已自动修复")
                                    full_content = unescaped
                                except Exception as e:
                                    logger.error(f"反转义失败: {e}，保持原样")
                                    pass

                        # ✅ 强制清理Markdown标记：无论是否检测到，都进行清理（防止漏检）
                        if isinstance(full_content, str):
                            original_content = full_content
                            full_content = strip_markdown_formatting(full_content)

                            # 如果内容发生了变化，说明清理了Markdown
                            if full_content != original_content:
                                logger.warning(
                                    f"第 {next_chapter_number} 章版本 {idx+1}: 检测到并清理了Markdown标记\n"
                                    f"  原始预览: {original_content[:100]}...\n"
                                    f"  清理后预览: {full_content[:100]}..."
                                )

                        contents.append(full_content)
                        logger.info(f"第 {next_chapter_number} 章版本 {idx+1}: 提取full_content，长度={len(full_content)}")
                    elif "content" in variant and variant["content"]:
                        content = variant["content"]

                        # ✅ 强制清理Markdown标记：无论是否检测到，都进行清理（防止漏检）
                        if isinstance(content, str):
                            original_content = content
                            content = strip_markdown_formatting(content)

                            # 如果内容发生了变化，说明清理了Markdown
                            if content != original_content:
                                logger.warning(
                                    f"第 {next_chapter_number} 章版本 {idx+1}: content字段检测到并清理了Markdown标记\n"
                                    f"  原始预览: {original_content[:100]}...\n"
                                    f"  清理后预览: {content[:100]}..."
                                )

                        contents.append(content)
                        logger.info(f"第 {next_chapter_number} 章版本 {idx+1}: 提取content，长度={len(content)}")
                    else:
                        # 如果没有找到内容字段，使用整个JSON
                        content_str = json.dumps(variant, ensure_ascii=False)
                        contents.append(content_str)
                        logger.warning(f"第 {next_chapter_number} 章版本 {idx+1}: 未找到full_content或content字段，使用完整JSON")
                else:
                    logger.info(f"第 {next_chapter_number} 章版本 {idx+1}: variant不是dict，直接转字符串")
                    contents.append(str(variant))

            # 保存版本
            await novel_service.replace_chapter_versions(chapter, contents, None)

            # 如果启用自动选择，先评估再选择最佳版本
            if task.auto_select_version:
                # 重新查询 chapter 并预加载 versions 和 selected_version 关系
                # 使用 populate_existing=True 强制重新加载，避免读取缓存的旧数据
                result = await db.execute(
                    select(Chapter)
                    .where(
                        Chapter.project_id == task.project_id,
                        Chapter.chapter_number == next_chapter_number
                    )
                    .options(
                        selectinload(Chapter.versions),
                        selectinload(Chapter.selected_version)
                    )
                    .execution_options(populate_existing=True)
                )
                chapter_obj = result.scalar_one_or_none()

                if chapter_obj and chapter_obj.versions:
                    # ✅ 新增：AI评估版本并自动选择最佳版本
                    selected_version_index = 0  # 默认选择第一个版本

                    # 如果有多个版本，进行AI评估
                    if len(chapter_obj.versions) > 1:
                        try:
                            await cls._log(
                                db,
                                task.id,
                                "info",
                                f"正在评估第 {next_chapter_number} 章的 {len(chapter_obj.versions)} 个版本..."
                            )

                            # 调用AI评估功能
                            selected_version_index = await cls._evaluate_and_select_best_version(
                                db=db,
                                task=task,
                                chapter=chapter_obj,
                                blueprint_dict=blueprint_dict,
                                llm_service=llm_service
                            )

                            await cls._log(
                                db,
                                task.id,
                                "success",
                                f"AI评估完成，选择了版本 {selected_version_index + 1}"
                            )
                        except Exception as e:
                            logger.error(f"AI评估失败，降级为选择第一个版本: {e}")
                            await cls._log(
                                db,
                                task.id,
                                "warning",
                                f"AI评估失败，自动选择第一个版本: {str(e)}"
                            )
                            selected_version_index = 0

                    # 选择版本
                    await novel_service.select_chapter_version(chapter_obj, selected_version_index)

                    # ✅ 修复：刷新 chapter_obj 以加载 selected_version 关系
                    await db.refresh(chapter_obj, ["selected_version"])

                    await cls._log(
                        db,
                        task.id,
                        "success",
                        f"第 {next_chapter_number} 章生成完成并已自动选择版本 {selected_version_index + 1}"
                    )

                    # ✅ 双模式架构：根据配置选择生成模式
                    # Bug #4 修复: 处理 generation_config 可能为 None 的情况
                    bug_fix_mode = cls._get_bug_fix_mode(task)

                    if bug_fix_mode == BugFixMode.FIXED:
                        # 修复模式: 安全地获取配置
                        generation_mode = (task.generation_config or {}).get("generation_mode", "basic")
                    else:
                        # 原始模式: 保留原有Bug(可能抛出AttributeError)
                        generation_mode = task.generation_config.get("generation_mode", "basic")

                    if generation_mode == "enhanced":
                        # 增强模式：使用超级分析
                        await cls._process_enhanced_mode(
                            db, task, chapter_obj, next_chapter_number,
                            blueprint_dict, llm_service
                        )
                    else:
                        # 基础模式：只生成摘要（原有逻辑）
                        await cls._process_basic_mode(
                            db, task, chapter_obj, llm_service
                        )

                    # 创意功能分析已移除（角色、世界观现在保存在 Volume 快照中）
                    pass
            else:
                await cls._log(
                    db,
                    task.id,
                    "success",
                    f"第 {next_chapter_number} 章生成完成，等待手动选择版本"
                )

                # 即使未自动选择版本，也触发创意功能分析
                result = await db.execute(
                    select(Chapter)
                    .where(
                        Chapter.project_id == task.project_id,
                        Chapter.chapter_number == next_chapter_number
                    )
                    .options(selectinload(Chapter.versions))
                )
                chapter_obj = result.scalar_one_or_none()
                # 创意功能分析已移除

            # 更新统计
            await db.execute(
                update(AutoGeneratorTask)
                .where(AutoGeneratorTask.id == task.id)
                .values(
                    chapters_generated=task.chapters_generated + 1,
                    last_generation_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
            )
            await db.commit()

            # 如果启用了自动上传，触发上传到番茄小说
            if task.auto_upload and task.fanqie_account:
                await cls._log(
                    db,
                    task.id,
                    "info",
                    f"检测到自动上传已启用，准备上传第 {next_chapter_number} 章到番茄小说"
                )

                try:
                    # 异步触发上传（不阻塞生成流程）
                    asyncio.create_task(
                        cls._auto_upload_chapter(
                            db=db,
                            task=task,
                            chapter_number=next_chapter_number
                        )
                    )
                except Exception as upload_error:
                    logger.error(f"触发自动上传失败: {upload_error}")
                    await cls._log(
                        db,
                        task.id,
                        "warning",
                        f"第 {next_chapter_number} 章自动上传触发失败: {str(upload_error)}"
                    )

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"第 {next_chapter_number} 章生成失败: {str(e)}\n{error_details}")

            # ✅ 修复：重置章节状态，避免卡在 "generating"
            try:
                chapter = await novel_service.get_or_create_chapter(task.project_id, next_chapter_number)
                chapter.status = "not_generated"  # 重置为未生成状态
                await db.commit()
                logger.info(f"已重置第 {next_chapter_number} 章状态为 not_generated")
            except Exception as reset_error:
                logger.error(f"重置章节状态失败: {reset_error}")

            await cls._log(
                db,
                task.id,
                "error",
                f"第 {next_chapter_number} 章生成失败: {str(e)}"
            )
            raise

    @classmethod
    @retry_on_db_lock(max_retries=10, initial_delay=0.2)
    async def _handle_error(cls, db: AsyncSession, task_id: int, error_msg: str):
        """处理错误（带数据库锁重试）"""

        result = await db.execute(
            select(AutoGeneratorTask).where(AutoGeneratorTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return

        error_count = task.error_count + 1

        # 如果错误次数过多，停止任务
        if error_count >= 5:
            await db.execute(
                update(AutoGeneratorTask)
                .where(AutoGeneratorTask.id == task_id)
                .values(
                    status="error",
                    error_count=error_count,
                    last_error=error_msg,
                    completed_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
            )
            await cls._log(db, task_id, "error", f"任务因错误次数过多而停止: {error_msg}")
        else:
            await db.execute(
                update(AutoGeneratorTask)
                .where(AutoGeneratorTask.id == task_id)
                .values(
                    error_count=error_count,
                    last_error=error_msg,
                    updated_at=datetime.now(timezone.utc)
                )
            )

        await db.commit()

    @classmethod
    async def _log(
        cls,
        db: AsyncSession,
        task_id: int,
        log_type: str,
        message: str,
        chapter_number: Optional[int] = None,
        details: Optional[dict] = None
    ):
        """记录日志（不添加装饰器，避免嵌套重试）

        ✅ 修复：捕获所有异常（包括 greenlet_spawn 错误），日志失败不影响主流程
        """
        # 先打印日志（确保至少有日志输出）
        logger.info(f"[Task {task_id}] {log_type.upper()}: {message}")

        # 尝试写入数据库，失败不影响主流程
        try:
            log = AutoGeneratorLog(
                task_id=task_id,
                chapter_number=chapter_number,
                log_type=log_type,
                message=message,
                details=details
            )
            db.add(log)
            await db.commit()
        except Exception as e:
            # 捕获所有异常（包括 greenlet_spawn），日志记录失败不应该中断主流程
            error_type = type(e).__name__
            logger.warning(f"Failed to log for task {task_id} ({error_type}): {str(e)[:100]}")
            try:
                await db.rollback()
            except:
                pass  # 连 rollback 都失败就彻底放弃，不影响主流程

    @classmethod
    async def _evaluate_outline_versions(
        cls,
        db: AsyncSession,
        task: AutoGeneratorTask,
        outline_versions: list,
        blueprint_dict: dict,
        llm_service: LLMService,
        prompt_service: PromptService,
        completed_chapters: list = None,
        previous_two_chapters: list = None,
        start_chapter: int = None,
        volumes_data: list = None
    ) -> int:
        """
        AI评估多个大纲版本，返回最佳版本的索引

        Args:
            db: 数据库会话
            task: 自动生成器任务
            outline_versions: 大纲版本列表，每个元素包含 version_id, data, raw_response
            blueprint_dict: 蓝图信息字典
            llm_service: LLM服务
            prompt_service: 提示词服务
            completed_chapters: 已完成章节摘要列表
            previous_two_chapters: 前两章完整内容
            start_chapter: 新大纲起始章节号
            volumes_data: 所有分卷的快照数据

        Returns:
            最佳版本的索引（0-based）
        """
        try:
            # 1. 获取评估提示词
            evaluator_prompt_content = await prompt_service.get_prompt("outline_evaluation")

            if not evaluator_prompt_content:
                # 降级：使用通用评估提示词
                evaluator_prompt_content = await prompt_service.get_prompt("evaluation")

            if not evaluator_prompt_content:
                logger.warning("缺少大纲评估提示词，默认选择第一个版本")
                await cls._log(db, task.id, "warning", "缺少评估提示词，使用第一个版本")
                return 0

            # 2. 构建评估payload
            versions_to_evaluate = []
            for v in outline_versions:
                version_info = {
                    "version_id": v["version_id"],
                    "volume_title": v["data"].get("volume_title", ""),
                    "chapters": v["data"].get("chapters", []),
                    "characters": v["data"].get("characters", []),
                    "total_chapters": len(v["data"].get("chapters", []))
                }
                versions_to_evaluate.append(version_info)

            # 🔥 传递所有卷的快照数据，并标注即将生成的新卷
            volumes_snapshot = []
            new_volume_number = 1
            if volumes_data and len(volumes_data) > 0:
                new_volume_number = len(volumes_data) + 1
                for vol in volumes_data:
                    vol_snapshot = {
                        "volume_number": vol.get("volume_number"),
                        "title": vol.get("title", ""),
                        "characters": vol.get("characters", []),
                        "relationships": vol.get("relationships", []),
                        "world_setting": vol.get("world_setting", {}),
                        "is_current": False
                    }
                    volumes_snapshot.append(vol_snapshot)
                logger.info(f"大纲评估：传递 {len(volumes_snapshot)} 个已有卷的快照数据，即将生成第 {new_volume_number} 卷")
                await cls._log(db, task.id, "info", f"传递 {len(volumes_snapshot)} 个已有卷的快照数据，即将生成第 {new_volume_number} 卷")

            evaluator_payload = {
                "novel_blueprint": blueprint_dict,
                "volumes_snapshot": volumes_snapshot,
                "new_volume_number": new_volume_number,
                "completed_chapters": completed_chapters or [],
                "previous_chapters_content": previous_two_chapters or [],
                "generation_context": {
                    "start_chapter": start_chapter,
                    "total_previous_chapters": len(completed_chapters) if completed_chapters else 0
                },
                "content_to_evaluate": {
                    "type": "outline",
                    "versions": versions_to_evaluate
                },
                "evaluation_criteria": [
                    "情节连贯性和吸引力",
                    "章节间节奏把控",
                    "冲突和转折设计",
                    "符合蓝图设定",
                    "章节标题吸引力"
                ]
            }

            await cls._log(db, task.id, "info", "正在调用AI评估大纲版本...")

            # 3. 调用AI评估
            evaluation_response = await llm_service.get_llm_response(
                system_prompt=evaluator_prompt_content,
                conversation_history=[{
                    "role": "user",
                    "content": json.dumps(evaluator_payload, ensure_ascii=False)
                }],
                temperature=0.3,  # 低温度，确保评估客观
                user_id=task.user_id,
                timeout=300.0,
            )

            # 4. 解析评估结果
            evaluation_clean = unwrap_markdown_json(remove_think_tags(evaluation_response))
            evaluation_data = json.loads(evaluation_clean)

            # 5. 提取最佳版本
            best_choice = evaluation_data.get("best_choice")
            if best_choice and isinstance(best_choice, int):
                best_index = best_choice - 1  # 转为0-based
                if 0 <= best_index < len(outline_versions):
                    reason = evaluation_data.get("reason_for_choice", "未提供")
                    logger.info(f"AI评估推荐大纲版本 {best_choice}，原因: {reason}")
                    await cls._log(
                        db,
                        task.id,
                        "info",
                        f"AI评估推荐版本 {best_choice}: {reason[:100]}"
                    )
                    return best_index

            logger.warning("AI评估结果无效，默认选择第一个版本")
            await cls._log(db, task.id, "warning", "评估结果无效，使用第一个版本")
            return 0

        except Exception as e:
            logger.error(f"大纲评估失败: {str(e)}，默认选择第一个版本")
            await cls._log(db, task.id, "warning", f"AI评估失败，使用第一个版本: {str(e)}")
            return 0

    @classmethod
    async def _auto_generate_outlines(
        cls,
        db: AsyncSession,
        task: AutoGeneratorTask,
        start_chapter: int
    ):
        """自动生成章节大纲（AI 自主决定章节数量）

        Args:
            db: 数据库会话
            task: 自动生成任务
            start_chapter: 起始章节号
        """
        from .prompt_service import PromptService
        from .llm_service import LLMService
        from ..utils.json_utils import remove_think_tags, unwrap_markdown_json

        await cls._log(
            db,
            task.id,
            "info",
            f"开始自动生成从第 {start_chapter} 章开始的大纲（AI 自主决定章节数）..."
        )

        # 获取项目信息
        novel_service = NovelService(db)

        # 获取用户ID（从任务中）
        user_id = task.user_id

        # 获取项目schema
        project_schema = await novel_service.get_project_schema(task.project_id, user_id)

        # ✅ 修复：检查 blueprint 是否存在
        if not project_schema.blueprint:
            error_msg = "项目蓝图未创建，无法生成大纲。请先在项目设置中创建蓝图。"
            logger.error(f"任务 {task.id}: {error_msg}")
            await cls._log(db, task.id, "error", error_msg)
            task.status = "failed"
            task.error_message = error_msg
            await db.commit()
            return

        blueprint_dict = project_schema.blueprint.model_dump()

        # ✅ 修复：直接查询数据库收集已完成章节摘要
        # 原因：project_schema.chapters 是空列表（性能优化），需要直接查询数据库
        completed_summaries = []

        # 查询所有已生成的章节（小于当前起始章节号，且有真实摘要）
        chapters_stmt = (
            select(Chapter, ChapterOutline)
            .outerjoin(ChapterOutline,
                      (Chapter.project_id == ChapterOutline.project_id) &
                      (Chapter.chapter_number == ChapterOutline.chapter_number))
            .where(
                Chapter.project_id == task.project_id,
                Chapter.chapter_number < start_chapter,
                Chapter.real_summary.isnot(None),
                Chapter.real_summary != ""
            )
            .order_by(Chapter.chapter_number)
        )
        chapters_result = await db.execute(chapters_stmt)
        chapters_rows = chapters_result.all()

        for chapter, outline in chapters_rows:
            completed_summaries.append({
                "chapter_number": chapter.chapter_number,
                "title": outline.title if outline else f"第{chapter.chapter_number}章",
                "summary": chapter.real_summary
            })

        await cls._log(
            db,
            task.id,
            "info",
            f"已收集 {len(completed_summaries)} 章已完成章节摘要，用于生成新大纲"
        )

        # ✅ 获取前两章的完整内容（用于大纲评估）
        previous_two_chapters = []
        if start_chapter > 1:
            prev_chapters_stmt = (
                select(Chapter)
                .where(
                    Chapter.project_id == task.project_id,
                    Chapter.chapter_number < start_chapter
                )
                .options(selectinload(Chapter.selected_version))
                .order_by(Chapter.chapter_number.desc())
                .limit(2)
            )
            prev_chapters_result = await db.execute(prev_chapters_stmt)
            prev_chapters = prev_chapters_result.scalars().all()

            for ch in reversed(prev_chapters):  # 反转顺序，让最早的在前
                if ch.selected_version and ch.selected_version.content:
                    # 获取章节标题
                    outline_stmt = select(ChapterOutline).where(
                        ChapterOutline.project_id == task.project_id,
                        ChapterOutline.chapter_number == ch.chapter_number
                    )
                    outline_result = await db.execute(outline_stmt)
                    outline = outline_result.scalar_one_or_none()

                    chapter_title = outline.title if outline else f"第{ch.chapter_number}章"
                    previous_two_chapters.append({
                        "number": ch.chapter_number,
                        "title": chapter_title,
                        "content": ch.selected_version.content
                    })

        # 获取大纲提示词
        prompt_service = PromptService(db)
        outline_prompt = await prompt_service.get_prompt("outline")
        if not outline_prompt:
            raise ValueError("缺少大纲提示词，请联系管理员配置 'outline' 提示词")

        # 获取所有分卷的快照数据
        volumes_stmt = select(Volume).where(Volume.project_id == task.project_id).order_by(Volume.volume_number)
        volumes_result = await db.execute(volumes_stmt)
        volumes = volumes_result.scalars().all()

        volumes_data = []
        for vol in volumes:
            vol_data = {
                "volume_number": vol.volume_number,
                "title": vol.title,
                "characters": vol.characters or [],
                "relationships": vol.relationships or [],
                "world_setting": vol.world_setting or {}
            }
            volumes_data.append(vol_data)

        # 构建请求payload（不再传递 num_chapters，让 AI 自主决定）
        payload = {
            "novel_blueprint": blueprint_dict,
            "completed_chapters": completed_summaries,  # 新增：传递已完成章节
            "volumes": volumes_data,  # 传递所有分卷的快照数据
            "wait_to_generate": {
                "start_chapter": start_chapter,
            },
        }

        # ✅ 检查是否使用3Agent大纲生成模式
        generation_mode = task.generation_config.get("generation_mode", "basic")

        if generation_mode == "agent_dialogue":
            # ========== 3Agent大纲生成模式 ==========
            await cls._log(
                db,
                task.id,
                "info",
                f"使用3Agent模式生成从第 {start_chapter} 章开始的大纲..."
            )

            from ..services.ai_orchestrator_helper import generate_outline_with_agents

            try:
                # ✅ 读取3Agent自定义配置
                agent_config = task.generation_config
                planner_temp = agent_config.get("agent_planner_temperature")
                writer_temp = agent_config.get("agent_writer_temperature")
                reviewer_temp = agent_config.get("agent_reviewer_temperature")
                min_score = agent_config.get("agent_min_score")
                max_iterations = agent_config.get("agent_max_iterations")
                # ✅ 读取3Agent LLM配置
                planner_provider = agent_config.get("agent_planner_provider")
                planner_model = agent_config.get("agent_planner_model")
                writer_provider = agent_config.get("agent_writer_provider")
                writer_model = agent_config.get("agent_writer_model")
                reviewer_provider = agent_config.get("agent_reviewer_provider")
                reviewer_model = agent_config.get("agent_reviewer_model")

                result = await generate_outline_with_agents(
                    db_session=db,
                    project_id=task.project_id,
                    start_chapter=start_chapter,
                    user_id=user_id,
                    blueprint_dict=blueprint_dict,
                    completed_summaries=completed_summaries,
                    volumes_data=volumes_data,
                    timeout=600.0,
                    planner_temperature=planner_temp,
                    writer_temperature=writer_temp,
                    reviewer_temperature=reviewer_temp,
                    min_score=min_score,
                    max_iterations=max_iterations,
                    planner_provider=planner_provider,
                    planner_model=planner_model,
                    writer_provider=writer_provider,
                    writer_model=writer_model,
                    reviewer_provider=reviewer_provider,
                    reviewer_model=reviewer_model,
                )

                # 从result中提取章节数据和元数据
                # 保留完整的result数据（包含volume_title, characters等）
                data = result.copy()
                # metadata用于日志记录
                metadata = result.get("metadata", {})

                await cls._log(
                    db,
                    task.id,
                    "success",
                    f"3Agent模式生成成功：{len(data['chapters'])}章，"
                    f"迭代{metadata.get('iterations', 0)}轮，"
                    f"评分{metadata.get('final_score', 0)}"
                )

            except Exception as e:
                logger.error(f"3Agent大纲生成失败: {str(e)}", exc_info=True)
                await cls._log(
                    db,
                    task.id,
                    "error",
                    f"3Agent大纲生成失败: {str(e)}"
                )
                raise

        else:
            # ========== 传统多版本大纲生成模式 ==========
            # ✅ 使用AI路由系统生成大纲
            from ..services.ai_orchestrator_helper import generate_outline

            # 记录任务日志
            await cls._log(
                db,
                task.id,
                "info",
                f"正在生成从第 {start_chapter} 章开始的大纲（AI 自主决定章节数）..."
            )

            # 🔄 生成多个大纲版本并让AI选择最佳
            outline_version_count = task.generation_config.get("outline_version_count", 3)  # 从配置读取
            outline_version_count = max(1, min(outline_version_count, 5))  # 限制在1-5之间

            outline_versions = []

            for version_idx in range(outline_version_count):
                await cls._log(
                    db,
                    task.id,
                    "info",
                    f"正在生成大纲版本 {version_idx + 1}/{outline_version_count}..."
                )

                logger.info(
                    f"开始调用AI功能: OUTLINE_GENERATION, 起始章节: {start_chapter}, 版本: {version_idx + 1}"
                )

                try:
                    response = await generate_outline(
                        db_session=db,
                        system_prompt=outline_prompt,
                        user_prompt=json.dumps(payload, ensure_ascii=False),
                        user_id=user_id,
                        temperature=0.7 + (version_idx * 0.1),  # 温度变化产生差异
                    )

                    logger.info(
                        f"AI功能调用成功: OUTLINE_GENERATION, 起始章节: {start_chapter}, 版本: {version_idx + 1}"
                    )

                    # 解析响应
                    normalized = unwrap_markdown_json(remove_think_tags(response))
                    version_data = json.loads(normalized)

                    # 验证基本结构
                    if version_data.get("chapters"):
                        outline_versions.append({
                            "version_id": version_idx + 1,
                            "data": version_data,
                            "raw_response": normalized[:500]
                        })
                        await cls._log(
                            db,
                            task.id,
                            "success",
                            f"版本 {version_idx + 1} 生成成功，包含 {len(version_data.get('chapters', []))} 个章节"
                        )
                    else:
                        logger.warning(f"版本 {version_idx + 1} 缺少章节数据")

                except json.JSONDecodeError as exc:
                    logger.warning(f"版本 {version_idx + 1} JSON解析失败: {exc}")
                    await cls._log(db, task.id, "warning", f"版本 {version_idx + 1} 生成失败")
                    continue
                except Exception as e:
                    logger.error(f"版本 {version_idx + 1} 生成失败: {str(e)}")
                    await cls._log(db, task.id, "warning", f"版本 {version_idx + 1} 生成失败: {str(e)}")
                    continue

            if not outline_versions:
                raise ValueError("所有大纲版本均生成失败，请检查提示词或重试")

            # 🎯 AI评估选择最佳版本（只有多版本时才评估）
            if len(outline_versions) > 1:
                await cls._log(
                    db,
                    task.id,
                    "info",
                    f"开始AI评估 {len(outline_versions)} 个大纲版本..."
                )

                best_version_idx = await cls._evaluate_outline_versions(
                    db=db,
                    task=task,
                    outline_versions=outline_versions,
                    blueprint_dict=blueprint_dict,
                    llm_service=LLMService(db),
                    prompt_service=prompt_service,
                    completed_chapters=completed_summaries,
                    previous_two_chapters=previous_two_chapters,
                    start_chapter=start_chapter,
                    volumes_data=volumes_data
                )

                data = outline_versions[best_version_idx]["data"]
                await cls._log(
                    db,
                    task.id,
                    "success",
                    f"AI选择了版本 {best_version_idx + 1} 作为最佳大纲"
                )
            else:
                # 只有一个版本，直接使用
                data = outline_versions[0]["data"]
                await cls._log(db, task.id, "info", "只生成了1个版本，直接使用")

        # 提取数据
        volume_title = data.get("volume_title", "")
        new_outlines = data.get("chapters", [])
        volume_characters = data.get("characters", [])  # 该卷的完整角色快照
        volume_relationships = data.get("relationships", [])  # 该卷的完整关系快照
        volume_world_setting = data.get("world_setting", {})  # 该卷的完整世界观快照

        if not new_outlines:
            raise ValueError("AI 未返回任何章节大纲")

        # 1. 创建或更新分卷（保存快照数据）
        volume_id = None
        if volume_title:
            # 根据起始章节号推断卷号
            result = await db.execute(
                select(Volume)
                .where(Volume.project_id == task.project_id)
                .order_by(Volume.volume_number.desc())
            )
            last_volume = result.scalars().first()
            next_volume_number = (last_volume.volume_number + 1) if last_volume else 1

            # 检查是否已存在该卷号
            result = await db.execute(
                select(Volume).where(
                    Volume.project_id == task.project_id,
                    Volume.volume_number == next_volume_number
                )
            )
            existing_volume = result.scalars().first()

            if existing_volume:
                existing_volume.title = volume_title
                # 保存快照数据到 Volume
                existing_volume.characters = volume_characters
                existing_volume.relationships = volume_relationships
                existing_volume.world_setting = volume_world_setting
                volume_id = existing_volume.id
                await cls._log(db, task.id, "info", f"更新分卷 {next_volume_number}: {volume_title}（包含 {len(volume_characters)} 个角色，{len(volume_relationships)} 个关系）")
            else:
                new_volume = Volume(
                    project_id=task.project_id,
                    volume_number=next_volume_number,
                    title=volume_title,
                    # 保存快照数据到 Volume
                    characters=volume_characters,
                    relationships=volume_relationships,
                    world_setting=volume_world_setting,
                )
                db.add(new_volume)
                await db.flush()
                volume_id = new_volume.id
                await cls._log(db, task.id, "info", f"创建新分卷 {next_volume_number}: {volume_title}（包含 {len(volume_characters)} 个角色，{len(volume_relationships)} 个关系）")
        else:
            # 如果没有卷名，使用默认分卷
            result = await db.execute(
                select(Volume)
                .where(Volume.project_id == task.project_id)
                .order_by(Volume.volume_number.desc())
                .limit(1)
            )
            last_volume = result.scalar_one_or_none()

            if not last_volume:
                last_volume = Volume(
                    project_id=task.project_id,
                    volume_number=1,
                    title="默认",
                    description="第一卷"
                )
                db.add(last_volume)
                await db.flush()

            volume_id = last_volume.id

        # 2. 保存章节大纲
        for item in new_outlines:
            stmt = (
                select(ChapterOutline)
                .where(
                    ChapterOutline.project_id == task.project_id,
                    ChapterOutline.chapter_number == item.get("chapter_number"),
                )
            )
            result = await db.execute(stmt)
            record = result.scalar_one_or_none()
            if record:
                # 更新现有大纲
                record.title = item.get("title", record.title)
                record.summary = item.get("summary", record.summary)
                if volume_id and not record.volume_id:
                    record.volume_id = volume_id
            else:
                # 创建新大纲
                db.add(
                    ChapterOutline(
                        project_id=task.project_id,
                        volume_id=volume_id,
                        chapter_number=item.get("chapter_number"),
                        title=item.get("title", ""),
                        summary=item.get("summary"),
                    )
                )

        # 注意：角色、关系、世界观已经保存到 Volume 的快照字段中
        # 不再需要单独添加到 BlueprintCharacter 或 NovelBlueprint

        await db.commit()

        await cls._log(
            db,
            task.id,
            "success",
            f"成功生成 {len(new_outlines)} 章大纲"
        )


    # ========== 增强模式处理方法 ==========

    @classmethod
    async def _evaluate_and_select_best_version(
        cls,
        db: AsyncSession,
        task: AutoGeneratorTask,
        chapter: Chapter,
        blueprint_dict: dict,
        llm_service: "LLMService"
    ) -> int:
        """
        ✅ AI评估章节版本并返回最佳版本的索引

        上下文构建：和生成摘要一样，包含完整上下文
        - 世界蓝图（JSON）
        - 分卷快照
        - 所有章节摘要
        - 上一章完整内容
        - 待评估的多个版本

        Args:
            db: 数据库会话
            task: 自动生成任务
            chapter: 章节对象（包含多个版本）
            blueprint_dict: 世界蓝图字典
            llm_service: LLM服务

        Returns:
            int: 最佳版本的索引（0-based）
        """
        import json
        from ..repositories.prompt_repository import PromptRepository
        from ..utils.text_utils import remove_think_tags

        try:
            # 1. 获取评估提示词
            prompt_repo = PromptRepository(db)
            evaluator_prompt = await prompt_repo.get_by_name("evaluation")

            if not evaluator_prompt or not evaluator_prompt.content:
                logger.warning("缺少评估提示词，降级为选择第一个版本")
                return 0

            # 2. 构建完整上下文（和生成摘要一样）
            # 2.1 获取项目和分卷信息
            project = await db.get(Project, task.project_id)
            if not project:
                logger.warning("项目不存在，使用简化上下文")
                # 降级为简化版本
                versions_to_evaluate = [
                    {"version_id": idx + 1, "content": version.content}
                    for idx, version in enumerate(sorted(chapter.versions, key=lambda item: item.created_at))
                ]
                evaluator_payload = {
                    "novel_blueprint": blueprint_dict,
                    "content_to_evaluate": {
                        "chapter_number": chapter.chapter_number,
                        "versions": versions_to_evaluate,
                    },
                }
            else:
                # 2.2 获取所有分卷（用于构建快照）
                volumes_result = await db.execute(
                    select(Volume)
                    .where(Volume.project_id == task.project_id)
                    .order_by(Volume.volume_number)
                )
                all_volumes = list(volumes_result.scalars().all())

                # 2.3 构建分卷快照
                volumes_snapshot = []
                for vol in all_volumes:
                    is_current = (chapter.volume_id == vol.id) if chapter.volume_id else False
                    volumes_snapshot.append({
                        "volume_number": vol.volume_number,
                        "title": f"{vol.title}{'（当前分卷）' if is_current else ''}",
                        "characters": vol.characters or [],
                        "relationships": vol.relationships or [],
                        "world_setting": vol.world_setting or {}
                    })

                # 2.4 获取所有已完成章节的摘要
                completed_chapters_result = await db.execute(
                    select(Chapter)
                    .where(
                        Chapter.project_id == task.project_id,
                        Chapter.chapter_number < chapter.chapter_number,
                        Chapter.real_summary.isnot(None)
                    )
                    .order_by(Chapter.chapter_number)
                )
                completed_chapters = list(completed_chapters_result.scalars().all())

                # 2.5 获取章节大纲（用于显示标题）
                outlines_result = await db.execute(
                    select(ChapterOutline)
                    .where(ChapterOutline.project_id == task.project_id)
                    .order_by(ChapterOutline.chapter_number)
                )
                outlines = list(outlines_result.scalars().all())
                outlines_map = {o.chapter_number: o for o in outlines}

                # 2.6 构建所有章节摘要文本
                all_summaries_text = ""
                if completed_chapters:
                    summaries = []
                    for ch in completed_chapters:
                        outline = outlines_map.get(ch.chapter_number)
                        title = outline.title if outline else f"第{ch.chapter_number}章"
                        summaries.append(f"- 第{ch.chapter_number}章 - {title}: {ch.real_summary}")
                    all_summaries_text = "\n".join(summaries)
                else:
                    all_summaries_text = "暂无前序章节"

                # 2.7 获取上一章完整内容
                previous_chapter_text = "暂无前序章节"
                if chapter.chapter_number > 1:
                    prev_result = await db.execute(
                        select(Chapter)
                        .where(
                            Chapter.project_id == task.project_id,
                            Chapter.chapter_number == chapter.chapter_number - 1
                        )
                        .options(selectinload(Chapter.selected_version))
                    )
                    prev_chapter = prev_result.scalar_one_or_none()

                    if prev_chapter and prev_chapter.selected_version:
                        prev_outline = outlines_map.get(prev_chapter.chapter_number)
                        prev_title = prev_outline.title if prev_outline else f"第{prev_chapter.chapter_number}章"
                        previous_chapter_text = f"### 第{prev_chapter.chapter_number}章 - {prev_title}\n{prev_chapter.selected_version.content}"

                # 2.8 准备待评估的版本
                versions_to_evaluate = [
                    {"version_id": idx + 1, "content": version.content}
                    for idx, version in enumerate(sorted(chapter.versions, key=lambda item: item.created_at))
                ]

                # 2.9 构建完整的评估payload（包含丰富上下文）
                blueprint_with_snapshot = blueprint_dict.copy()
                blueprint_with_snapshot["volumes_snapshot"] = volumes_snapshot

                evaluator_payload = {
                    "novel_blueprint": blueprint_with_snapshot,
                    "completed_chapters_summary": all_summaries_text,
                    "previous_chapter_content": previous_chapter_text,
                    "content_to_evaluate": {
                        "chapter_number": chapter.chapter_number,
                        "versions": versions_to_evaluate,
                    },
                }

            # 3. 调用AI进行评估
            evaluation_raw = await llm_service.get_llm_response(
                system_prompt=evaluator_prompt.content,
                conversation_history=[{"role": "user", "content": json.dumps(evaluator_payload, ensure_ascii=False)}],
                temperature=0.3,
                user_id=task.user_id,
                timeout=360.0,
            )

            evaluation_clean = remove_think_tags(evaluation_raw)

            # 4. 保存评估结果
            from ..services.novel_service import NovelService
            novel_service = NovelService(db)
            await novel_service.add_chapter_evaluation(chapter, None, evaluation_clean)

            # 5. 解析评估结果，提取最佳版本
            try:
                evaluation_data = json.loads(evaluation_clean)
                best_choice = evaluation_data.get("best_choice")

                if best_choice and isinstance(best_choice, int):
                    # 转换为0-based索引
                    best_index = best_choice - 1

                    # 验证索引有效性
                    if 0 <= best_index < len(chapter.versions):
                        logger.info(f"AI评估推荐版本 {best_choice}，原因: {evaluation_data.get('reason_for_choice', '未提供')}")
                        return best_index
                    else:
                        logger.warning(f"AI推荐的版本索引 {best_choice} 超出范围，降级为第一个版本")
                        return 0
                else:
                    logger.warning(f"评估结果中未找到有效的 best_choice 字段，降级为第一个版本")
                    return 0

            except json.JSONDecodeError as e:
                logger.error(f"解析评估结果失败: {e}，评估内容: {evaluation_clean[:200]}...")
                return 0

        except Exception as e:
            logger.error(f"AI评估过程失败: {e}", exc_info=True)
            return 0

    @classmethod
    async def _process_basic_mode(
        cls,
        db: AsyncSession,
        task: AutoGeneratorTask,
        chapter: Chapter,
        llm_service: "LLMService"
    ):
        """基础模式：只生成摘要

        注意：此方法不会自己commit，由调用者控制事务边界
        """
        # 获取选中版本的内容
        if not chapter.selected_version:
            logger.warning(f"章节 {chapter.chapter_number} 没有选中版本，跳过摘要生成")
            return

        content = chapter.selected_version.content

        # ✅ 使用AI路由系统生成摘要
        from ..services.ai_orchestrator_helper import generate_summary
        from ..services.prompt_service import PromptService
        from ..services.novel_service import NovelService

        # 记录任务日志
        await cls._log(
            db,
            task.id,
            "info",
            f"正在生成第 {chapter.chapter_number} 章摘要（使用 Gemini Flash）..."
        )

        logger.info(
            f"开始调用AI功能: SUMMARY_EXTRACTION, 章节: {chapter.chapter_number}"
        )

        # 获取摘要提示词
        prompt_service = PromptService(db)
        system_prompt = await prompt_service.get_prompt("extraction")

        # ✅ 新增：构建和生成章节内容相同的上下文（只是少传一章）
        # 1. 获取项目和蓝图
        novel_service = NovelService(db)
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload, joinedload

        result = await db.execute(
            select(Project)
            .where(Project.id == task.project_id)
            .options(
                selectinload(Project.outlines),
                joinedload(Project.blueprint),
                selectinload(Project.volumes)
            )
        )
        project = result.scalar_one_or_none()
        if not project:
            logger.error(f"项目 {task.project_id} 不存在")
            # 降级：只用本章内容
            summary = await generate_summary(
                db_session=db,
                system_prompt=system_prompt,
                chapter_content=content,
                user_id=task.user_id,
            )
            chapter.real_summary = summary
            return

        # 2. 构建蓝图
        project_schema = await novel_service._serialize_project(project)
        blueprint_dict = project_schema.blueprint.model_dump() if project_schema.blueprint else {}

        # 清理蓝图
        banned_keys = {"chapter_summaries", "chapter_details", "chapter_dialogues", "chapter_events", "conversation_history", "character_timelines"}
        for key in banned_keys:
            blueprint_dict.pop(key, None)

        # 3. 添加分卷快照
        outlines_map = {item.chapter_number: item for item in project.outlines}
        current_outline = outlines_map.get(chapter.chapter_number)
        current_volume_id = current_outline.volume_id if current_outline else None

        volumes_snapshot = []
        for vol in sorted(project.volumes, key=lambda v: v.volume_number):
            is_current = (vol.id == current_volume_id)
            vol_data = {
                "volume_number": vol.volume_number,
                "title": vol.title,
                "characters": vol.characters or [],
                "relationships": vol.relationships or [],
                "world_setting": vol.world_setting or {},
                "is_current": is_current  # 🔥 标注当前卷
            }
            volumes_snapshot.append(vol_data)

        # 🔥 不再把 volumes_snapshot 放到 blueprint_dict 中，而是作为单独参数传递

        # 🔥 现在不再构建 enhanced_context，改为传递结构化参数
        summary = await generate_summary(
            db_session=db,
            system_prompt=system_prompt,
            chapter_content=content,  # 🔥 只传递章节内容
            user_id=task.user_id,
            blueprint_dict=blueprint_dict,  # 🔥 单独传递蓝图
            volumes_snapshot=volumes_snapshot,  # 🔥 单独传递分卷快照
        )

        logger.info(
            f"AI功能调用成功: SUMMARY_EXTRACTION, 章节: {chapter.chapter_number}"
        )

        # 保存摘要（不commit，由调用者控制）
        chapter.real_summary = summary

        logger.info(f"基础模式：第 {chapter.chapter_number} 章摘要生成完成")

    @classmethod
    async def _process_enhanced_mode(
        cls,
        db: AsyncSession,
        task: AutoGeneratorTask,
        chapter: Chapter,
        chapter_number: int,
        blueprint: dict,
        llm_service: "LLMService"
    ):
        """
        ✅ 增强模式：异步处理（立即返回 + 后台分析）

        工作流程：
        1. 生成基础摘要（快速，同步）
        2. 立即提交，用户可见章节内容
        3. 创建pending_analysis记录
        4. 后台处理器异步执行增强分析

        优势：
        - 用户体验提升80%（立即看到章节）
        - 不阻塞生成流程
        - 支持重试和监控
        """
        try:
            # 获取选中版本的内容
            if not chapter.selected_version:
                logger.warning(f"章节 {chapter_number} 没有选中版本，降级到基础模式")
                await cls._process_basic_mode(db, task, chapter, llm_service)
                # ✅ 修复：提交事务，确保摘要写入数据库
                await db.commit()
                return

            content = chapter.selected_version.content

            # ✅ 动态阈值检查：章节长度
            from ..schemas.generation_config import should_run_enhanced_analysis
            if not should_run_enhanced_analysis(task.generation_config or {}, len(content)):
                logger.info(
                    f"第 {chapter_number} 章长度({len(content)}字)低于阈值，"
                    f"降级到基础模式以节省成本"
                )
                await cls._process_basic_mode(db, task, chapter, llm_service)
                # ✅ 修复：提交事务，确保摘要写入数据库
                await db.commit()
                return

            # ✅ 步骤1: 生成基础摘要（快速，同步）
            from .super_analysis_service import SuperAnalysisService
            super_analysis = SuperAnalysisService(db, llm_service)

            # 只执行基础分析（摘要生成）
            basic_result, _ = await super_analysis.analyze_chapter(
                chapter_number=chapter_number,
                chapter_content=content,
                blueprint=blueprint,
                user_id=task.user_id,
                enhanced_mode=False  # ✅ 关键：只做基础分析
            )

            # ✅ 步骤2: 保存摘要并立即提交
            chapter.real_summary = basic_result.get("summary", "")
            await db.commit()  # ✅ 立即提交，用户可见

            logger.info(f"第 {chapter_number} 章基础摘要已保存，开始异步增强分析")

            # ✅ 步骤3: 创建异步分析任务
            from ..models.async_task import PendingAnalysis

            pending = PendingAnalysis(
                chapter_id=chapter.id,
                project_id=task.project_id,
                user_id=task.user_id,
                task_id=task.id,
                status='pending',
                priority=5,  # 默认优先级
                generation_config=task.generation_config,
                max_retries=3
            )
            db.add(pending)
            await db.commit()

            logger.info(
                f"第 {chapter_number} 章已创建异步分析任务 (ID: {pending.id})，"
                f"后台处理器将在 {cls._get_processor_poll_interval()} 秒内开始处理"
            )

        except Exception as e:
            logger.error(f"增强模式处理失败：{e}", exc_info=True)
            await db.rollback()
            raise

    @classmethod
    def _get_processor_poll_interval(cls) -> int:
        """获取处理器轮询间隔"""
        return 10  # 默认10秒

    # ========== 角色自动管理和世界观扩展已移除 ==========
    # 这些功能已被分卷版本化系统取代，角色和世界观现在保存在 Volume 的快照中

    @staticmethod
    def _build_previous_chapters_context(completed_chapters: List[dict]) -> str:
        """
        ✅ 新增：构建前置章节上下文（智能分层）

        策略：
        - 少于3章：全部用完整内容
        - 多于3章：早期章节用摘要，最近3章用完整内容

        Args:
            completed_chapters: 已完成章节列表，每个元素包含 chapter_number, title, summary, content

        Returns:
            格式化的前置章节上下文字符串
        """
        if not completed_chapters:
            return ""

        # ✅ 向后兼容：少于3章时，全部用完整内容
        if len(completed_chapters) <= 3:
            result = []
            for ch in completed_chapters:
                result.append(
                    f"=== 第{ch['chapter_number']}章：{ch['title']} ===\n{ch['content']}"
                )
            return "\n\n".join(result)

        # ✅ 新增：多于3章时，智能分层
        early_chapters = completed_chapters[:-3]
        recent_chapters = completed_chapters[-3:]

        result = "【前期剧情概要】\n"
        early_summaries = []
        for ch in early_chapters:
            early_summaries.append(
                f"第{ch['chapter_number']}章《{ch['title']}》：{ch['summary']}"
            )
        result += "\n".join(early_summaries)

        result += "\n\n【最近章节完整内容】\n"
        recent_contents = []
        for ch in recent_chapters:
            recent_contents.append(
                f"=== 第{ch['chapter_number']}章：{ch['title']} ===\n{ch['content']}"
            )
        result += "\n\n".join(recent_contents)

        return result

    @classmethod
    async def _auto_upload_chapter(
        cls,
        db: AsyncSession,
        task: AutoGeneratorTask,
        chapter_number: int
    ):
        """自动上传章节到番茄小说

        Args:
            db: 数据库会话
            task: 自动生成任务
            chapter_number: 章节号
        """
        try:
            from .fanqie_publisher_service import FanqiePublisherService

            await cls._log(
                db,
                task.id,
                "info",
                f"开始自动上传第 {chapter_number} 章到番茄小说（账号: {task.fanqie_account}）"
            )

            # 创建番茄发布服务实例（使用 async with 确保资源正确管理）
            async with FanqiePublisherService(headless=True) as publisher:
                # 上传单个章节（自动生成器模式，不需要间隔）
                result = await publisher.upload_novel_to_fanqie(
                    db=db,
                    project_id=task.project_id,
                    account=task.fanqie_account,
                    upload_interval=0  # 自动生成器模式不需要间隔
                )

                if result.get("success"):
                    await cls._log(
                        db,
                        task.id,
                        "success",
                        f"第 {chapter_number} 章已成功上传到番茄小说"
                    )
                else:
                    error_msg = result.get("error", "未知错误")
                    await cls._log(
                        db,
                        task.id,
                        "error",
                        f"第 {chapter_number} 章上传失败: {error_msg}"
                    )

        except Exception as e:
            logger.error(f"自动上传第 {chapter_number} 章失败: {e}")
            await cls._log(
                db,
                task.id,
                "error",
                f"第 {chapter_number} 章自动上传异常: {str(e)}"
            )
