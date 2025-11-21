#!/usr/bin/env python3
"""
模拟 3Agent 生成流程，查找 Planner 内容被错误保存的原因
"""
import json

print("=" * 80)
print("🧪 模拟 3Agent 章节生成流程")
print("=" * 80)

# ==================== 模拟数据 ====================

# 1. Planner Agent 的返回结果
planner_result = {
    "analysis": "对当前章节的深度分析：本章核心情节...",
    "plan": "章节内容规划：开头、发展、高潮、结尾...",
    "queries_summary": "查询结果总结：...",
    "notes_for_writer": "给写作Agent的建议：..."
}

print("\n【步骤1】Planner Agent 返回")
print("-" * 80)
print(f"planner_result = {json.dumps(planner_result, ensure_ascii=False, indent=2)[:200]}...")

# 2. Writer Agent 的返回结果（正确的）
writer_result = {
    "full_content": "第一章 危机降临\n\n林远站在村口，看着远处升起的黑烟...",
    "writing_notes": "本章着重刻画了林远的内心挣扎..."
}

print("\n【步骤2】Writer Agent 返回")
print("-" * 80)
print(f"writer_result = {json.dumps(writer_result, ensure_ascii=False, indent=2)[:200]}...")

# 3. 模拟 generate_chapter_content 返回值
def simulate_generate_chapter_content():
    """模拟 ai_orchestrator_helper.py 的返回"""
    # 这里应该返回 writer_result 的 full_content
    # 但如果代码有问题，可能会返回错误的内容

    final_content = writer_result.get("full_content", "")

    result = {
        "full_content": final_content,
        "summary": "章节摘要...",
        "metadata": {
            "conversation_history": [
                {"agent": "planner", "content": planner_result},
                {"agent": "writer", "content": writer_result},
            ],
            "iterations": 1,
            "final_score": 85
        }
    }

    return json.dumps(result, ensure_ascii=False)

response = simulate_generate_chapter_content()

print("\n【步骤3】generate_chapter_content 返回（JSON字符串）")
print("-" * 80)
print(f"response = {response[:300]}...")

# 4. 模拟 auto_generator_service.py 的处理
def simulate_auto_generator_processing(response_str):
    """模拟 auto_generator_service.py 第905-911行的处理"""
    print("\n【步骤4】auto_generator_service.py 处理")
    print("-" * 80)

    # 移除 think tags
    cleaned = response_str  # remove_think_tags(response)

    # 解包 markdown json
    normalized = cleaned  # unwrap_markdown_json(cleaned)

    # 解析 JSON
    try:
        parsed = json.loads(normalized)
        print(f"✅ JSON 解析成功")
        print(f"字段: {list(parsed.keys())}")
        return parsed
    except (json.JSONDecodeError, ValueError) as e:
        print(f"❌ JSON 解析失败: {e}")
        return {"content": normalized}

raw_version = simulate_auto_generator_processing(response)

# 5. 提取 full_content
def simulate_extract_full_content(variant):
    """模拟 auto_generator_service.py 第916-971行的处理"""
    print("\n【步骤5】提取 full_content")
    print("-" * 80)

    if not isinstance(variant, dict):
        print(f"❌ variant 不是 dict: {type(variant)}")
        return None

    print(f"variant 字段: {list(variant.keys())}")

    if "full_content" in variant and variant["full_content"]:
        full_content = variant["full_content"]
        print(f"✅ 找到 full_content 字段")
        print(f"类型: {type(full_content)}")
        print(f"长度: {len(full_content) if isinstance(full_content, str) else '不是字符串'}")
        print(f"前200字: {str(full_content)[:200]}")

        # 检查是否是 Planner 格式
        if isinstance(full_content, str):
            content_stripped = full_content.strip()
            if content_stripped.startswith("{") and content_stripped.endswith("}"):
                try:
                    parsed = json.loads(content_stripped)
                    planner_fields = ['analysis', 'plan', 'queries_summary', 'notes_for_writer']
                    has_planner = sum(1 for f in planner_fields if f in parsed)

                    if has_planner >= 3:
                        print(f"\n❌❌❌ 检测到 Planner 格式！包含 {has_planner} 个字段")
                        print(f"字段: {[f for f in planner_fields if f in parsed]}")
                        print(f"\n🚨 这就是问题所在！full_content 是 Planner 的输出！")
                        return None  # 应该抛出异常
                    else:
                        print(f"✅ 不是 Planner 格式（只有 {has_planner} 个字段）")
                except json.JSONDecodeError:
                    print(f"✅ 不是 JSON，是正常文本")

        return full_content
    else:
        print(f"❌ 没有 full_content 字段")
        return None

extracted_content = simulate_extract_full_content(raw_version)

