#!/usr/bin/env python3
"""
预览章节内容，检测格式问题

使用方法：
  python3 preview_chapters.py [数据库路径] [章节数]

示例：
  python3 preview_chapters.py                    # 查看最近3章
  python3 preview_chapters.py /path/to/db.db 5  # 查看最近5章
"""

import sqlite3
import sys
import json
from pathlib import Path

def find_database():
    """自动查找数据库"""
    candidates = ["backend/storage/arboris.db", "storage/arboris.db", "arboris.db"]
    for candidate in candidates:
        db_file = Path.cwd() / candidate
        if db_file.exists():
            return str(db_file)
    return None

# 解析参数
db_path = sys.argv[1] if len(sys.argv) > 1 else find_database()
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 3

if not db_path:
    print("❌ 未找到数据库，请指定路径")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"\n📖 预览最近 {limit} 章内容")
print("=" * 80)

cursor.execute("""
SELECT
    c.chapter_number,
    p.title as project_title,
    cv.content,
    cv.metadata,
    cv.created_at,
    c.word_count
FROM chapters c
JOIN chapter_versions cv ON c.selected_version_id = cv.id
JOIN novel_projects p ON c.project_id = p.id
ORDER BY cv.created_at DESC
LIMIT ?
""", (limit,))

chapters = cursor.fetchall()

if not chapters:
    print("📭 没有找到章节")
    sys.exit(0)

for idx, (chapter_num, project, content, metadata, created, word_count) in enumerate(chapters, 1):
    print(f"\n{'='*80}")
    print(f"📄 第 {chapter_num} 章 - {project}")
    print(f"⏰ 创建时间: {created}")
    print(f"📊 字数: {word_count}")
    print(f"{'='*80}")

    # 检测格式问题
    issues = []

    if not content:
        issues.append("❌ 内容为空")
        return issues

    # 检查1：是否包含 planner 格式关键词
    planner_keywords = ["analysis:", "plan:", "queries_summary:", "notes_for_writer:"]
    content_preview = content[:500] if len(content) >= 500 else content
    for kw in planner_keywords:
        if kw in content_preview:
            issues.append(f"⚠️  包含 Planner 关键词: {kw}")

    # 检查2：是否是纯 JSON
    content_stripped = content.strip()
    if content_stripped.startswith("{") and content_stripped.endswith("}"):
        try:
            json.loads(content)
            issues.append("⚠️  内容是纯 JSON 格式")
        except:
            pass

    # 检查3：是否包含 JSON 标记
    if content.strip().startswith("```json") or content.strip().startswith("```"):
        issues.append("⚠️  包含 Markdown 代码块标记")

    # 检查4：字数异常
    if word_count < 500:
        issues.append(f"⚠️  字数过少: {word_count}")

    # 显示问题
    if issues:
        print("\n🚨 检测到格式问题:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n✅ 格式正常")

    # 显示内容预览
    print(f"\n📝 内容预览 (前500字):")
    print("-" * 80)
    print(content[:500])
    if len(content) > 500:
        print("...")
    print("-" * 80)

    # 解析 metadata 查看生成信息
    if metadata:
        try:
            meta = json.loads(metadata)
            if "iterations" in meta:
                print(f"\n📊 生成信息:")
                print(f"  迭代次数: {meta.get('iterations', 'N/A')}")
                print(f"  最终评分: {meta.get('final_score', 'N/A')}")
                print(f"  总耗时: {meta.get('total_time_seconds', 'N/A')} 秒")
        except:
            pass

conn.close()

print("\n" + "=" * 80)
print(f"✅ 预览完成，共检查 {len(chapters)} 章")
