#!/usr/bin/env python3
"""
测试 Planner 格式检测逻辑

使用实际的问题章节内容来验证检测逻辑是否正确
"""
import json

# 实际的第7章内容（用户提供的）
test_content_1 = """{
  "analysis": "对当前章节的深度分析：
本章核心情节：在林氏即将被灭族之际，由族人鲜血激活的青铜残片"仙庭"展现神异，形成一道庇护屏障，将黑风寨的攻击暂时抵挡在外。
涉及角色：林远（领导者）、林氏幸存族人（受庇护者，处于震惊和悲痛中）、黑风寨修士（攻击者，从残忍变为惊疑）。
关键冲突：从凡人对修士的肉搏惨败，转变为仙庭屏障与黑风寨修士攻击之间的对峙。这是林氏命运的第一个超自然转折点。
特殊设定：本章将首次具象化"仙庭"的初级能力——庇护。需要详细描写屏障的形态、质感和防御力。",
  "plan": "章节内容规划：
开头：紧接上一章"血之契约"。从林远的视角切入，描绘屠杀的惨状和他的绝望。在最危急的时刻，他怀中的青铜残片（或被鲜血溅到的残片）爆发出柔和但不容侵犯的微光。
发展：微光迅速扩展，形成一个笼罩林家祖宅的无形屏障。黑风寨修士的攻击（如法术、飞剑）打在屏障上，如泥牛入海，只激起淡淡的涟漪。内外瞬间陷入死寂，双方都处于震惊之中。
高潮：黑风寨头领从震惊中反应过来，变为贪婪和愤怒，亲自出手发动更猛烈的攻击。屏障剧烈震动，但依然坚不可摧。林氏幸存者在屏障内，从死亡的恐惧中回过神来，转化为劫后余生的茫然和对族人逝去的巨大悲痛。
结尾：黑风寨久攻不下，暂时停止攻击，选择围困。林远看着庇护着众人的光芒，又看看脚下族人的尸体，深刻体会到这份"庇护"是由亲人的生命换来的，眼神变得无比复杂。为后续章节探索仙庭的"代价"埋下伏笔。
重点情节：光芒爆发瞬间（150字）、屏障抵挡攻击的场景（250字）、林氏族人内外情绪的转变（200字）。",
  "queries_summary": "查询结果总结：
本次查询尝试失败，工具未能成功执行。因此，所有规划均基于项目蓝图、所有章节摘要和前两章的详细内容进行。根据第5章和第6章的摘要可以推断：林氏与黑风寨的冲突已在正面交锋中彻底激化，并付出了惨重的人员伤亡（"血流成河"）。仙庭是在"濒死族人"的鲜血浇灌下才被动激活的，这决定了本章的基调是惨胜而非完胜。林远作为领导者，此刻应处于目睹族人惨死、身心俱疲但又因这突来转机而强撑精神的复杂状态。",
  "notes_for_writer": "给写作Agent的建议：
注意事项：本章的核心是"转折"而非"反杀"。要极力渲染绝望到希望的瞬间变化，但这份希望必须是沉重的。屏障是"庇护"
}"""

# 第5章内容（Markdown包裹的JSON）
test_content_2 = """`json
{
  "full_content": "## 泰拉-0，创世核心\\n\\n【周期：150】\\n【文明状态：稳定】\\n【项目'盖亚'运行良好，农业基础设施V1.0已完成部署，人口增长曲线符合预期模型。】\\n\\n林奇的意识在数据流中徜徉，享受着这种一切尽在掌握的宁静。他的世界，泰拉-0，就像一个完美编译、 flawlessly运行的程序。没有error，没有warning，每一个进程都在盖亚这个\\"中央处理器\\"的调度下有条不紊地执行。",
  "word_count": 2000
}
`"""

# 正常的章节内容
test_content_3 = """第一章 林氏危机

林远站在村口，看着远处的黑烟升起，心中涌起不祥的预感。

作为林氏家族的少族长，他深知这次危机的严重性。黑风寨的修士们已经围困村子三天三夜，族人们人心惶惶。

"族长，我们该怎么办？"一名族人焦急地问道。

林远沉思片刻，目光坚定："我们不能坐以待毙，必须想办法突围。"

..."""

def test_orchestrator_detection(content):
    """测试 ai_orchestrator_helper.py 的检测逻辑"""
    print("\n" + "="*80)
    print("测试 orchestrator 检测逻辑")
    print("="*80)

    # 模拟检测逻辑
    planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
    suspicious_count = 0

    preview = content[:500] if len(content) >= 500 else content

    for kw in planner_keywords:
        # 检查多种格式: analysis:, "analysis":
        if f'{kw}:' in preview or f'"{kw}":' in preview:
            suspicious_count += 1
            print(f"  ✓ 检测到关键词: {kw}")

    print(f"\n  可疑关键词数量: {suspicious_count}")

    if suspicious_count >= 2:
        print("  ❌ 判定：Planner 格式（会被阻止）")
        return False
    else:
        print("  ✅ 判定：正常内容（会通过）")
        return True

