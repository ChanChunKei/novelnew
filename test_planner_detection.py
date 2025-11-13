#!/usr/bin/env python3
"""
测试Planner格式检测逻辑
不需要数据库和服务器环境，直接测试检测函数
"""
import json
import re

def detect_planner_format(content: str, verbose=True) -> tuple[bool, list[str]]:
    """
    检测内容是否是Planner格式
    
    Returns:
        (is_planner, reasons) - 是否是Planner格式，以及检测到的原因列表
    """
    reasons = []
    
    # 检测1: JSON格式检测
    if content.strip().startswith("{"):
        try:
            nested = json.loads(content)
            if isinstance(nested, dict):
                planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
                found_planner_fields = [k for k in planner_keywords if k in nested]
                
                if found_planner_fields and "full_content" not in nested:
                    reasons.append(f"JSON包含Planner字段: {found_planner_fields}，但缺少full_content")
                    if verbose:
                        print(f"  ✅ 检测1（JSON格式）: 发现Planner字段 {found_planner_fields}")
                    return True, reasons
                
                if "full_content" in nested:
                    if verbose:
                        print(f"  ✅ 检测1（JSON格式）: 正常，包含full_content字段")
                    # 继续检测full_content的内容
                    content = nested["full_content"]
        except json.JSONDecodeError:
            if verbose:
                print(f"  ℹ️ 检测1（JSON格式）: 不是有效JSON")
    
    # 检测2: 文本关键词检测
    planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
    suspicious_count = 0
    check_length = min(1000, len(content))
    found_keywords = []
    
    for kw in planner_keywords:
        if f'{kw}:' in content[:check_length] or f'"{kw}":' in content[:check_length]:
            suspicious_count += 1
            found_keywords.append(kw)
    
    if suspicious_count >= 2:
        reasons.append(f"文本包含{suspicious_count}个Planner关键词: {found_keywords}")
        if verbose:
            print(f"  ✅ 检测2（文本关键词）: 发现{suspicious_count}个关键词 {found_keywords}")
        return True, reasons
    
    if verbose:
        print(f"  ✅ 检测2（文本关键词）: 正常，仅发现{suspicious_count}个关键词")
    
    return False, reasons


def test_cases():
    """测试各种场景"""
    
    print("=" * 80)
    print("测试Planner格式检测逻辑")
    print("=" * 80)
    
    # 测试用例
    test_data = [
        {
            "name": "场景1: 纯JSON的Planner格式",
            "content": json.dumps({
                "analysis": "这是对章节的分析",
                "plan": "这是内容规划",
                "queries_summary": "查询结果总结",
                "notes_for_writer": "给Writer的建议"
            }, ensure_ascii=False),
            "expected": True
        },
        {
            "name": "场景2: 非JSON的Planner文本",
            "content": """
analysis: 这是对当前章节的分析
plan: 这是详细的内容规划
queries_summary: 查询历史章节的结果
notes_for_writer: 建议Writer注意这些点
            """.strip(),
            "expected": True
        },
        {
            "name": "场景3: 正常的章节内容",
            "content": """
第一章 觉醒

清晨的阳光透过窗户洒进房间，张三缓缓睁开双眼。
今天是他人生中最重要的一天——觉醒仪式。

"该起床了。"母亲的声音从门外传来。

张三深吸一口气，翻身下床。他知道，今天之后，
他的命运将彻底改变。
            """.strip(),
            "expected": False
        },
        {
            "name": "场景4: 包含full_content的正常JSON",
            "content": json.dumps({
                "full_content": "这是正常的章节内容，讲述主角的冒险故事...",
                "writing_notes": "本章重点描写主角的心理变化"
            }, ensure_ascii=False),
            "expected": False
        },
        {
            "name": "场景5: 只有1个Planner关键词（不应触发）",
            "content": """
张三在进行深入的analysis之后，决定采取行动。
他制定了一个详细的策略。
            """.strip(),
            "expected": False
        },
        {
            "name": "场景6: 嵌套的正常JSON",
            "content": json.dumps({
                "full_content": json.dumps({
                    "story": "这是故事内容",
                    "dialogue": "这是对话"
                }, ensure_ascii=False)
            }, ensure_ascii=False),
            "expected": False
        },
        {
            "name": "场景7: Markdown代码块包裹的Planner JSON",
            "content": """
```json
{
  "analysis": "章节分析",
  "plan": "内容规划",
  "notes_for_writer": "写作建议"
}
```
            """.strip(),
            "expected": True
        },
        {
            "name": "场景8: full_content是Planner格式文本",
            "content": json.dumps({
                "full_content": "analysis: 这是分析内容\nplan: 这是规划内容\nqueries_summary: 查询结果",
                "writing_notes": "创作说明"
            }, ensure_ascii=False),
            "expected": True
        }
    ]
    
    # 运行测试
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_data, 1):
        print(f"\n{'=' * 80}")
        print(f"测试 {i}: {test['name']}")
        print(f"{'=' * 80}")
        print(f"内容前200字: {test['content'][:200]}...")
        print(f"期望结果: {'Planner格式' if test['expected'] else '正常内容'}")
        print()
        
        is_planner, reasons = detect_planner_format(test['content'], verbose=True)
        
        print()
        print(f"检测结果: {'Planner格式' if is_planner else '正常内容'}")
        if reasons:
            print(f"检测原因:")
            for reason in reasons:
                print(f"  - {reason}")
        
        if is_planner == test['expected']:
            print(f"✅ 测试通过")
            passed += 1
        else:
            print(f"❌ 测试失败")
            failed += 1
    
    # 总结
    print(f"\n{'=' * 80}")
    print(f"测试总结")
    print(f"{'=' * 80}")
    print(f"通过: {passed}/{len(test_data)}")
    print(f"失败: {failed}/{len(test_data)}")
    
    if failed == 0:
        print(f"\n🎉 所有测试通过！检测逻辑正确。")
    else:
        print(f"\n⚠️ 有 {failed} 个测试失败，需要调整检测逻辑。")
    
    return failed == 0


def interactive_test():
    """交互式测试"""
    print("\n" + "=" * 80)
    print("交互式测试模式")
    print("=" * 80)
    print("输入内容来测试检测逻辑（输入 'quit' 退出）")
    print()
    
    while True:
        print("请输入要测试的内容（可以是多行，输入空行结束）:")
        lines = []
        while True:
            line = input()
            if line.strip() == "quit":
                return
            if line == "" and lines:
                break
            lines.append(line)
        
        content = "\n".join(lines)
        if not content.strip():
            continue
        
        print("\n检测中...")
        is_planner, reasons = detect_planner_format(content, verbose=True)
        
        print()
        if is_planner:
            print("🚫 检测结果: Planner格式（应该阻止保存）")
            print("原因:")
            for reason in reasons:
                print(f"  - {reason}")
        else:
            print("✅ 检测结果: 正常内容（可以保存）")
        print()


if __name__ == "__main__":
    import sys
    
    # 运行自动测试
    success = test_cases()
    
    # 如果测试通过且用户想要交互测试
    if "--interactive" in sys.argv or "-i" in sys.argv:
        interactive_test()
    
    sys.exit(0 if success else 1)
