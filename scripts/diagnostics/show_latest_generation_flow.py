#!/usr/bin/env python3
"""
显示最新章节的完整生成流程
包括 Planner, Writer, Reviewer 的所有交互
"""
import sqlite3
import sys
import json
from pathlib import Path

def find_database():
    candidates = ["backend/storage/arboris.db", "storage/arboris.db", "arboris.db"]
    for candidate in candidates:
        db_file = Path.cwd() / candidate
        if db_file.exists():
            return str(db_file)
    return None

db_path = sys.argv[1] if len(sys.argv) > 1 else find_database()

if not db_path:
    print("❌ 未找到数据库")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查询最新章节
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

chapter_num, project_title, content, metadata_str, created = result

print("\n" + "=" * 80)
print(f"最新章节：第 {chapter_num} 章 - {project_title}")
print(f"创建时间：{created}")
print("=" * 80)

# 1. 检查 content
print("\n【1】章节内容（content字段）")
print("-" * 80)
print(f"类型：{type(content).__name__}")
print(f"长度：{len(content) if content else 0} 字符")

if content:
    content_preview = content[:500]
    print(f"\n前500字：")
    print(content_preview)

    # 检查是否是JSON
    if content.strip().startswith("{"):
        try:
            parsed = json.loads(content)
            print(f"\n⚠️  content 是 JSON 格式！")
            print(f"JSON 字段：{list(parsed.keys())}")

            # 检查是否是 Planner 格式
            planner_fields = ['analysis', 'plan', 'queries_summary', 'notes_for_writer']
            found = [f for f in planner_fields if f in parsed]
            if len(found) >= 3:
                print(f"\n❌ 这是 Planner 格式！包含字段：{found}")
            else:
                print(f"\n字段匹配：{found}")
        except:
            pass

# 2. 解析 metadata
print("\n\n【2】生成过程（metadata.conversation_history）")
print("-" * 80)

if not metadata_str:
    print("❌ 没有 metadata")
    sys.exit(1)

try:
    metadata = json.loads(metadata_str)
except:
    print("❌ metadata 解析失败")
    sys.exit(1)

if "conversation_history" not in metadata:
    print("❌ metadata 中没有 conversation_history")
    sys.exit(1)

history = metadata["conversation_history"]
print(f"\n共 {len(history)} 步交互\n")

# 分析每一步
for idx, item in enumerate(history, 1):
    agent = item.get("agent", "unknown")
    iteration = item.get("iteration", "")
    content_data = item.get("content", {})

    print(f"\n步骤 {idx}: {agent.upper()}", end="")
    if iteration:
        print(f" (迭代 {iteration})", end="")
    print()
    print("·" * 40)

    if agent == "planner":
        print("  Planner 的分析和规划：")
        if isinstance(content_data, dict):
            for key in ['analysis', 'plan', 'queries_summary', 'notes_for_writer']:
                if key in content_data:
                    value = str(content_data[key])[:100]
                    print(f"    {key}: {value}...")

    elif agent == "writer":
        print("  Writer 的输出：")
        if isinstance(content_data, dict):
            print(f"    字段：{list(content_data.keys())}")

            # 显示内容预览
            if 'word_count' in content_data:
                print(f"    字数：{content_data['word_count']}")
            if 'preview' in content_data:
                print(f"    预览：{content_data['preview'][:100]}...")

            # 检查是否有完整的full_content（不应该在history中）
            if 'full_content' in content_data:
                fc = content_data['full_content']
                print(f"    ⚠️  history 中包含完整 full_content！({len(str(fc))} 字符)")

                # 检查是否是Planner格式
                if isinstance(fc, str) and fc.strip().startswith("{"):
                    try:
                        parsed_fc = json.loads(fc)
                        planner_fields = ['analysis', 'plan', 'queries_summary', 'notes_for_writer']
                        found = [f for f in planner_fields if f in parsed_fc]
                        if len(found) >= 3:
                            print(f"    ❌ full_content 是 Planner 格式！{found}")
                    except:
                        pass

    elif agent == "reviewer":
        print("  Reviewer 的审核：")
        if isinstance(content_data, dict):
            approved = content_data.get("approved", False)
            score = content_data.get("score", 0)
            print(f"    通过：{'✅' if approved else '❌'}")
            print(f"    评分：{score}")
            if not approved:
                issues = content_data.get("issues", [])
                if issues:
                    print(f"    问题：{issues[:2]}")

    elif agent == "summarizer":
        print("  Summarizer 的摘要：")
        if isinstance(content_data, dict):
            summary = content_data.get("summary", "")
            print(f"    {summary[:150]}...")

# 3. 总结
print("\n\n【3】诊断结论")
print("-" * 80)

# 检查最终content
if content and content.strip().startswith("{"):
    try:
        parsed = json.loads(content)
        planner_fields = ['analysis', 'plan', 'queries_summary', 'notes_for_writer']
        found = [f for f in planner_fields if f in parsed]
        if len(found) >= 3:
            print("\n❌ 问题确认：章节content是Planner格式！")
            print(f"   包含字段：{found}")
            print(f"\n可能原因：")
            print(f"   1. Writer Agent 误返回了 Planner 的分析")
            print(f"   2. 保存时使用了错误的变量")
            print(f"   3. 检测逻辑未执行或被绕过")

            # 检查history中Writer的输出
            writer_outputs = [h for h in history if h.get("agent") == "writer"]
            if writer_outputs:
                print(f"\n   Writer 调用了 {len(writer_outputs)} 次")
                print(f"   需要查看 Writer 实际返回了什么")
        else:
            print("\n✅ content 不是 Planner 格式")
    except:
        pass
else:
    print("\n✅ content 是正常文本")

print("\n" + "=" * 80 + "\n")

conn.close()