def test_auto_generator_detection(content):
    """测试 auto_generator_service.py 的检测逻辑"""
    print("\n" + "="*80)
    print("测试 auto_generator 检测逻辑")
    print("="*80)

    # 移除 Markdown 包裹
    content_stripped = content.strip()
    if content_stripped.startswith('`'):
        if content_stripped.startswith('```json'):
            content_stripped = content_stripped[7:]
        elif content_stripped.startswith('```'):
            content_stripped = content_stripped[3:]
        if content_stripped.endswith('```'):
            content_stripped = content_stripped[:-3]
        content_stripped = content_stripped.strip()

    # 检查是否是 JSON
    if content_stripped.startswith("{") and content_stripped.endswith("}"):
        try:
            parsed = json.loads(content_stripped)
            print(f"  ✓ 是 JSON 格式")
            print(f"  字段: {list(parsed.keys())}")

            # 检查是否包含Planner字段
            planner_fields = ['analysis', 'plan', 'queries_summary', 'notes_for_writer']
            has_planner = sum(1 for f in planner_fields if f in parsed)

            found_fields = [f for f in planner_fields if f in parsed]
            if found_fields:
                print(f"  ✓ 包含 Planner 字段: {found_fields}")

            print(f"\n  Planner 字段数量: {has_planner}")

            if has_planner >= 3:
                print("  ❌ 判定：Planner 格式（会被拒绝保存）")
                return False
            else:
                # 检查是否有 full_content
                if 'full_content' in parsed:
                    print("  ✅ 判定：包含 full_content（会保存）")
                    return True
                else:
                    print("  ⚠️  判定：JSON 但无 full_content（会报错）")
                    return False
        except json.JSONDecodeError as e:
            print(f"  ✗ JSON 解析失败: {e}")
            print("  ✅ 判定：不是 JSON，按普通文本处理")
            return True
    else:
        print("  ✅ 判定：不是 JSON，按普通文本处理")
        return True

print("\n" + "="*80)
print("🧪 Planner 格式检测逻辑验证")
print("="*80)

# 测试1：第7章（纯 Planner 格式）
print("\n\n【测试1】第7章 - 纯 Planner 格式")
print("-"*80)
print(f"内容长度: {len(test_content_1)} 字符")
print(f"前100字: {test_content_1[:100]}...")

result1_orchestrator = test_orchestrator_detection(test_content_1)
result1_auto_gen = test_auto_generator_detection(test_content_1)

print("\n📊 综合判定:")
if not result1_orchestrator or not result1_auto_gen:
    print("  ✅ 会被阻止保存（符合预期）")
else:
    print("  ❌ 不会被阻止（检测失败！）")

# 测试2：第5章（Markdown 包裹的 JSON，有 full_content）
print("\n\n【测试2】第5章 - Markdown 包裹的 JSON（有 full_content）")
print("-"*80)
print(f"内容长度: {len(test_content_2)} 字符")
print(f"前100字: {test_content_2[:100]}...")

result2_orchestrator = test_orchestrator_detection(test_content_2)
result2_auto_gen = test_auto_generator_detection(test_content_2)

print("\n📊 综合判定:")
if result2_auto_gen:
    print("  ✅ 会被保存（符合预期）")
else:
    print("  ❌ 会被阻止（误判！）")

# 测试3：正常章节
print("\n\n【测试3】正常章节内容")
print("-"*80)
print(f"内容长度: {len(test_content_3)} 字符")
print(f"前100字: {test_content_3[:100]}...")

result3_orchestrator = test_orchestrator_detection(test_content_3)
result3_auto_gen = test_auto_generator_detection(test_content_3)

print("\n📊 综合判定:")
if result3_orchestrator and result3_auto_gen:
    print("  ✅ 会通过检测（符合预期）")
else:
    print("  ❌ 会被阻止（误判！）")

# 总结
print("\n\n" + "="*80)
print("📋 测试总结")
print("="*80)
print("\n测试结果:")
print(f"  测试1（纯Planner）: {'✅ 通过' if not (result1_orchestrator and result1_auto_gen) else '❌ 失败'}")
print(f"  测试2（有full_content）: {'✅ 通过' if result2_auto_gen else '❌ 失败'}")
print(f"  测试3（正常内容）: {'✅ 通过' if (result3_orchestrator and result3_auto_gen) else '❌ 失败'}")

all_passed = (
    not (result1_orchestrator and result1_auto_gen) and  # 测试1应该被阻止
    result2_auto_gen and  # 测试2应该通过
    (result3_orchestrator and result3_auto_gen)  # 测试3应该通过
)

print(f"\n总体结果: {'✅ 所有测试通过！修复逻辑正确' if all_passed else '❌ 有测试失败，需要调整'}")
print("="*80 + "\n")
