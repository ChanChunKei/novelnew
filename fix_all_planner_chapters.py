#!/usr/bin/env python3
"""
修复所有 Planner 格式的章节

自动检测包含 Planner 格式的章节，并尝试提取 full_content
如果无法提取，则标记为需要重新生成

使用方法：
  python3 fix_all_planner_chapters.py [数据库路径]
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

def is_planner_format(content):
    """检测是否是 Planner 格式（更准确的检测）"""
    if not content:
        return False

    content_stripped = content.strip()

    # 检查是否以 Markdown 代码块开头
    if content_stripped.startswith('`'):
        # 移除 Markdown 包裹
        if content_stripped.startswith('```json'):
            content_stripped = content_stripped[7:]
        elif content_stripped.startswith('```'):
            content_stripped = content_stripped[3:]

        if content_stripped.endswith('```'):
            content_stripped = content_stripped[:-3]
        content_stripped = content_stripped.strip()

    # 检查是否是 JSON
    if not (content_stripped.startswith('{') and content_stripped.endswith('}')):
        return False

    try:
        data = json.loads(content_stripped)

        # 检查是否包含 Planner 的典型字段
        planner_fields = ['analysis', 'plan', 'queries_summary', 'notes_for_writer']
        has_planner_fields = sum(1 for field in planner_fields if field in data)

        # 如果有3个或以上 Planner 字段，认为是 Planner 格式
        if has_planner_fields >= 3:
            return True

        # 或者有 analysis 和 plan 这两个核心字段
        if 'analysis' in data and 'plan' in data:
            return True

    except:
        pass

    return False

def extract_content(content):
    """尝试从各种格式中提取正文内容"""
    if not content:
        return None, None

    content_stripped = content.strip()

    # 移除 Markdown 代码块
    if content_stripped.startswith('`'):
        if content_stripped.startswith('```json'):
            content_stripped = content_stripped[7:]
        elif content_stripped.startswith('```'):
            content_stripped = content_stripped[3:]

        if content_stripped.endswith('```'):
            content_stripped = content_stripped[:-3]
        content_stripped = content_stripped.strip()

    # 尝试解析 JSON
    if content_stripped.startswith('{') and content_stripped.endswith('}'):
        try:
            data = json.loads(content_stripped)

            # 尝试提取 full_content
            if 'full_content' in data:
                return data['full_content'], 'json.full_content'

            # 尝试其他可能的字段
            for field in ['content', 'text', 'chapter_content', 'body']:
                if field in data and isinstance(data[field], str) and len(data[field]) > 100:
                    return data[field], f'json.{field}'

            return None, 'json_no_content_field'
        except:
            pass

    return None, None

# 主程序
db_path = sys.argv[1] if len(sys.argv) > 1 else find_database()

if not db_path:
    print("❌ 未找到数据库")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n" + "=" * 80)
print("🔧 修复 Planner 格式章节")
print("=" * 80)

# 查询所有章节
cursor.execute("""
SELECT c.id, c.chapter_number, p.title, cv.id as version_id, cv.content
FROM chapters c
JOIN chapter_versions cv ON c.selected_version_id = cv.id
JOIN novel_projects p ON c.project_id = p.id
ORDER BY c.id
""")

all_chapters = cursor.fetchall()

print(f"\n扫描 {len(all_chapters)} 个章节...")

# 找出 Planner 格式的章节
planner_chapters = []
for chapter_id, chapter_num, project_title, version_id, content in all_chapters:
    if is_planner_format(content):
        extracted, method = extract_content(content)
        planner_chapters.append({
            'chapter_id': chapter_id,
            'chapter_num': chapter_num,
            'project_title': project_title,
            'version_id': version_id,
            'content': content,
            'extracted': extracted,
            'method': method
        })

if not planner_chapters:
    print("\n✅ 未找到 Planner 格式的章节")
    conn.close()
    sys.exit(0)

print(f"\n找到 {len(planner_chapters)} 个 Planner 格式章节\n")

# 分类统计
can_fix = []
need_regenerate = []

for chapter in planner_chapters:
    if chapter['extracted']:
        can_fix.append(chapter)
    else:
        need_regenerate.append(chapter)

print(f"📊 统计:")
print(f"  可自动修复: {len(can_fix)} 章")
print(f"  需要重新生成: {len(need_regenerate)} 章")

# 显示详情
if can_fix:
    print(f"\n" + "=" * 80)
    print(f"✅ 可自动修复的章节（{len(can_fix)} 章）")
    print("=" * 80)

    for ch in can_fix:
        print(f"\n第 {ch['chapter_num']} 章 - {ch['project_title']}")
        print(f"  章节ID: {ch['chapter_id']}")
        print(f"  提取方法: {ch['method']}")
        print(f"  原始长度: {len(ch['content'])} → 提取后: {len(ch['extracted'])}")
        print(f"  内容预览: {ch['extracted'][:100]}...")

if need_regenerate:
    print(f"\n" + "=" * 80)
    print(f"❌ 需要重新生成的章节（{len(need_regenerate)} 章）")
    print("=" * 80)

    for ch in need_regenerate:
        print(f"\n第 {ch['chapter_num']} 章 - {ch['project_title']}")
        print(f"  章节ID: {ch['chapter_id']}")
        print(f"  原因: {ch['method'] or '无法提取内容'}")
        print(f"  原始内容前200字: {ch['content'][:200]}...")

# 询问是否执行修复
if can_fix:
    print(f"\n" + "=" * 80)
    response = input(f"\n是否修复 {len(can_fix)} 个可自动修复的章节？(yes/no): ").strip().lower()

    if response == 'yes':
        fixed_count = 0
        for ch in can_fix:
            try:
                cursor.execute("""
                    UPDATE chapter_versions
                    SET content = ?, updated_at = ?
                    WHERE id = ?
                """, (ch['extracted'], datetime.utcnow().isoformat(), ch['version_id']))

                conn.commit()
                fixed_count += 1
                print(f"✅ 已修复: 第 {ch['chapter_num']} 章")
            except Exception as e:
                print(f"❌ 修复失败: 第 {ch['chapter_num']} 章 - {e}")

        print(f"\n✅ 成功修复 {fixed_count}/{len(can_fix)} 章")
    else:
        print("\n⏭️  跳过修复")

conn.close()

print("\n" + "=" * 80)
print("✅ 完成")
print("=" * 80)

if need_regenerate:
    print(f"\n💡 提示: 有 {len(need_regenerate)} 章需要重新生成")
    print("这些章节无法自动修复，建议删除后重新生成")
    print("\n章节ID列表:")
    print(", ".join(str(ch['chapter_id']) for ch in need_regenerate))

print()
