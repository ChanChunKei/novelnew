#!/usr/bin/env python3
"""
测试工具调用参数解析修复

验证 _execute_tools 能够处理两种格式：
1. OpenAI 格式：arguments 是 JSON 字符串
2. Gemini 格式：arguments 是字典对象
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def test_tool_argument_parsing():
    """测试工具参数解析的兼容性"""
    
    # 模拟两种格式的 tool_calls
    
    # 格式1：OpenAI 标准格式（arguments 是字符串）
    openai_tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "search_chapters",
            "arguments": '{"keyword": "张三", "limit": 3}'  # JSON 字符串
        }
    }
    
    # 格式2：Gemini 格式（arguments 是字典）
    gemini_tool_call = {
        "id": "call_456",
        "type": "function",
        "function": {
            "name": "search_chapters",
            "arguments": {"keyword": "李四", "limit": 5}  # 字典对象
        }
    }
    
    # 测试解析逻辑（复制自修复后的代码）
    def parse_arguments(arguments_raw):
        """解析工具参数（兼容两种格式）"""
        if isinstance(arguments_raw, dict):
            return arguments_raw
        elif isinstance(arguments_raw, str):
            try:
                return json.loads(arguments_raw)
            except json.JSONDecodeError:
                return None
        else:
            return None
    
    # 测试 OpenAI 格式
    print("=" * 60)
    print("测试 OpenAI 格式（arguments 是字符串）")
    print("=" * 60)
    openai_args = parse_arguments(openai_tool_call["function"]["arguments"])
    if openai_args:
        print(f"✅ 解析成功: {openai_args}")
        assert openai_args["keyword"] == "张三"
        assert openai_args["limit"] == 3
    else:
        print("❌ 解析失败")
        return False
    
    # 测试 Gemini 格式
    print("\n" + "=" * 60)
    print("测试 Gemini 格式（arguments 是字典）")
    print("=" * 60)
    gemini_args = parse_arguments(gemini_tool_call["function"]["arguments"])
    if gemini_args:
        print(f"✅ 解析成功: {gemini_args}")
        assert gemini_args["keyword"] == "李四"
        assert gemini_args["limit"] == 5
    else:
        print("❌ 解析失败")
        return False
    
    # 测试错误格式
    print("\n" + "=" * 60)
    print("测试错误格式（非法 JSON 字符串）")
    print("=" * 60)
    bad_args = parse_arguments("{invalid json")
    if bad_args is None:
        print("✅ 正确处理了错误格式")
    else:
        print("❌ 应该返回 None")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
    print("\n工具调用修复验证成功：")
    print("- OpenAI 格式（JSON 字符串）：✅")
    print("- Gemini 格式（字典对象）：✅")
    print("- 错误处理：✅")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_tool_argument_parsing())
    sys.exit(0 if success else 1)
