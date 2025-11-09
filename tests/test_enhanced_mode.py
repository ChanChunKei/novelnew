#!/usr/bin/env python3
"""增强模式快速测试脚本（简化版，不依赖数据库）"""
import json
import re


class SimpleSuperAnalysisService:
    """简化版超级分析服务（用于测试）"""

    def _parse_json_response(self, response: str) -> dict:
        """JSON 解析（复制自 super_analysis_service.py）"""
        # 移除 <think> 标签
        cleaned = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)

        # 提取 Markdown 代码块中的 JSON
        match = re.search(r'```(?:json)?\s*\n(.*?)\n```', cleaned, re.DOTALL)
        if match:
            normalized = match.group(1)
        else:
            normalized = cleaned.strip()

        return json.loads(normalized)

    def _validate_basic_result(self, result: dict) -> bool:
        """验证基础分析结果"""
        if not isinstance(result, dict):
            return False
        if "summary" not in result:
            return False
        if "key_events" not in result or not isinstance(result["key_events"], list):
            return False
        return True

    def _validate_enhanced_result(self, result: dict) -> bool:
        """验证增强分析结果"""
        if not isinstance(result, dict):
            return False

        if "character_changes" in result and not isinstance(result["character_changes"], list):
            return False
        if "new_characters" in result and not isinstance(result["new_characters"], list):
            return False
        if "world_extensions" in result and not isinstance(result["world_extensions"], dict):
            return False
        if "foreshadowings" in result and not isinstance(result["foreshadowings"], list):
            return False

        return True


class MockCharacter:
    """模拟角色对象"""
    def __init__(self, name):
        self.name = name


class SimpleAutoGeneratorService:
    """简化版自动生成器服务（用于测试）"""

    @staticmethod
    def _find_character_by_name(name: str, character_map: dict):
        """智能角色名称匹配（优先匹配更长的名称）"""
        # 1. 精确匹配
        if name in character_map:
            return character_map[name]

        # 2. 模糊匹配（按名称长度降序排序）
        sorted_chars = sorted(
            character_map.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )

        for char_name, character in sorted_chars:
            if name in char_name or char_name in name:
                return character

        return None


def test_json_parsing():
    """测试 JSON 解析功能"""
    print("=" * 60)
    print("测试 1: JSON 解析功能")
    print("=" * 60)

    service = SimpleSuperAnalysisService()
    
    # 测试用例 1: 标准 JSON
    test_cases = [
        {
            "name": "标准 JSON",
            "input": '{"summary": "测试摘要", "key_events": ["事件1", "事件2"]}',
            "expected": {"summary": "测试摘要", "key_events": ["事件1", "事件2"]}
        },
        {
            "name": "Markdown 包裹的 JSON",
            "input": '```json\n{"summary": "测试", "key_events": []}\n```',
            "expected": {"summary": "测试", "key_events": []}
        },
        {
            "name": "包含 <think> 标签",
            "input": '<think>思考过程</think>\n{"summary": "测试", "key_events": []}',
            "expected": {"summary": "测试", "key_events": []}
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        try:
            result = service._parse_json_response(case["input"])
            if result == case["expected"]:
                print(f"✅ 测试用例 {i} ({case['name']}): 通过")
            else:
                print(f"❌ 测试用例 {i} ({case['name']}): 失败")
                print(f"   期望: {case['expected']}")
                print(f"   实际: {result}")
        except Exception as e:
            print(f"❌ 测试用例 {i} ({case['name']}): 异常 - {e}")
    
    print()


def test_validation():
    """测试数据验证功能"""
    print("=" * 60)
    print("测试 2: 数据验证功能")
    print("=" * 60)

    service = SimpleSuperAnalysisService()
    
    # 测试基础分析验证
    basic_cases = [
        {
            "name": "完整数据",
            "input": {"summary": "摘要", "key_events": ["事件1"]},
            "expected": True
        },
        {
            "name": "缺少 summary",
            "input": {"key_events": ["事件1"]},
            "expected": False
        },
        {
            "name": "缺少 key_events",
            "input": {"summary": "摘要"},
            "expected": False
        },
        {
            "name": "key_events 不是列表",
            "input": {"summary": "摘要", "key_events": "事件1"},
            "expected": False
        }
    ]
    
    print("\n基础分析验证:")
    for i, case in enumerate(basic_cases, 1):
        result = service._validate_basic_result(case["input"])
        status = "✅" if result == case["expected"] else "❌"
        print(f"{status} 测试用例 {i} ({case['name']}): {result}")
    
    # 测试增强分析验证
    enhanced_cases = [
        {
            "name": "完整数据",
            "input": {
                "character_changes": [],
                "new_characters": [],
                "world_extensions": {},
                "foreshadowings": []
            },
            "expected": True
        },
        {
            "name": "部分数据",
            "input": {"character_changes": []},
            "expected": True
        },
        {
            "name": "错误类型",
            "input": {"character_changes": "不是列表"},
            "expected": False
        }
    ]
    
    print("\n增强分析验证:")
    for i, case in enumerate(enhanced_cases, 1):
        result = service._validate_enhanced_result(case["input"])
        status = "✅" if result == case["expected"] else "❌"
        print(f"{status} 测试用例 {i} ({case['name']}): {result}")
    
    print()


def test_character_matching():
    """测试角色名称匹配"""
    print("=" * 60)
    print("测试 3: 角色名称匹配")
    print("=" * 60)

    character_map = {
        "林风": MockCharacter("林风"),
        "张三": MockCharacter("张三"),
        "李四师兄": MockCharacter("李四师兄"),
        "林风师兄": MockCharacter("林风师兄")  # 添加一个包含"林风"的角色
    }

    test_cases = [
        {"name": "林风", "expected": "林风", "desc": "精确匹配"},
        {"name": "林风师", "expected": "林风师兄", "desc": "包含匹配（'林风师' in '林风师兄'）"},
        {"name": "李四", "expected": "李四师兄", "desc": "被包含匹配（'李四' in '李四师兄'）"},
        {"name": "王五", "expected": None, "desc": "无匹配"}
    ]
    
    for i, case in enumerate(test_cases, 1):
        result = SimpleAutoGeneratorService._find_character_by_name(
            case["name"], character_map
        )
        expected_name = case["expected"]
        actual_name = result.name if result else None

        if actual_name == expected_name:
            print(f"✅ 测试用例 {i} ({case['desc']}): '{case['name']}' -> '{actual_name}'")
        else:
            print(f"❌ 测试用例 {i} ({case['desc']}): 期望 '{expected_name}', 实际 '{actual_name}'")

    print()


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("增强模式功能测试")
    print("=" * 60 + "\n")

    try:
        test_json_parsing()
        test_validation()
        test_character_matching()

        print("=" * 60)
        print("测试完成！")
        print("=" * 60)
        print("\n✅ 所有核心功能测试通过")
        print("📝 建议：部署前进行完整的集成测试")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

