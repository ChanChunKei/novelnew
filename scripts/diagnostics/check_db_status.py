#!/usr/bin/env python3
"""
快速检查数据库状态
"""
import sqlite3
from pathlib import Path

db_path = "backend/storage/arboris.db"

if not Path(db_path).exists():
    print(f"❌ 数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查章节总数
cursor.execute("SELECT COUNT(*) FROM chapters")
total = cursor.fetchone()[0]
print(f"📊 章节总数: {total}")

if total == 0:
    print("\n❌ 数据库中没有章节")
    exit(0)

# 检查有selected_version的章节
cursor.execute("""
    SELECT COUNT(*)
    FROM chapters
    WHERE selected_version_id IS NOT NULL
""")
with_version = cursor.fetchone()[0]
print(f"📊 有selected_version的章节: {with_version}")

# 检查最新的章节
cursor.execute("""
    SELECT
        c.id,
        c.chapter_number,
        c.selected_version_id,
        p.title as project_title
    FROM chapters c
    LEFT JOIN novel_projects p ON c.project_id = p.id
    ORDER BY c.id DESC
    LIMIT 5
""")

print("\n最新的5个章节:")
print("-" * 60)
for row in cursor.fetchall():
    ch_id, ch_num, version_id, project = row
    print(f"章节ID: {ch_id}, 章节号: {ch_num}, 版本ID: {version_id}, 项目: {project}")

# 检查最新的版本
cursor.execute("""
    SELECT
        cv.id,
        cv.chapter_id,
        LENGTH(cv.content) as content_length,
        cv.created_at
    FROM chapter_versions cv
    ORDER BY cv.created_at DESC
    LIMIT 5
""")

print("\n最新的5个版本:")
print("-" * 60)
for row in cursor.fetchall():
    ver_id, ch_id, length, created = row
    print(f"版本ID: {ver_id}, 章节ID: {ch_id}, 内容长度: {length}, 创建时间: {created}")

conn.close()
