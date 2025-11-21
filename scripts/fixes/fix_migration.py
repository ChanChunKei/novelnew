#!/usr/bin/env python3
"""手动添加定时启动字段到数据库"""
import sqlite3
import sys

db_path = 'backend/storage/arboris.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("🔧 开始添加字段...")

    # 1. 添加 scheduled_start_time
    try:
        cursor.execute('ALTER TABLE auto_generator_tasks ADD COLUMN scheduled_start_time TIMESTAMP NULL')
        print("  ✅ 添加 scheduled_start_time 字段")
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  scheduled_start_time 已存在")
        else:
            raise

    # 2. 添加 delay_seconds
    try:
        cursor.execute('ALTER TABLE auto_generator_tasks ADD COLUMN delay_seconds INTEGER DEFAULT 0')
        print("  ✅ 添加 delay_seconds 字段")
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  delay_seconds 已存在")
        else:
            raise

    # 3. 添加 batch_id
    try:
        cursor.execute('ALTER TABLE auto_generator_tasks ADD COLUMN batch_id VARCHAR(36) NULL')
        print("  ✅ 添加 batch_id 字段")
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  batch_id 已存在")
        else:
            raise

    # 4. 创建索引
    try:
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_auto_generator_tasks_scheduled_start
            ON auto_generator_tasks(scheduled_start_time)
            WHERE scheduled_start_time IS NOT NULL
        ''')
        print("  ✅ 创建 scheduled_start_time 索引")
    except Exception as e:
        print(f"  ⚠️  创建 scheduled_start_time 索引失败: {e}")

    try:
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_auto_generator_tasks_batch_id
            ON auto_generator_tasks(batch_id)
            WHERE batch_id IS NOT NULL
        ''')
        print("  ✅ 创建 batch_id 索引")
    except Exception as e:
        print(f"  ⚠️  创建 batch_id 索引失败: {e}")

    conn.commit()

    # 验证
    print("\n✅ 字段添加完成！\n")
    print("验证表结构:")
    cursor.execute('PRAGMA table_info(auto_generator_tasks)')
    columns = cursor.fetchall()

    for col in columns:
        print(f"  - {col[1]} ({col[2]})")

    conn.close()
    print("\n✅ 迁移成功！可以重启后端服务了。")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    sys.exit(1)
