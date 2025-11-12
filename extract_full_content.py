#!/usr/bin/env python3
"""
从 JSON 格式的章节中提取 full_content

当 Writer 返回纯 JSON 格式时，这个脚本会尝试提取 full_content 字段并更新到数据库

使用方法：
  python3 extract_full_content.py [数据库路径] [章节ID]

示例：
  python3 extract_full_content.py                         # 自动修复所有JSON章节
  python3 extract_full_content.py /path/db.db             # 指定数据库
  python3 extract_full_content.py /path/db.db 123         # 修复指定章节
"""

import sqlite3
import sys
import json
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

def extract_content_from_json(content_str):
    """尝试从各种 JSON 格式中提取 full_content"""
    try:
        data = json.loads(content_str)

        # 尝试多种可能的字段名
        possible_keys = [
            'full_content',
            'content',
            'text',
            'chapter_content',
            'body',
            'story',
            'narrative'
        ]

        for key in possible_keys:
            if key in data:
                extracted = data[key]
                if isinstance(extracted, str) and len(extracted) > 100:
                    return extracted, key

        # 如果是嵌套的，尝试深入查找
        for key, value in data.items():
            if isinstance(value, dict):
                for sub_key in possible_keys:
                    if sub_key in value:
                        extracted = value[sub_key]
                        if isinstance(extracted, str) and len(extracted) > 100:
                            return extracted, f"{key}.{sub_key}"

        return None, None
    except json.JSONDecodeError:
        return None, None

def fix_chapter(cursor, conn, chapter_id, chapter_num, project_title, content):
    """修复单个章节"""
    print(f"\n{'='*60}")
    print(f"修复第 {chapter_num} 章 - {project_title}")
    print(f"章节ID: {chapter_id}")
    print(f"{'='*60}")

    # 显示原始内容预览
    print(f"\n原始内容前200字:")
    print("-" * 60)
    print(content[:200])
    print("...")

    # 尝试提取
    extracted, found_key = extract_content_from_json(content)

    if not extracted:
        print("\n❌ 无法提取 full_content（未找到有效字段）")
        return False

    print(f"\n✅ 成功提取！使用字段: {found_key}")
    print(f"提取内容长度: {len(extracted)} 字")
    print(f"\n提取内容前300字:")
    print("-" * 60)
    print(extracted[:300])
    print("...")

    # 询问是否更新
    response = input("\n是否更新到数据库？(y/n，默认n): ").strip().lower()

    if response == 'y':
        # 获取当前版本信息
        cursor.execute("""
            SELECT selected_version_id FROM chapters WHERE id = ?
        """, (chapter_id,))
        version_id = cursor.fetchone()[0]

        # 更新版本内容
        cursor.execute("""
            UPDATE chapter_versions
            SET content = ?, updated_at = ?
            WHERE id = ?
        """, (extracted, datetime.utcnow().isoformat(), version_id))

        conn.commit()
        print("✅ 已更新到数据库")
        return True
    else:
        print("⏭️  跳过更新")
        return False

# 解析参数
db_path = sys.argv[1] if len(sys.argv) > 1 else find_database()
specific_chapter_id = int(sys.argv[2]) if len(sys.argv) > 2 else None

if not db_path:
    print("❌ 未找到数据库")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n" + "=" * 80)
print("🔧 提取 full_content 工具")
print("=" * 80)

# 查询需要修复的章节
if specific_chapter_id:
    cursor.execute("""
        SELECT c.id, c.chapter_number, p.title, cv.content
        FROM chapters c
        JOIN chapter_versions cv ON c.selected_version_id = cv.id
        JOIN novel_projects p ON c.project_id = p.id
        WHERE c.id = ?
    """, (specific_chapter_id,))
else:
    # 查找所有 JSON 格式的章节
    cursor.execute("""
        SELECT c.id, c.chapter_number, p.title, cv.content
        FROM chapters c
        JOIN chapter_versions cv ON c.selected_version_id = cv.id
        JOIN novel_projects p ON c.project_id = p.id
        ORDER BY c.chapter_number
    """)

chapters = cursor.fetchall()

if not chapters:
    print("\n❌ 未找到符合条件的章节")
    conn.close()
    sys.exit(1)

# 筛选出 JSON 格式的章节
json_chapters = []
for chapter_id, chapter_num, project_title, content in chapters:
    content = content.strip()
    if content.startswith("{") and content.endswith("}"):
        try:
            json.loads(content)
            json_chapters.append((chapter_id, chapter_num, project_title, content))
        except:
            pass

if not json_chapters:
    print("\n✅ 未找到纯 JSON 格式的章节")
    conn.close()
    sys.exit(0)

print(f"\n找到 {len(json_chapters)} 个 JSON 格式的章节")

# 修复章节
fixed_count = 0
skipped_count = 0

for chapter_data in json_chapters:
    success = fix_chapter(cursor, conn, *chapter_data)
    if success:
        fixed_count += 1
    else:
        skipped_count += 1

    # 如果不是最后一个，添加分隔符
    if chapter_data != json_chapters[-1]:
        print("\n" + "~" * 80 + "\n")

# 显示统计
print("\n" + "=" * 80)
print("📊 修复统计")
print("=" * 80)
print(f"总计: {len(json_chapters)} 章")
print(f"已修复: {fixed_count} 章")
print(f"跳过: {skipped_count} 章")

conn.close()

print("\n" + "=" * 80)
print("✅ 完成")
print("=" * 80 + "\n")
