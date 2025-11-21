#!/usr/bin/env python3
"""应用定时启动功能的数据库迁移"""
import asyncio
import sys
import os

# 强制使用 SQLite
os.environ['DB_PROVIDER'] = 'sqlite'
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///backend/storage/arboris.db'

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy import text
from backend.app.db.session import AsyncSessionLocal


async def apply_migration():
    """应用迁移"""
    async with AsyncSessionLocal() as db:
        try:
            # 读取迁移 SQL
            with open('backend/migrations/add_scheduled_start.sql', 'r', encoding='utf-8') as f:
                migration_sql = f.read()

            # 分割成单独的语句
            statements = []
            current_statement = []

            for line in migration_sql.split('\n'):
                line = line.strip()
                # 跳过注释和空行
                if not line or line.startswith('--'):
                    continue
                current_statement.append(line)
                if line.endswith(';'):
                    statements.append(' '.join(current_statement))
                    current_statement = []

            # 执行每个语句
            for i, stmt in enumerate(statements, 1):
                try:
                    print(f"执行语句 {i}/{len(statements)}: {stmt[:100]}...")
                    await db.execute(text(stmt))
                    await db.commit()
                    print(f"  ✅ 成功")
                except Exception as e:
                    # 如果字段已存在，忽略错误
                    error_msg = str(e).lower()
                    if 'duplicate column' in error_msg or 'already exists' in error_msg:
                        print(f"  ⚠️  跳过（字段已存在）")
                    else:
                        print(f"  ❌ 失败: {e}")
                        raise

            print("\n✅ 迁移完成！")

            # 验证迁移结果
            result = await db.execute(text("PRAGMA table_info(auto_generator_tasks)"))
            columns = result.fetchall()

            print("\n当前表结构：")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")

            # 检查新字段是否存在
            column_names = [col[1] for col in columns]
            new_fields = ['scheduled_start_time', 'delay_seconds', 'batch_id']

            print("\n新增字段检查：")
            for field in new_fields:
                if field in column_names:
                    print(f"  ✅ {field}")
                else:
                    print(f"  ❌ {field} (未找到)")

        except Exception as e:
            print(f"\n❌ 迁移失败: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(apply_migration())
