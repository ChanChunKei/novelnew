#!/usr/bin/env python3
"""直接查看章节内容，不做复杂分析"""
import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "backend/storage/arboris.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查询最近3章
cursor.execute('''
SELECT c.chapter_number, p.title, cv.content, cv.metadata
FROM chapters c
JOIN chapter_versions cv ON c.selected_version_id = cv.id
JOIN novel_projects p ON c.project_id = p.id
ORDER BY cv.created_at DESC
LIMIT 3
''')

for idx, (chapter_num, project_title, content, metadata) in enumerate(cursor.fetchall(), 1):
    print(f"\n{'='*80}")
    print(f"第 {chapter_num} 章 - {project_title}")
    print(f"{'='*80}")

    # 基本信息
    print(f"content 类型: {type(content)}")
    print(f"content 是否为 None: {content is None}")
    if content:
        print(f"content 长度: {len(content)}")
        print(f"\n前1000字符:")
        print("-"*80)
        print(content[:1000])
        print("...")
    else:
        print("❌ content 是 None 或空")

    print(f"\nmetadata 类型: {type(metadata)}")
    print(f"metadata 是否为 None: {metadata is None}")
    if metadata:
        print(f"metadata 长度: {len(metadata)}")

    if idx < 3:
        print("\n" + "~"*80)

conn.close()
