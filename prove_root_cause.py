#!/usr/bin/env python3
"""
用实际例子证明根本原因
"""
import json

print("=" * 80)
print("🔍 证明：为什么 Writer 会返回 Planner 格式")
print("=" * 80)

# 模拟 Planner 的返回结果
planner_result = {
    "analysis": "本章核心情节：林氏族人激活青铜残片...",
    "plan": "开头：危机时刻；发展：屏障形成；高潮：抵挡攻击...",
    "queries_summary": "查询到前文中提到过青铜残片...",
    "notes_for_writer": "注意渲染绝望到希望的转折..."
}

print("\n【步骤1】Planner Agent 返回")
print("-" * 80)
print(json.dumps(planner_result, ensure_ascii=False, indent=2))

# ==================== 旧代码的做法（有问题）====================
print("\n\n" + "=" * 80)
print("❌ 旧代码的做法（会导致问题）")
print("=" * 80)

def old_build_writer_context(user_prompt, planner_result):
    """旧版本：直接把整个 JSON 传给 Writer"""
    context_parts = [
        "# 章节上下文",
        user_prompt,
        "",
        "# 思考Agent的分析和规划",
        json.dumps(planner_result, ensure_ascii=False, indent=2),  # ← 问题所在！
        "",
        "# 请撰写章节正文（JSON格式：{\"full_content\": \"...\"}）"
    ]
    return "\n".join(context_parts)

old_context = old_build_writer_context("根据大纲撰写第7章", planner_result)

print("\n【Writer Agent 收到的上下文】")
print("-" * 80)
print(old_context)
print("\n")

print("⚠️  问题分析：")
print("   1. Writer 看到的是一个完整的 JSON 结构")
print("   2. JSON 中有 4 个字段：analysis, plan, queries_summary, notes_for_writer")
print("   3. LLM 可能会误以为：\"哦，我也应该返回这种格式的 JSON\"")
print("   4. 结果：Writer 返回了")
print("      {")
print("        \"full_content\": \"{\\\"analysis\\\": ..., \\\"plan\\\": ...}\"  ← 错误！")
print("      }")
print()
print("   或者更糟：")
print("      {")
print("        \"analysis\": \"...\",  ← 直接模仿 Planner 格式")
print("        \"plan\": \"...\",")
print("        \"full_content\": \"...\"")
print("      }")

# ==================== 新代码的做法（已修复）====================
print("\n\n" + "=" * 80)
print("✅ 新代码的做法（已修复）")
print("=" * 80)

def new_build_writer_context(user_prompt, planner_result):
    """新版本：只提取文本内容，避免 JSON 结构污染"""
    planner_guidance = []
    if planner_result.get("analysis"):
        planner_guidance.append(f"【章节分析】\n{planner_result['analysis']}")
    if planner_result.get("plan"):
        planner_guidance.append(f"【内容规划】\n{planner_result['plan']}")
    if planner_result.get("notes_for_writer"):
        planner_guidance.append(f"【写作建议】\n{planner_result['notes_for_writer']}")
    if planner_result.get("queries_summary"):
        planner_guidance.append(f"【查询结果参考】\n{planner_result['queries_summary']}")

    context_parts = [
        "# 章节上下文",
        user_prompt,
        "",
        "# 思考Agent的分析和建议",
        "\n\n".join(planner_guidance) if planner_guidance else "无额外建议",
        "",
        "# ⚠️ 重要：你的任务是撰写章节正文",
        "",
        "请根据上述分析和建议，撰写完整的章节内容（小说正文），输出JSON格式：",
        "{",
        '  "full_content": "完整的章节正文内容（markdown格式的小说文本）",',
        '  "writing_notes": "创作说明（可选）"',
        "}",
        "",
        "❌ 不要输出分析、规划等结构化内容",
        "✅ 只输出故事正文（对话、描写、情节等）"
    ]
    return "\n".join(context_parts)

new_context = new_build_writer_context("根据大纲撰写第7章", planner_result)

print("\n【Writer Agent 收到的上下文】")
print("-" * 80)
print(new_context)
print("\n")

print("✅ 改进说明：")
print("   1. 不再显示完整的 JSON 结构")
print("   2. 只提取 Planner 的文本建议，用标题分隔")
print("   3. 明确告诉 Writer：你的任务是写章节正文")
print("   4. 明确说明输出格式：{\"full_content\": \"...\", \"writing_notes\": \"...\"}")
print("   5. 添加反面指令：❌ 不要输出分析、规划等结构化内容")

# ==================== 对比总结 ====================
print("\n\n" + "=" * 80)
print("📊 对比总结")
print("=" * 80)

print("\n旧代码传给 Writer 的内容包含：")
print("  {")
print('    "analysis": "...",')
print('    "plan": "...",')
print('    "queries_summary": "...",')
print('    "notes_for_writer": "..."')
print("  }")
print("  ↓")
print("  LLM 看到这个 JSON 结构，可能模仿它")

print("\n新代码传给 Writer 的内容：")
print("  【章节分析】")
print("  本章核心情节：...")
print("  ")
print("  【内容规划】")
print("  开头：危机时刻...")
print("  ")
print("  ⚠️ 重要：你的任务是撰写章节正文")
print("  输出格式：{\"full_content\": \"...\", \"writing_notes\": \"...\"}")
print("  ❌ 不要输出分析、规划等结构化内容")
print("  ↓")
print("  LLM 清楚地知道要输出章节正文，不会模仿 Planner 格式")

print("\n" + "=" * 80)
print("💡 结论")
print("=" * 80)
print("""
问题的根本原因：
  旧代码把 Planner 的完整 JSON 结构传给了 Writer。
  LLM 看到这个结构后，可能会模仿它的格式，而不是严格按照 Writer prompt 输出。

为什么会这样？
  1. LLM 会参考上下文中的所有示例
  2. 当上下文中有一个清晰的 JSON 结构示例时，LLM 可能认为这是"期望的输出格式"
  3. 尽管 Writer prompt 说明了要输出 full_content，但上下文的影响更强

修复方法：
  1. ✅ 移除 JSON 结构，只保留文本内容
  2. ✅ 用标题分隔不同部分（【章节分析】、【内容规划】等）
  3. ✅ 明确强调输出格式和任务
  4. ✅ 添加反面指令，明确说明不要做什么

这就是为什么 Writer 会"仿照" Planner 的输出格式！
""")

print("=" * 80 + "\n")
