#!/usr/bin/env python3
"""
诊断 3Agent 生成问题

检查：
- Writer 是否返回了错误格式
- Planner/Reviewer/Summarizer 的工作情况
- 迭代次数和评分

使用方法：
  python3 diagnose_3agent.py [数据库路径] [章节号]

示例：
  python3 diagnose_3agent.py              # 诊断最新章节
  python3 diagnose_3agent.py /path/db 1  # 诊断第1章
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
chapter_num = int(sys.argv[2]) if len(sys.argv) > 2 else None

if not db_path:
    print("❌ 未找到数据库")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查询章节
if chapter_num:
    cursor.execute("""
    SELECT c.chapter_number, p.title, cv.content, cv.metadata, cv.created_at
    FROM chapters c
    JOIN chapter_versions cv ON c.selected_version_id = cv.id
    JOIN novel_projects p ON c.project_id = p.id
    WHERE c.chapter_number = ?
    ORDER BY cv.created_at DESC
    LIMIT 1
    """, (chapter_num,))
else:
    cursor.execute("""
    SELECT c.chapter_number, p.title, cv.content, cv.metadata, cv.created_at
    FROM chapters c
    JOIN chapter_versions cv ON c.selected_version_id = cv.id
    JOIN novel_projects p ON c.project_id = p.id
    ORDER BY cv.created_at DESC
    LIMIT 1
    """)

result = cursor.fetchone()

if not result:
    print("❌ 未找到章节")
    sys.exit(1)

chapter_num, project_title, content, metadata, created = result

print("\n" + "=" * 80)
print(f"🔍 诊断第 {chapter_num} 章 - {project_title}")
print(f"⏰ 创建时间: {created}")
print("=" * 80)

# ==================== 内容格式检查 ====================
print("\n📋 1. 内容格式检查")
print("-" * 80)

issues = []
warnings = []

# 检查内容类型
if content.strip().startswith("{") and content.strip().endswith("}"):
    try:
        parsed = json.loads(content)
        issues.append("❌ 内容是纯 JSON 对象")
        print(f"内容结构: {list(parsed.keys())}")
    except:
        pass

# 检查 Planner 关键词
planner_keywords = {
    "analysis:": 0,
    "plan:": 0,
    "queries_summary:": 0,
    "notes_for_writer:": 0,
    '"analysis":': 0,
    '"plan":': 0,
}

for kw in planner_keywords:
    if kw in content[:1000]:
        planner_keywords[kw] = content[:1000].count(kw)

planner_count = sum(planner_keywords.values())
if planner_count > 0:
    issues.append(f"❌ 包含 Planner 格式关键词 ({planner_count} 个)")
    for kw, count in planner_keywords.items():
        if count > 0:
            print(f"  发现: {kw} (出现 {count} 次)")

# 检查 Markdown 标记
if "```json" in content[:200] or "```" in content[:200]:
    warnings.append("⚠️  包含 Markdown 代码块标记")

# 检查字数
word_count = len(content)
if word_count < 500:
    warnings.append(f"⚠️  字数过少: {word_count}")
elif word_count > 5000:
    print(f"✅ 字数正常: {word_count}")
else:
    print(f"✅ 字数: {word_count}")

# 显示问题
if issues:
    print("\n🚨 严重问题:")
    for issue in issues:
        print(f"  {issue}")

if warnings:
    print("\n⚠️  警告:")
    for warning in warnings:
        print(f"  {warning}")

if not issues and not warnings:
    print("\n✅ 格式检查通过")

# 显示内容预览
print(f"\n📝 内容前300字:")
print("-" * 80)
print(content[:300])
print("...")

# ==================== Metadata 分析 ====================
print("\n" + "=" * 80)
print("📊 2. 生成过程分析")
print("-" * 80)

if not metadata:
    print("❌ 没有 metadata 信息")
else:
    try:
        meta = json.loads(metadata)

        # 基本信息
        print(f"\n基本信息:")
        print(f"  迭代次数: {meta.get('iterations', 'N/A')}")
        print(f"  最终评分: {meta.get('final_score', 'N/A')}")
        print(f"  总耗时: {meta.get('total_time_seconds', 'N/A')} 秒")

        # 对话历史
        if "conversation_history" in meta:
            history = meta["conversation_history"]
            print(f"\n对话历史 (共 {len(history)} 条):")

            # 统计各 Agent 的调用次数
            agent_counts = {}
            for item in history:
                agent = item.get("agent", "unknown")
                agent_counts[agent] = agent_counts.get(agent, 0) + 1

            print("\nAgent 调用统计:")
            for agent, count in agent_counts.items():
                print(f"  {agent}: {count} 次")

            # 显示关键步骤
            print("\n关键步骤:")
            for idx, item in enumerate(history, 1):
                agent = item.get("agent", "unknown")
                iteration = item.get("iteration", "")
                iter_str = f" (迭代 {iteration})" if iteration else ""

                if agent == "planner":
                    content_preview = str(item.get("content", {}))[:100]
                    print(f"  {idx}. Planner{iter_str}: {content_preview}...")

                elif agent == "writer":
                    content_data = item.get("content", {})
                    word_count = content_data.get("word_count", 0)
                    preview = content_data.get("preview", "")[:50]
                    print(f"  {idx}. Writer{iter_str}: 生成 {word_count} 字, 预览: {preview}...")

                elif agent == "reviewer":
                    content_data = item.get("content", {})
                    approved = content_data.get("approved", False)
                    score = content_data.get("score", 0)
                    status = "✅ 通过" if approved else "❌ 未通过"
                    print(f"  {idx}. Reviewer{iter_str}: {status}, 评分: {score}")

                    # 显示修改建议
                    suggestions = content_data.get("suggestions", [])
                    if suggestions:
                        print(f"      修改建议: {suggestions[:2]}")

                elif agent == "summarizer":
                    content_data = item.get("content", {})
                    summary = content_data.get("summary", "")[:100]
                    print(f"  {idx}. Summarizer: {summary}...")

    except json.JSONDecodeError as e:
        print(f"❌ Metadata 解析失败: {e}")
    except Exception as e:
        print(f"❌ 分析失败: {e}")

# ==================== 建议 ====================
print("\n" + "=" * 80)
print("💡 3. 诊断建议")
print("-" * 80)

if issues:
    print("\n🔧 需要修复的问题:")
    if any("JSON" in issue for issue in issues):
        print("  - Writer 返回了纯 JSON，没有正确提取 full_content")
        print("  - 建议：重新生成这一章")
    if any("Planner" in issue for issue in issues):
        print("  - Writer 返回了 Planner 格式的内容")
        print("  - 建议：检查 Writer prompt，或使用更好的模型")
else:
    print("\n✅ 没有发现严重问题")

if metadata:
    try:
        meta = json.loads(metadata)
        iterations = meta.get("iterations", 0)
        final_score = meta.get("final_score", 0)

        if iterations >= 3:
            print(f"\n⚠️  迭代次数较多 ({iterations} 次)，可能说明:")
            print("  - Reviewer 标准较严格")
            print("  - Writer 初次生成质量不够")

        if final_score < 7:
            print(f"\n⚠️  最终评分较低 ({final_score})，建议:")
            print("  - 考虑重新生成")
            print("  - 或手动修改内容")
    except:
        pass

conn.close()

print("\n" + "=" * 80)
print("✅ 诊断完成")
print("=" * 80 + "\n")
