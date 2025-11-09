#!/usr/bin/env python3
"""检查并列出所有未完成灵感项目的运行中任务"""
import asyncio
import sys
from pathlib import Path

# 添加backend到path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload

from app.models.novel import NovelProject, ChapterOutline
from app.models.auto_generator import AutoGeneratorTask


async def main():
    # 创建数据库引擎
    database_url = "sqlite+aiosqlite:///backend/data.db"
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 1. 获取所有运行中/等待中的任务
        result = await db.execute(
            select(AutoGeneratorTask)
            .where(AutoGeneratorTask.status.in_(["pending", "running", "paused"]))
        )
        active_tasks = result.scalars().all()

        print(f"📊 总共有 {len(active_tasks)} 个活跃任务（pending/running/paused）\n")

        if not active_tasks:
            print("✅ 没有活跃任务")
            return

        # 2. 检查每个任务对应的项目是否有章节大纲
        invalid_tasks = []

        for task in active_tasks:
            # 获取项目
            project_result = await db.execute(
                select(NovelProject)
                .where(NovelProject.id == task.project_id)
                .options(selectinload(NovelProject.outlines))
            )
            project = project_result.scalar_one_or_none()

            if not project:
                print(f"⚠️  任务 #{task.id} 的项目 {task.project_id} 不存在")
                invalid_tasks.append((task, None, "项目不存在"))
                continue

            # 检查章节大纲
            outline_result = await db.execute(
                select(ChapterOutline)
                .where(ChapterOutline.project_id == task.project_id)
            )
            outlines = outline_result.scalars().all()

            if not outlines or len(outlines) == 0:
                print(f"❌ 发现无效任务！")
                print(f"   任务ID: {task.id}")
                print(f"   项目ID: {task.project_id}")
                print(f"   项目标题: {project.title}")
                print(f"   任务状态: {task.status}")
                print(f"   已生成章节: {task.chapters_generated}")
                print(f"   章节大纲数量: 0 ❌")
                print(f"   创建时间: {task.created_at}")
                print()
                invalid_tasks.append((task, project, "无章节大纲"))
            else:
                print(f"✅ 任务 #{task.id} - 项目 '{project.title}' - 有 {len(outlines)} 个大纲 - 状态: {task.status}")

        print(f"\n{'='*60}")
        print(f"📈 统计结果：")
        print(f"   总活跃任务数: {len(active_tasks)}")
        print(f"   有效任务数: {len(active_tasks) - len(invalid_tasks)}")
        print(f"   无效任务数: {len(invalid_tasks)} ❌")

        if invalid_tasks:
            print(f"\n⚠️  发现 {len(invalid_tasks)} 个无效任务需要处理！")
            print(f"\n建议操作：")
            print(f"   1. 停止这些无效任务")
            print(f"   2. 运行清理脚本：python cleanup_invalid_tasks.py")
        else:
            print(f"\n✅ 所有活跃任务都是有效的！")


if __name__ == "__main__":
    asyncio.run(main())
