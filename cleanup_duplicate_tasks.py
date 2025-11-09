#!/usr/bin/env python3
"""清理重复的自动生成任务

问题：同一个项目可能有多个 pending/running 状态的任务，导致 "Multiple rows" 错误
解决：保留最新的任务，停止其他旧任务
"""
import asyncio
import sys
import os

# 强制使用 SQLite
os.environ['DB_PROVIDER'] = 'sqlite'
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///backend/storage/arboris.db'

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy import select, update, func
from backend.app.db.session import AsyncSessionLocal
from backend.app.models.auto_generator import AutoGeneratorTask


async def cleanup_duplicate_tasks():
    """清理重复的任务"""
    async with AsyncSessionLocal() as db:
        print("🔍 检查重复的任务...")

        # 查找所有运行中的任务
        result = await db.execute(
            select(AutoGeneratorTask)
            .where(AutoGeneratorTask.status.in_(['pending', 'running', 'paused']))
            .order_by(AutoGeneratorTask.project_id, AutoGeneratorTask.created_at.desc())
        )
        tasks = result.scalars().all()

        if not tasks:
            print("✅ 没有找到运行中的任务")
            return

        # 按项目分组
        tasks_by_project = {}
        for task in tasks:
            if task.project_id not in tasks_by_project:
                tasks_by_project[task.project_id] = []
            tasks_by_project[task.project_id].append(task)

        # 检查重复
        duplicates_found = False
        for project_id, project_tasks in tasks_by_project.items():
            if len(project_tasks) > 1:
                duplicates_found = True
                print(f"\n⚠️  项目 {project_id} 有 {len(project_tasks)} 个运行中的任务：")

                # 显示所有任务
                for i, task in enumerate(project_tasks, 1):
                    print(f"  {i}. 任务 ID: {task.id}")
                    print(f"     状态: {task.status}")
                    print(f"     创建时间: {task.created_at}")
                    print(f"     已生成章节: {task.chapters_generated}")

                # 保留最新的，停止其他的
                keep_task = project_tasks[0]  # 最新的（已按时间降序排序）
                old_tasks = project_tasks[1:]  # 旧的任务

                print(f"  \n  ✅ 保留最新任务: ID {keep_task.id}")
                print(f"  ⏹️  停止 {len(old_tasks)} 个旧任务:")

                for task in old_tasks:
                    print(f"     - 任务 ID {task.id}")
                    task.status = 'stopped'

                await db.commit()

        if not duplicates_found:
            print("✅ 所有项目都只有1个或0个运行中的任务，无需清理")
        else:
            print("\n✅ 清理完成！")

        # 显示统计
        print("\n📊 最终统计:")
        result = await db.execute(
            select(AutoGeneratorTask.status, func.count(AutoGeneratorTask.id))
            .group_by(AutoGeneratorTask.status)
        )
        stats = result.all()

        for status, count in stats:
            print(f"  {status}: {count} 个任务")


if __name__ == "__main__":
    asyncio.run(cleanup_duplicate_tasks())
