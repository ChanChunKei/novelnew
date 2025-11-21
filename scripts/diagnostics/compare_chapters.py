#!/usr/bin/env python3
"""
对比多个章节的生成质量

对比不同章节的：
- 迭代次数
- 评分
- Writer 输出格式
- 最终内容质量

使用方法：
  python3 compare_chapters.py [数据库路径] [章节号1] [章节号2] ...

示例：
  python3 compare_chapters.py 1 2 3               # 对比第1,2,3章
  python3 compare_chapters.py /path/db.db 1 2    # 指定数据库
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

def analyze_chapter_quality(content, metadata):
    """分析章节质量"""
    quality = {
        'word_count': len(content),
        'has_issues': False,
        'issues': [],
        'iterations': 0,
        'final_score': 0,
        'writer_format': 'unknown',
        'total_time': 0,
    }

    # 检查内容格式
    if content.strip().startswith("{") and content.strip().endswith("}"):
        try:
            json.loads(content)
            quality['has_issues'] = True
            quality['issues'].append("纯JSON格式")
        except:
            pass

    if content:
        planner_keywords = ["analysis:", "plan:", "queries_summary:", "notes_for_writer:"]
        content_preview = content[:500] if len(content) >= 500 else content
        if any(kw in content_preview for kw in planner_keywords):
            quality['has_issues'] = True
            quality['issues'].append("Planner格式")

    if not content or len(content) < 500:
        quality['has_issues'] = True
        quality['issues'].append("字数过少")

    # 解析 metadata
    if metadata:
        try:
            meta = json.loads(metadata)
            quality['iterations'] = meta.get('iterations', 0)
            quality['final_score'] = meta.get('final_score', 0)
            quality['total_time'] = meta.get('total_time_seconds', 0)

            # 分析 Writer 格式
            if 'conversation_history' in meta:
                history = meta['conversation_history']
                for item in history:
                    if item.get('agent') == 'writer':
                        content_data = item.get('content', {})
                        if isinstance(content_data, dict):
                            if 'full_content' in content_data:
                                quality['writer_format'] = 'dict_with_full_content'
                            else:
                                quality['writer_format'] = 'dict_without_full_content'
                        elif isinstance(content_data, str):
                            quality['writer_format'] = 'string'
                        break
        except:
            pass

    return quality

# 解析参数
args = sys.argv[1:]
db_path = find_database()
chapter_numbers = []

# 判断第一个参数是否是数据库路径
if args and not args[0].isdigit():
    db_path = args[0]
    chapter_numbers = [int(x) for x in args[1:] if x.isdigit()]
else:
    chapter_numbers = [int(x) for x in args if x.isdigit()]

if not db_path:
    print("❌ 未找到数据库")
    sys.exit(1)

if not chapter_numbers:
    print("❌ 请指定要对比的章节号")
    print("\n使用方法：")
    print("  python3 compare_chapters.py 1 2 3")
    print("  python3 compare_chapters.py /path/db.db 1 2 3")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n" + "=" * 80)
print(f"📊 对比章节质量（共 {len(chapter_numbers)} 章）")
print("=" * 80)

# 查询章节数据
chapters_data = []
for chapter_num in chapter_numbers:
    cursor.execute("""
    SELECT c.chapter_number, p.title, cv.content, cv.metadata, cv.created_at
    FROM chapters c
    JOIN chapter_versions cv ON c.selected_version_id = cv.id
    JOIN novel_projects p ON c.project_id = p.id
    WHERE c.chapter_number = ?
    ORDER BY cv.created_at DESC
    LIMIT 1
    """, (chapter_num,))

    result = cursor.fetchone()
    if result:
        chapters_data.append(result)
    else:
        print(f"⚠️  未找到第 {chapter_num} 章")

if not chapters_data:
    print("❌ 未找到任何章节")
    conn.close()
    sys.exit(1)

# 分析每个章节
print(f"\n找到 {len(chapters_data)} 个章节")
print()

results = []
for chapter_num, project_title, content, metadata, created in chapters_data:
    quality = analyze_chapter_quality(content, metadata)
    results.append({
        'chapter_num': chapter_num,
        'project': project_title,
        'created': created,
        'quality': quality
    })

# ==================== 显示对比表格 ====================
print("=" * 100)
print(f"{'章节':<6} {'字数':<8} {'迭代':<6} {'评分':<6} {'耗时(s)':<10} {'Writer格式':<25} {'问题'}")
print("=" * 100)

for result in results:
    q = result['quality']
    issues_str = ", ".join(q['issues']) if q['issues'] else "✅"

    # 根据问题添加标记
    marker = "❌" if q['has_issues'] else "✅"

    print(f"{marker} 第{result['chapter_num']:<3} {q['word_count']:<8} {q['iterations']:<6} "
          f"{q['final_score']:<6.1f} {q['total_time']:<10.1f} {q['writer_format']:<25} {issues_str}")

print("=" * 100)

# ==================== 统计分析 ====================
print("\n📈 统计分析")
print("-" * 80)

total = len(results)
has_issues = sum(1 for r in results if r['quality']['has_issues'])
avg_iterations = sum(r['quality']['iterations'] for r in results) / total if total > 0 else 0
avg_score = sum(r['quality']['final_score'] for r in results) / total if total > 0 else 0
avg_time = sum(r['quality']['total_time'] for r in results) / total if total > 0 else 0

print(f"总章节数:      {total}")
print(f"有问题章节:    {has_issues} ({has_issues/total*100:.1f}%)")
print(f"正常章节:      {total - has_issues} ({(total-has_issues)/total*100:.1f}%)")
print(f"\n平均迭代次数:  {avg_iterations:.1f}")
print(f"平均评分:      {avg_score:.1f}")
print(f"平均耗时:      {avg_time:.1f} 秒")

# Writer 格式统计
writer_formats = {}
for r in results:
    fmt = r['quality']['writer_format']
    writer_formats[fmt] = writer_formats.get(fmt, 0) + 1

print(f"\nWriter 格式分布:")
for fmt, count in writer_formats.items():
    print(f"  {fmt}: {count} ({count/total*100:.1f}%)")

# ==================== 详细对比 ====================
print("\n" + "=" * 80)
print("📋 详细对比")
print("=" * 80)

for result in results:
    q = result['quality']
    print(f"\n第 {result['chapter_num']} 章 - {result['project']}")
    print(f"  创建时间: {result['created']}")
    print(f"  字数: {q['word_count']}")
    print(f"  迭代次数: {q['iterations']}")
    print(f"  最终评分: {q['final_score']}")
    print(f"  生成耗时: {q['total_time']:.1f} 秒")
    print(f"  Writer格式: {q['writer_format']}")

    if q['issues']:
        print(f"  ❌ 问题:")
        for issue in q['issues']:
            print(f"     • {issue}")
    else:
        print(f"  ✅ 无问题")

# ==================== 建议 ====================
if has_issues > 0:
    print("\n" + "=" * 80)
    print("💡 改进建议")
    print("=" * 80)

    # 找出问题模式
    json_issues = sum(1 for r in results if "纯JSON格式" in r['quality']['issues'])
    planner_issues = sum(1 for r in results if "Planner格式" in r['quality']['issues'])

    if json_issues > 0:
        print(f"\n{json_issues} 章有 JSON 格式问题：")
        print("  • 使用 extract_full_content.py 提取正确内容")
        print("  • 检查内容提取逻辑是否正确")

    if planner_issues > 0:
        print(f"\n{planner_issues} 章有 Planner 格式问题：")
        print("  • 检查 Writer 的 prompt 设置")
        print("  • 考虑使用更好的模型")
        print("  • 重新生成这些章节")

    # 检查是否有模式
    if writer_formats.get('dict_without_full_content', 0) > 0:
        print(f"\n⚠️  发现 Writer 返回的 dict 缺少 full_content 字段")
        print("  这是导致问题的根本原因！")
        print("  建议：")
        print("    1. 检查 Writer 的 system prompt")
        print("    2. 确保明确要求返回 full_content 字段")
        print("    3. 在后端添加更严格的验证")

conn.close()

print("\n" + "=" * 80)
print("✅ 对比完成")
print("=" * 80 + "\n")
