#!/usr/bin/env python3
"""
自动修复格式错误的章节

支持修复：
1. 纯 JSON 格式 - 提取 full_content
2. Planner 格式 - 标记为需要重新生成
3. Markdown 代码块 - 移除包裹标记

使用方法：
  python3 fix_broken_chapters.py [数据库路径] [章节ID...]

示例：
  python3 fix_broken_chapters.py                    # 自动修复所有问题章节
  python3 fix_broken_chapters.py /path/db.db        # 指定数据库
  python3 fix_broken_chapters.py /path/db.db 1 2 3  # 修复指定章节ID
  python3 fix_broken_chapters.py --dry-run          # 预览模式，不实际修改
"""

import sqlite3
import sys
import json
import re
from pathlib import Path
from datetime import datetime

def find_database():
    """自动查找数据库"""
    candidates = ["backend/storage/arboris.db", "storage/arboris.db", "arboris.db"]
    for candidate in candidates:
        db_file = Path.cwd() / candidate
        if db_file.exists():
            return str(db_file)
    return None

def extract_from_json(content):
    """从 JSON 中提取 full_content"""
    try:
        data = json.loads(content)

        # 尝试多种字段名
        for key in ['full_content', 'content', 'text', 'chapter_content', 'body']:
            if key in data and isinstance(data[key], str) and len(data[key]) > 100:
                return data[key], f"json_field_{key}"

        # 尝试嵌套
        for key, value in data.items():
            if isinstance(value, dict):
                for sub_key in ['full_content', 'content', 'text']:
                    if sub_key in value and isinstance(value[sub_key], str) and len(value[sub_key]) > 100:
                        return value[sub_key], f"json_nested_{key}.{sub_key}"

        return None, None
    except:
        return None, None

