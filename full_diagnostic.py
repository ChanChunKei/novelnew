#!/usr/bin/env python3
"""
完整诊断报告 - 一键运行所有检查

使用方法：
  python3 full_diagnostic.py [数据库路径]

示例：
  python3 full_diagnostic.py                    # 自动检测
  python3 full_diagnostic.py /path/to/db.db    # 指定数据库
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

def print_section(title, level=1):
    """打印章节标题"""
    if level == 1:
        print("\n" + "=" * 80)
        print(f"📋 {title}")
        print("=" * 80)
    elif level == 2:
        print("\n" + "-" * 80)
        print(f"🔍 {title}")
        print("-" * 80)
    else:
        print(f"\n💡 {title}")

def check_gemini_config(cursor):
    """检查 Gemini 配置"""
    print_section("1. Gemini RAG 配置检查", level=1)

    cursor.execute("""
        SELECT key, value
        FROM system_configs
        WHERE key IN ('gemini.api_key', 'rag.provider')
    """)

    configs = dict(cursor.fetchall())

    api_key = configs.get('gemini.api_key', '')
    provider = configs.get('rag.provider', '')

    print(f"\n配置状态:")
    print(f"  RAG Provider: {provider if provider else '❌ 未配置'}")

    if api_key:
        print(f"  Gemini API Key: {api_key[:10]}...{api_key[-4:]} ✅")
        config_ok = True
    else:
        print(f"  Gemini API Key: ❌ 未配置")
        config_ok = False

    if provider == 'gemini' and api_key:
        print(f"\n✅ Gemini RAG 已正确配置")
        return True
    else:
        print(f"\n⚠️  Gemini RAG 未启用或配置不完整")
        return False

def check_projects(cursor):
    """检查项目状态"""
    print_section("2. 项目状态检查", level=1)

    cursor.execute("""
        SELECT
            p.id,
            p.title,
            p.status,
            COUNT(DISTINCT c.id) as chapter_count
        FROM novel_projects p
        LEFT JOIN chapters c ON p.id = c.project_id
        GROUP BY p.id
        ORDER BY p.created_at DESC
        LIMIT 10
    """)

    projects = cursor.fetchall()

    if not projects:
        print("\n📭 暂无项目")
        return 0

    print(f"\n找到 {len(projects)} 个项目：\n")

    for pid, title, status, chapter_count in projects:
        corpus_name = f"novel-project-{pid}"
        print(f"📖 {title}")
        print(f"   ID: {pid}, 状态: {status}, 章节数: {chapter_count}")
        print(f"   Corpus: {corpus_name}")

    return len(projects)

def check_all_chapters(cursor):
    """批量检查所有章节"""
    print_section("3. 章节格式批量检查", level=1)

    cursor.execute("""
    SELECT c.id, c.chapter_number, p.title, cv.content, cv.metadata
    FROM chapters c
    JOIN chapter_versions cv ON c.selected_version_id = cv.id
    JOIN novel_projects p ON c.project_id = p.id
    ORDER BY p.id, c.chapter_number
    """)

    chapters = cursor.fetchall()

    if not chapters:
        print("\n❌ 未找到任何章节")
        return None

    print(f"\n扫描 {len(chapters)} 个章节...")

    # 统计信息
    stats = {
        'total': len(chapters),
        'json_format': 0,
        'planner_format': 0,
        'markdown': 0,
        'short': 0,
        'normal': 0,
        'avg_iterations': 0,
        'avg_score': 0,
        'avg_word_count': 0,
    }

    problematic = []
    total_iterations = 0
    total_score = 0
    total_words = 0
    score_count = 0

    for chapter_id, chapter_num, project_title, content, metadata in chapters:
        issues = []

        # 检查格式
        if content.strip().startswith("{") and content.strip().endswith("}"):
            try:
                json.loads(content)
                issues.append("纯JSON")
                stats['json_format'] += 1
            except:
                pass

        if content:
            planner_keywords = ["analysis:", "plan:", "queries_summary:", "notes_for_writer:"]
            content_preview = content[:500] if len(content) >= 500 else content
            if any(kw in content_preview for kw in planner_keywords):
                issues.append("Planner格式")
                stats['planner_format'] += 1

            content_head = content[:200] if len(content) >= 200 else content
            if "```" in content_head:
                issues.append("Markdown标记")
                stats['markdown'] += 1

        word_count = len(content) if content else 0
        total_words += word_count

        if word_count < 500:
            issues.append(f"字数少({word_count})")
            stats['short'] += 1

        # 解析 metadata
        if metadata:
            try:
                meta = json.loads(metadata)
                iterations = meta.get('iterations', 0)
                score = meta.get('final_score', 0)
                total_iterations += iterations
                if score > 0:
                    total_score += score
                    score_count += 1
            except:
                pass

        if issues:
            problematic.append({
                'chapter_num': chapter_num,
                'project': project_title,
                'issues': issues,
                'word_count': word_count
            })
        else:
            stats['normal'] += 1

    # 计算平均值
    stats['avg_iterations'] = total_iterations / stats['total'] if stats['total'] > 0 else 0
    stats['avg_score'] = total_score / score_count if score_count > 0 else 0
    stats['avg_word_count'] = total_words / stats['total'] if stats['total'] > 0 else 0

    # 显示统计
    print(f"\n📊 统计结果:")
    print(f"  总章节数:    {stats['total']}")
    print(f"  正常章节:    {stats['normal']} ({stats['normal']/stats['total']*100:.1f}%)")
    print(f"  问题章节:    {len(problematic)} ({len(problematic)/stats['total']*100:.1f}%)")
    print(f"    - JSON格式:   {stats['json_format']}")
    print(f"    - Planner:    {stats['planner_format']}")
    print(f"    - Markdown:   {stats['markdown']}")
    print(f"    - 字数少:     {stats['short']}")
    print(f"\n  平均迭代:    {stats['avg_iterations']:.1f} 次")
    print(f"  平均评分:    {stats['avg_score']:.1f}")
    print(f"  平均字数:    {stats['avg_word_count']:.0f}")

    if problematic:
        print(f"\n🚨 问题章节列表:")
        for item in problematic[:10]:  # 最多显示10个
            issues_str = ", ".join(item['issues'])
            print(f"  • 第 {item['chapter_num']} 章: {issues_str}")

        if len(problematic) > 10:
            print(f"  ... 还有 {len(problematic) - 10} 个问题章节")

    return stats

def check_recent_chapters(cursor):
    """检查最近章节"""
    print_section("4. 最近章节详细检查", level=1)

    cursor.execute("""
    SELECT c.chapter_number, p.title, cv.content, cv.metadata, cv.created_at
    FROM chapters c
    JOIN chapter_versions cv ON c.selected_version_id = cv.id
    JOIN novel_projects p ON c.project_id = p.id
    ORDER BY cv.created_at DESC
    LIMIT 3
    """)

    chapters = cursor.fetchall()

    if not chapters:
        print("\n📭 暂无章节")
        return

    print(f"\n最近 {len(chapters)} 章详情:\n")

    for chapter_num, project_title, content, metadata, created in chapters:
        print(f"📄 第 {chapter_num} 章 - {project_title}")
        print(f"   时间: {created}")

        # 格式检查
        issues = []
        if content:
            content_stripped = content.strip()
            if content_stripped.startswith("{") and content_stripped.endswith("}"):
                try:
                    json.loads(content)
                    issues.append("❌ 纯JSON")
                except:
                    pass

            content_preview = content[:500] if len(content) >= 500 else content
            if any(kw in content_preview for kw in ["analysis:", "plan:", "queries_summary:"]):
                issues.append("❌ Planner格式")

        word_count = len(content) if content else 0
        if word_count < 500:
            issues.append(f"⚠️  字数少({word_count})")

        # metadata 信息
        if metadata:
            try:
                meta = json.loads(metadata)
                iterations = meta.get('iterations', 0)
                score = meta.get('final_score', 0)
                time_sec = meta.get('total_time_seconds', 0)

                print(f"   迭代: {iterations}, 评分: {score:.1f}, 耗时: {time_sec:.1f}s")

                # 分析 Writer 格式
                if 'conversation_history' in meta:
                    history = meta['conversation_history']
                    for item in history:
                        if item.get('agent') == 'writer':
                            content_data = item.get('content', {})
                            if isinstance(content_data, dict):
                                if 'full_content' in content_data:
                                    print(f"   Writer: ✅ dict with full_content")
                                else:
                                    print(f"   Writer: ❌ dict without full_content")
                                    issues.append("❌ Writer缺少full_content")
                            else:
                                print(f"   Writer: string")
                            break
            except:
                pass

        if issues:
            print(f"   问题: {', '.join(issues)}")
        else:
            print(f"   ✅ 格式正常 ({word_count} 字)")

        print()

def generate_recommendations(config_ok, stats):
    """生成建议"""
    print_section("5. 诊断建议", level=1)

    recommendations = []

    # 配置建议
    if not config_ok:
        recommendations.append({
            'priority': '🔴 高',
            'category': '配置',
            'issue': 'Gemini RAG 未配置或未启用',
            'action': '运行: python3 insert_config.py'
        })

    # 章节问题建议
    if stats:
        if stats['json_format'] > 0:
            recommendations.append({
                'priority': '🟡 中',
                'category': '格式',
                'issue': f"{stats['json_format']} 章是纯JSON格式",
                'action': '运行: python3 fix_broken_chapters.py'
            })

        if stats['planner_format'] > 0:
            recommendations.append({
                'priority': '🔴 高',
                'category': '格式',
                'issue': f"{stats['planner_format']} 章包含Planner格式",
                'action': '需要重新生成这些章节，检查 Writer prompt'
            })

        if stats['short'] > 0:
            recommendations.append({
                'priority': '🟡 中',
                'category': '内容',
                'issue': f"{stats['short']} 章字数过少",
                'action': '建议重新生成'
            })

        if stats['avg_score'] < 7:
            recommendations.append({
                'priority': '🟡 中',
                'category': '质量',
                'issue': f"平均评分较低 ({stats['avg_score']:.1f})",
                'action': '考虑优化 Writer prompt 或使用更好的模型'
            })

        if stats['avg_iterations'] > 3:
            recommendations.append({
                'priority': '🟢 低',
                'category': '性能',
                'issue': f"平均迭代次数较多 ({stats['avg_iterations']:.1f})",
                'action': '考虑调整 Reviewer 标准或优化 Writer 初次生成质量'
            })

    if recommendations:
        print("\n发现以下问题：\n")

        for rec in recommendations:
            print(f"{rec['priority']} [{rec['category']}] {rec['issue']}")
            print(f"   解决方案: {rec['action']}")
            print()
    else:
        print("\n✅ 未发现明显问题！系统运行良好。")

    # 下一步建议
    print_section("下一步操作建议", level=3)

    if stats and (stats['json_format'] > 0 or stats['markdown'] > 0):
        print("\n1️⃣  修复可自动修复的问题:")
        print("   python3 fix_broken_chapters.py --dry-run  # 预览")
        print("   python3 fix_broken_chapters.py            # 执行")

    if stats and stats['planner_format'] > 0:
        print("\n2️⃣  分析 Planner 格式问题:")
        print("   python3 analyze_writer_output.py")
        print("   # 查看 Writer 为什么返回 Planner 格式")

    if stats and len([1 for k, v in stats.items() if 'format' in k and v > 0]) > 1:
        print("\n3️⃣  对比正常与问题章节:")
        print("   python3 compare_chapters.py 1 2 3 4 5")
        print("   # 找出规律")

    print("\n4️⃣  查看详细文档:")
    print("   cat DIAGNOSTIC_TOOLS.md")

# ==================== 主程序 ====================

db_path = sys.argv[1] if len(sys.argv) > 1 else find_database()

if not db_path:
    print("❌ 未找到数据库")
    print("\n使用方法:")
    print("  python3 full_diagnostic.py [数据库路径]")
    sys.exit(1)

print("\n" + "=" * 80)
print("🔍 3Agent 系统完整诊断报告")
print("=" * 80)
print(f"\n数据库: {db_path}")
print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 运行所有检查
config_ok = check_gemini_config(cursor)
project_count = check_projects(cursor)
stats = check_all_chapters(cursor)
check_recent_chapters(cursor)
generate_recommendations(config_ok, stats)

conn.close()

print("\n" + "=" * 80)
print("✅ 诊断完成")
print("=" * 80)
print("\n💡 提示: 查看 DIAGNOSTIC_TOOLS.md 了解所有工具的详细用法")
print()
