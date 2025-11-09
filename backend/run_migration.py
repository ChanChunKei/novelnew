"""运行数据库迁移"""
import asyncio
import os
from pathlib import Path
from sqlalchemy import text
from app.db.session import AsyncSessionLocal, engine
from app.db.base import Base

# 导入所有模型，确保 Base.metadata 包含所有表定义
from app import models  # noqa: F401

async def run_migration():
    """运行数据库迁移：先创建所有表，再运行增量迁移"""

    # 1. 使用 SQLAlchemy 创建所有表（如果不存在）
    print("📦 创建数据库表...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库表创建完成")

    # 2. 运行增量迁移脚本
    migrations_dir = Path(__file__).parent / 'migrations'
    if not migrations_dir.exists():
        print("⚠️  未找到 migrations 目录，跳过增量迁移")
        return

    # 获取所有 .sql 文件并排序
    migration_files = sorted(migrations_dir.glob('*.sql'))

    if not migration_files:
        print("⚠️  未找到迁移文件，跳过增量迁移")
        return

    print(f"\n📝 找到 {len(migration_files)} 个迁移文件")

    async with AsyncSessionLocal() as db:
        for migration_file in migration_files:
            print(f"\n执行迁移: {migration_file.name}")

            try:
                with open(migration_file, 'r', encoding='utf-8') as f:
                    sql = f.read()

                # 分割SQL语句并执行
                statements = [
                    s.strip()
                    for s in sql.split(';')
                    if s.strip() and not s.strip().startswith('--') and not s.strip().startswith('COMMENT')
                ]

                for stmt in statements:
                    if stmt:
                        try:
                            await db.execute(text(stmt))
                        except Exception as e:
                            # 忽略已存在的表/列错误
                            error_msg = str(e).lower()
                            if 'already exists' in error_msg or 'duplicate column' in error_msg:
                                print(f"  ⏭️  跳过（已存在）: {stmt[:60]}...")
                            else:
                                print(f"  ⚠️  警告: {e}")

                await db.commit()
                print(f"  ✅ {migration_file.name} 完成")

            except Exception as e:
                print(f"  ❌ {migration_file.name} 失败: {e}")
                await db.rollback()

    print("\n✅ 所有迁移完成")

if __name__ == '__main__':
    asyncio.run(run_migration())