# 6. 最终保存
print("\n【步骤6】最终保存到数据库")
print("-" * 80)
if extracted_content:
    print(f"✅ 保存的内容: {extracted_content[:200]}...")

    # 检查最终保存的内容
    if extracted_content.strip().startswith("{"):
        print(f"\n⚠️  保存的内容以 {{ 开头，可能有问题！")
        try:
            parsed = json.loads(extracted_content)
            planner_fields = ['analysis', 'plan', 'queries_summary', 'notes_for_writer']
            found = [f for f in planner_fields if f in parsed]
            if len(found) >= 3:
                print(f"❌❌❌ 确认：保存的是 Planner 格式！")
                print(f"包含字段: {found}")
        except:
            pass
else:
    print(f"❌ 没有内容可保存")

print("\n" + "=" * 80)
print("🔍 诊断结论")
print("=" * 80)

# ==================== 现在测试错误情况 ====================
print("\n\n" + "=" * 80)
print("🔴 测试错误情况：Writer 返回了 Planner 的内容")
print("=" * 80)

# 模拟 Writer 错误地返回了 Planner 的内容
wrong_writer_result = {
    "full_content": json.dumps(planner_result, ensure_ascii=False),  # 🔴 这是错的！
    "writing_notes": "..."
}

print("\n【错误模拟】Writer 错误地返回 Planner JSON 作为 full_content")
print("-" * 80)
print(f"wrong_writer_result['full_content'] = {wrong_writer_result['full_content'][:200]}...")

# 重新模拟流程
def simulate_wrong_flow():
    result = {
        "full_content": wrong_writer_result["full_content"],
        "summary": "章节摘要...",
        "metadata": {
            "conversation_history": [],
            "iterations": 1,
            "final_score": 85
        }
    }
    return json.dumps(result, ensure_ascii=False)

wrong_response = simulate_wrong_flow()
wrong_raw_version = simulate_auto_generator_processing(wrong_response)
wrong_extracted = simulate_extract_full_content(wrong_raw_version)

print("\n【错误结果】")
print("-" * 80)
if wrong_extracted:
    # 检查
    try:
        parsed = json.loads(wrong_extracted)
        planner_fields = ['analysis', 'plan', 'queries_summary', 'notes_for_writer']
        found = [f for f in planner_fields if f in parsed]
        if len(found) >= 3:
            print(f"❌❌❌ 确认问题：Writer 返回的 full_content 是 Planner 的 JSON 字符串！")
            print(f"包含 Planner 字段: {found}")
            print(f"\n💡 根本原因：")
            print(f"   Writer Agent 的 LLM 模型错误地返回了 Planner 格式的内容")
            print(f"   而不是真正的章节正文")
            print(f"\n💡 解决方案：")
            print(f"   1. ✅ 已实现：在 ai_orchestrator_helper.py:1766-1790 检测并阻止")
            print(f"   2. ✅ 已实现：在 auto_generator_service.py:934-956 二次检测")
            print(f"   3. 需要：检查 Writer 的 prompt 是否明确要求返回正文")
            print(f"   4. 需要：检查 Writer 的上下文中是否有 Planner 的输出污染")
    except:
        print(f"✅ 不是 JSON")

print("\n" + "=" * 80)
print("📋 结论")
print("=" * 80)
print("""
根据模拟，问题的根本原因是：

1. ❌ Writer Agent 的 LLM 错误地返回了 Planner 格式的 JSON
   - 本应返回：{"full_content": "第一章 危机降临\\n\\n林远..."}
   - 实际返回：{"full_content": "{\\"analysis\\": ..., \\"plan\\": ...}"}

2. 为什么会这样？
   - Writer 的上下文中包含了 Planner 的完整输出（见 _build_writer_context）
   - LLM 可能混淆了角色，把 Planner 的内容当作了要写的内容

3. 如何验证？
   - 查看实际章节的 metadata.conversation_history
   - 看 Writer 步骤中的 content 字段
   - 确认 Writer 实际返回了什么

4. 已实现的防护措施：
   - ai_orchestrator_helper.py:1766-1790: 检测 full_content 中的 Planner 关键词
   - auto_generator_service.py:934-956: 保存前检查是否是 Planner 格式
   - 两轮检测机制，第二轮失败会抛出异常

5. 可能的问题：
   - 如果 Writer 在第一轮就返回了正常内容，不会进入第二轮
   - 但如果第一轮返回的内容只包含了部分 Planner 关键词（<2个），会被放过
   - 或者关键词检测未能匹配（如使用了不同的格式）
""")

print("\n✅ 建议：运行 show_latest_generation_flow.py 查看实际的 conversation_history")
print("=" * 80 + "\n")
