#!/usr/bin/env python3
"""
批量检查所有章节的格式问题

使用方法：
  python3 batch_check_all_chapters.py [数据库路径]

示例：
  python3 batch_check_all_chapters.py                     # 自动检测
  python3 batch_check_all_chapters.py /path/to/db.db    # 指定路径
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

if not db_path:
    print("❌ 未找到数据库")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查询所有章节
cursor.execute("""
SELECT c.id, c.chapter_number, p.title, cv.content, cv.created_at
FROM chapters c
JOIN chapter_versions cv ON c.selected_version_id = cv.id
JOIN novel_projects p ON c.project_id = p.id
ORDER BY p.id, c.chapter_number
""")

chapters = cursor.fetchall()

if not chapters:
    print("❌ 未找到任何章节")
    sys.exit(1)

print("\n" + "=" * 80)
print(f"🔍 批量检查所有章节（共 {len(chapters)} 章）")
print("=" * 80)

# 统计信息
total_chapters = len(chapters)
issues_found = 0
json_format_count = 0
planner_format_count = 0
markdown_marker_count = 0
low_word_count = 0

# 问题章节列表
problematic_chapters = []

for chapter_id, chapter_num, project_title, content, created in chapters:
    issues = []
    warnings = []

    # 检查内容类型
    if content.strip().startswith("{") and content.strip().endswith("}"):
        try:
            parsed = json.loads(content)
            issues.append("纯JSON格式")
            json_format_count += 1
        except:
            pass

    # 检查 Planner 关键词
    planner_keywords = [
        "analysis:", "plan:", "queries_summary:", "notes_for_writer:",
        '"analysis":', '"plan":'
    ]

    found_planner = []
    for kw in planner_keywords:
        if kw in content[:1000]:
            found_planner.append(kw)

    if found_planner:
        issues.append(f"包含Planner格式 ({', '.join(found_planner)})")
        planner_format_count += 1

    # 检查 Markdown 标记
    if "```json" in content[:200] or "```" in content[:200]:
        warnings.append("Markdown代码块")
        markdown_marker_count += 1

    # 检查字数
    word_count = len(content)
    if word_count < 500:
        warnings.append(f"字数过少({word_count})")
        low_word_count += 1

    # 如果有问题，记录下来
    if issues or warnings:
        issues_found += 1
        problematic_chapters.append({
            'id': chapter_id,
            'chapter_num': chapter_num,
            'project': project_title,
            'issues': issues,
            'warnings': warnings,
            'word_count': word_count,
            'created': created
        })

# ==================== 显示结果 ====================
print("\n📊 检查统计")
print("-" * 80)
print(f"总章节数:        {total_chapters}")
print(f"有问题的章节:    {issues_found}")
print(f"  - 纯JSON格式:   {json_format_count}")
print(f"  - Planner格式:  {planner_format_count}")
print(f"  - Markdown标记: {markdown_marker_count}")
print(f"  - 字数过少:     {low_word_count}")
print(f"正常章节:        {total_chapters - issues_found}")

if problematic_chapters:
    print("\n" + "=" * 80)
    print("🚨 问题章节详情")
    print("=" * 80)

    for item in problematic_chapters:
        print(f"\n第 {item['chapter_num']} 章 - {item['project']}")
        print(f"  ID: {item['id']}")
        print(f"  创建时间: {item['created']}")
        print(f"  字数: {item['word_count']}")

        if item['issues']:
            print(f"  ❌ 严重问题:")
            for issue in item['issues']:
                print(f"     • {issue}")

        if item['warnings']:
            print(f"  ⚠️  警告:")
            for warning in item['warnings']:
                print(f"     • {warning}")
else:
    print("\n✅ 所有章节格式正常！")

# ==================== 建议 ====================
if problematic_chapters:
    print("\n" + "=" * 80)
    print("💡 修复建议")
    print("=" * 80)

    if json_format_count > 0:
        print(f"\n📋 {json_format_count} 个章节是纯JSON格式：")
        print("  解决方案：")
        print("    1. 使用 extract_full_content.py 脚本提取 full_content")
        print("    2. 或使用 fix_broken_chapters.py 自动修复")

    if planner_format_count > 0:
        print(f"\n📋 {planner_format_count} 个章节包含Planner格式：")
        print("  解决方案：")
        print("    1. 重新生成这些章节")
        print("    2. 检查 Writer 的 prompt 设置")
        print("    3. 考虑使用更好的模型")

    if low_word_count > 0:
        print(f"\n📋 {low_word_count} 个章节字数过少：")
        print("  解决方案：")
        print("    1. 检查生成过程是否被中断")
        print("    2. 重新生成这些章节")

    print("\n🔧 批量修复命令：")
    chapter_ids = [str(item['id']) for item in problematic_chapters]
    print(f"  python3 fix_broken_chapters.py {db_path} {' '.join(chapter_ids)}")

conn.close()

print("\n" + "=" * 80)
print("✅ 批量检查完成")
print("=" * 80 + "\n")
