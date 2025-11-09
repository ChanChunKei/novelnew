#!/usr/bin/env python3
"""诊断自动生成任务性能问题"""
import asyncio
import sys
import os

# 强制使用 SQLite
os.environ['DB_PROVIDER'] = 'sqlite'
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///backend/storage/arboris.db'

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy import select, func, text
from backend.app.db.session import AsyncSessionLocal
from backend.app.models.auto_generator import AutoGeneratorTask
from backend.app.models.novel import Chapter

async def diagnose():
    """诊断性能问题"""

    print("=" * 60)
    print("自动生成任务性能诊断")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # 1. 检查运行中的任务数量
        print("\n1️⃣ 检查运行中的任务...")
        result = await db.execute(
            select(AutoGeneratorTask)
            .where(AutoGeneratorTask.status.in_(["running", "pending"]))
        )
        running_tasks = result.scalars().all()

        print(f"   运行中/等待中的任务数: {len(running_tasks)}")
        if running_tasks:
            for task in running_tasks:
                print(f"   - 任务 ID={task.id}, 项目={task.project_id[:8]}..., 状态={task.status}, 已生成={task.chapters_generated}章")

        # 2. 检查数据库大小
        print("\n2️⃣ 检查数据库大小...")
        result = await db.execute(text("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();"))
        db_size = result.scalar()
        print(f"   数据库大小: {db_size / 1024 / 1024:.2f} MB")

        # 3. 检查章节数量
        print("\n3️⃣ 检查章节数量...")
        result = await db.execute(select(func.count(Chapter.id)))
        chapter_count = result.scalar()
        print(f"   总章节数: {chapter_count}")

        result = await db.execute(
            select(func.count(Chapter.id))
            .where(Chapter.selected_version_id.isnot(None))
        )
        completed_count = result.scalar()
        print(f"   已完成章节数: {completed_count}")

        # 4. 检查任务历史
        print("\n4️⃣ 检查最近的任务...")
        result = await db.execute(
            select(AutoGeneratorTask)
            .order_by(AutoGeneratorTask.created_at.desc())
            .limit(5)
        )
        recent_tasks = result.scalars().all()

        for task in recent_tasks:
            print(f"   - 任务 ID={task.id}, 状态={task.status}, 已生成={task.chapters_generated}/{task.target_chapters or '无限'}章, 创建于={task.created_at}")

        # 5. 测试数据库查询速度
        print("\n5️⃣ 测试数据库查询速度...")
        import time

        # 测试简单查询
        start = time.time()
        await db.execute(select(AutoGeneratorTask).limit(1))
        elapsed = time.time() - start
        print(f"   简单查询耗时: {elapsed*1000:.2f}ms")

        # 测试复杂查询
        start = time.time()
        await db.execute(
            select(AutoGeneratorTask)
            .where(AutoGeneratorTask.status == "running")
        )
        elapsed = time.time() - start
        print(f"   条件查询耗时: {elapsed*1000:.2f}ms")

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)

    print("\n💡 性能分析:")
    if len(running_tasks) > 5:
        print("   ⚠️  运行中的任务过多（>5），可能导致创建新任务时等待信号量")
    else:
        print("   ✅ 运行中的任务数量正常")

    if db_size / 1024 / 1024 > 100:
        print("   ⚠️  数据库较大（>100MB），可能影响查询速度")
    else:
        print("   ✅ 数据库大小正常")

    if chapter_count > 500:
        print("   ⚠️  章节数量较多（>500），项目列表加载已优化")
    else:
        print("   ✅ 章节数量正常")

if __name__ == "__main__":
    asyncio.run(diagnose())
