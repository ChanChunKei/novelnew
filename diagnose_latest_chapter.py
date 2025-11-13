#!/usr/bin/env python3
"""
诊断最新生成的章节问题
"""
import sqlite3
import json
from pathlib import Path

db_path = "backend/storage/arboris.db"

if not Path(db_path).exists():
    print(f"❌ 数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 获取最新的章节版本
cursor.execute("""
    SELECT
        cv.id,
        cv.chapter_id,
        cv.content,
        cv.metadata,
        cv.created_at,
        c.chapter_number
    FROM chapter_versions cv
    JOIN chapters c ON cv.chapter_id = c.id
    ORDER BY cv.created_at DESC
    LIMIT 1
""")

row = cursor.fetchone()
if not row:
    print("❌ 数据库中没有章节版本")
    conn.close()
    exit(0)

version_id, chapter_id, content, metadata_str, created_at, chapter_number = row

print("=" * 80)
print(f"📖 最新生成的章节：第 {chapter_number} 章")
print("=" * 80)
print(f"版本ID: {version_id}")
print(f"章节ID: {chapter_id}")
print(f"创建时间: {created_at}")
print(f"内容长度: {len(content) if content else 0} 字符")
print()

# 检查内容是否是 Planner 格式
if content:
    print("=" * 80)
    print("📝 内容分析")
    print("=" * 80)

    content_preview = content[:500] if len(content) > 500 else content

    # 检查是否包含 Planner 关键词
    planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
    found_keywords = []
    for kw in planner_keywords:
        if f'"{kw}":' in content_preview or f'{kw}:' in content_preview:
            found_keywords.append(kw)

    if found_keywords:
        print(f"⚠️  检测到 Planner 格式关键词: {found_keywords}")
        print()
        print("内容前 500 字符:")
        print("-" * 80)
        print(content_preview)
        print("-" * 80)
    else:
        print("✅ 未检测到 Planner 格式关键词")
        print()
        print("内容前 300 字符:")
        print("-" * 80)
        print(content[:300] if len(content) > 300 else content)
        print("-" * 80)

# 分析 metadata 中的 conversation_history
if metadata_str:
    print()
    print("=" * 80)
    print("🔍 分析生成过程 (conversation_history)")
    print("=" * 80)

    try:
        metadata = json.loads(metadata_str)
        conversation_history = metadata.get("conversation_history", [])

        if not conversation_history:
            print("⚠️  没有找到 conversation_history")
        else:
            print(f"📊 对话轮次: {len(conversation_history)}")
            print()

            # 找到 Planner 的输出
            planner_output = None
            for item in conversation_history:
                if item.get("agent") == "planner":
                    planner_output = item.get("content")
                    break

            if planner_output:
                print("=" * 80)
                print("1️⃣  Planner Agent 的输出")
                print("=" * 80)
                print(json.dumps(planner_output, ensure_ascii=False, indent=2)[:800])
                print("..." if len(json.dumps(planner_output)) > 800 else "")
                print()

            # 找到 Writer 收到的上下文（如果有的话）
            # 通常 Writer 的输入会包含在 conversation_history 中
            writer_items = [item for item in conversation_history if item.get("agent") == "writer"]

            if writer_items:
                print("=" * 80)
                print("2️⃣  Writer Agent 的输出")
                print("=" * 80)
                for idx, item in enumerate(writer_items, 1):
                    print(f"\n--- Writer 第 {idx} 轮 ---")
                    writer_content = item.get("content")
                    if isinstance(writer_content, dict):
                        full_content = writer_content.get("full_content", "")
                        if full_content:
                            # 检查是否是 Planner 格式
                            if any(f'"{kw}":' in full_content[:500] for kw in planner_keywords):
                                print("❌ Writer 返回了 Planner 格式内容！")
                                print()
                                print("full_content 前 500 字符:")
                                print(full_content[:500])
                            else:
                                print("✅ Writer 返回了正常的章节内容")
                                print()
                                print("full_content 前 200 字符:")
                                print(full_content[:200])
                    else:
                        print("⚠️  Writer 返回格式异常")
                        print(str(writer_content)[:300])

            # 检查是否有 context 字段（可能记录了 Writer 收到的上下文）
            print()
            print("=" * 80)
            print("3️⃣  检查 Writer 收到的上下文")
            print("=" * 80)

            # 查找包含 planner_result 的地方
            found_context = False
            for item in conversation_history:
                if "context" in item:
                    found_context = True
                    print("找到 context 字段:")
                    print(json.dumps(item["context"], ensure_ascii=False, indent=2)[:1000])
                    break

            if not found_context:
                print("⚠️  conversation_history 中没有记录 Writer 的输入上下文")
                print("这是正常的，因为通常只记录输出，不记录输入")

    except json.JSONDecodeError as e:
        print(f"❌ 无法解析 metadata JSON: {e}")
    except Exception as e:
        print(f"❌ 分析 metadata 时出错: {e}")

print()
print("=" * 80)
print("💡 诊断建议")
print("=" * 80)

if found_keywords:
    print("""
问题确认：章节内容确实包含 Planner 格式

可能的原因：
1. ❌ 后端服务没有重启，还在使用旧代码
2. ❌ 代码修改没有生效
3. ❌ 还有其他地方也在构建 Writer 上下文

下一步诊断：
1. 检查后端服务是否重启
2. 检查代码中 _build_writer_context 函数是否被正确调用
3. 添加日志输出，看 Writer 实际收到的上下文是什么
""")
else:
    print("""
✅ 内容看起来正常，没有检测到 Planner 格式

如果你看到的内容确实有问题，可能是：
1. 检测逻辑不够准确
2. Planner 格式在内容的其他位置（不在前 500 字符）

请检查完整内容或提供更多细节。
""")

conn.close()