def extract_from_markdown(content):
    """从 Markdown 代码块中提取内容"""
    # 移除 ```json ... ``` 或 ``` ... ```
    patterns = [
        r'^```json\s*\n(.*)\n```$',
        r'^```\s*\n(.*)\n```$',
        r'^```json\s*(.*?)```$',
        r'^```(.*?)```$',
    ]

    for pattern in patterns:
        match = re.match(pattern, content.strip(), re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            if len(extracted) > 100:
                return extracted, "markdown_block"

    return None, None

def detect_issue(content):
    """检测章节问题"""
    content_stripped = content.strip()

    # 1. 检查纯 JSON
    if content_stripped.startswith("{") and content_stripped.endswith("}"):
        try:
            json.loads(content)
            return "json", "纯JSON格式"
        except:
            pass

    # 2. 检查 Markdown 代码块
    if content_stripped.startswith("```"):
        return "markdown", "Markdown代码块"

    # 3. 检查 Planner 格式
    planner_keywords = ["analysis:", "plan:", "queries_summary:", "notes_for_writer:"]
    content_preview = content[:500] if len(content) >= 500 else content
    if any(kw in content_preview for kw in planner_keywords):
        return "planner", "Planner格式"

    # 4. 检查字数
    if len(content) < 500:
        return "short", f"字数过少({len(content)}字)"

    return None, None

def fix_chapter(cursor, conn, chapter_id, content, dry_run=False):
    """尝试修复单个章节"""
    issue_type, issue_desc = detect_issue(content)

    if not issue_type:
        return False, "无问题"

    fixed_content = None
    fix_method = None

    # 尝试修复
    if issue_type == "json":
        fixed_content, fix_method = extract_from_json(content)
    elif issue_type == "markdown":
        fixed_content, fix_method = extract_from_markdown(content)
        # 如果提取后还是 JSON，继续提取
        if fixed_content:
            nested_issue, _ = detect_issue(fixed_content)
            if nested_issue == "json":
                nested_fixed, nested_method = extract_from_json(fixed_content)
                if nested_fixed:
                    fixed_content = nested_fixed
                    fix_method = f"{fix_method} -> {nested_method}"
    elif issue_type == "planner":
        return False, "Planner格式无法自动修复，需要重新生成"
    elif issue_type == "short":
        return False, "字数过少无法自动修复，需要重新生成"

    if not fixed_content:
        return False, f"无法修复: {issue_desc}"

    # 验证修复后的内容
    new_issue, _ = detect_issue(fixed_content)
    if new_issue:
        return False, f"修复后仍有问题: {new_issue}"

    if dry_run:
        return True, f"可修复 ({fix_method}) [预览模式]"

    # 更新数据库
    try:
        cursor.execute("""
            SELECT selected_version_id FROM chapters WHERE id = ?
        """, (chapter_id,))
        version_id = cursor.fetchone()[0]

        cursor.execute("""
            UPDATE chapter_versions
            SET content = ?, updated_at = ?
            WHERE id = ?
        """, (fixed_content, datetime.utcnow().isoformat(), version_id))

        conn.commit()
        return True, f"已修复 ({fix_method})"
    except Exception as e:
        return False, f"更新失败: {e}"

# 解析参数
args = sys.argv[1:]
db_path = find_database()
chapter_ids = []
dry_run = False

# 解析参数
for arg in args:
    if arg == "--dry-run":
        dry_run = True
    elif arg.isdigit():
        chapter_ids.append(int(arg))
    elif not arg.startswith("-") and Path(arg).exists():
        db_path = arg

if not db_path:
    print("❌ 未找到数据库")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n" + "=" * 80)
print(f"🔧 自动修复章节工具 {'[预览模式]' if dry_run else '[修复模式]'}")
print("=" * 80)

# 查询章节
if chapter_ids:
    placeholders = ','.join('?' * len(chapter_ids))
    cursor.execute(f"""
        SELECT c.id, c.chapter_number, p.title, cv.content
        FROM chapters c
        JOIN chapter_versions cv ON c.selected_version_id = cv.id
        JOIN novel_projects p ON c.project_id = p.id
        WHERE c.id IN ({placeholders})
        ORDER BY c.chapter_number
    """, chapter_ids)
else:
    # 查询所有章节，筛选有问题的
    cursor.execute("""
        SELECT c.id, c.chapter_number, p.title, cv.content
        FROM chapters c
        JOIN chapter_versions cv ON c.selected_version_id = cv.id
        JOIN novel_projects p ON c.project_id = p.id
        ORDER BY c.chapter_number
    """)

chapters = cursor.fetchall()

if not chapters:
    print("\n❌ 未找到章节")
    conn.close()
    sys.exit(1)

print(f"\n检查 {len(chapters)} 个章节...")

# 筛选有问题的章节
problematic = []
for chapter_id, chapter_num, project_title, content in chapters:
    issue_type, issue_desc = detect_issue(content)
    if issue_type:
        problematic.append((chapter_id, chapter_num, project_title, content, issue_type, issue_desc))

if not problematic:
    print("\n✅ 所有章节格式正常，无需修复")
    conn.close()
    sys.exit(0)

print(f"\n找到 {len(problematic)} 个有问题的章节")
print()

# 修复章节
fixed_count = 0
failed_count = 0
skipped_count = 0

for chapter_id, chapter_num, project_title, content, issue_type, issue_desc in problematic:
    print(f"第 {chapter_num} 章 - {project_title}")
    print(f"  问题: {issue_desc}")
    print(f"  字数: {len(content)}")

    success, message = fix_chapter(cursor, conn, chapter_id, content, dry_run)

    if success:
        print(f"  ✅ {message}")
        fixed_count += 1
    else:
        print(f"  ❌ {message}")
        if "无法自动修复" in message or "需要重新生成" in message:
            skipped_count += 1
        else:
            failed_count += 1

    print()

# 统计
print("=" * 80)
print("📊 修复统计")
print("=" * 80)
print(f"总问题章节: {len(problematic)}")
print(f"已修复:     {fixed_count}")
print(f"修复失败:   {failed_count}")
print(f"需重新生成: {skipped_count}")

if dry_run and fixed_count > 0:
    print("\n" + "=" * 80)
    print("💡 提示")
    print("=" * 80)
    print("这是预览模式，没有实际修改数据库")
    print("如需应用修复，去掉 --dry-run 参数重新运行")

if skipped_count > 0:
    print("\n" + "=" * 80)
    print("💡 需要重新生成的章节")
    print("=" * 80)
    print("以下章节无法自动修复，建议重新生成：")
    for chapter_id, chapter_num, project_title, content, issue_type, issue_desc in problematic:
        if issue_type in ["planner", "short"]:
            print(f"  • 第 {chapter_num} 章 ({issue_desc})")

conn.close()

print("\n" + "=" * 80)
print("✅ 完成")
print("=" * 80 + "\n")
