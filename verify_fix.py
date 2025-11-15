#!/usr/bin/env python3
"""验证 _normalize_version_content 修复是否正确"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.novel_service import _normalize_version_content

# 测试案例1: 正常的3Agent返回（content是字符串，metadata是字典）
print("=" * 80)
print("测试案例1: 正常的3Agent返回")
print("=" * 80)

content_str = "这是章节正文内容..."
metadata_dict = {
    "conversation_history": [
        {"agent": "planner", "content": {"analysis": "...", "plan": "..."}},
        {"agent": "writer", "content": {"full_content": "writer的内容"}},
    ],
    "iterations": 2,
    "final_score": 85
}

result = _normalize_version_content(content_str, metadata_dict)
print(f"✅ 结果: {result}")
assert result == content_str, "应该返回content_str，而不是metadata"
print("✅ 测试通过：正确从raw_content提取内容，忽略metadata\n")

# 测试案例2: content是dict（包含full_content字段）
print("=" * 80)
print("测试案例2: content是dict（包含full_content字段）")
print("=" * 80)

content_dict = {
    "full_content": "这是完整的章节内容...",
    "summary": "章节摘要",
    "metadata": {
        "conversation_history": [],
        "iterations": 1
    }
}

result = _normalize_version_content(content_dict, None)
print(f"✅ 结果: {result}")
assert result == "这是完整的章节内容...", "应该提取full_content字段"
print("✅ 测试通过：正确提取full_content字段\n")

# 测试案例3: content是dict（只有content字段）
print("=" * 80)
print("测试案例3: content是dict（只有content字段）")
print("=" * 80)

content_dict = {
    "content": "这是章节内容...",
}

result = _normalize_version_content(content_dict, None)
print(f"✅ 结果: {result}")
assert result == "这是章节内容...", "应该提取content字段"
print("✅ 测试通过：正确提取content字段\n")

# 测试案例4: content是dict但缺少有效字段（应该抛出异常）
print("=" * 80)
print("测试案例4: content是Planner格式dict（应该抛出异常）")
print("=" * 80)

planner_dict = {
    "analysis": "章节分析...",
    "plan": "内容规划...",
    "notes_for_writer": "写作建议..."
}

try:
    result = _normalize_version_content(planner_dict, None)
    print(f"❌ 测试失败：应该抛出异常，但返回了 {result}")
    sys.exit(1)
except ValueError as e:
    print(f"✅ 正确抛出异常: {e}")
    print("✅ 测试通过：正确拒绝Planner格式的内容\n")

# 测试案例5: 即使metadata包含内容，也不应该从中提取
print("=" * 80)
print("测试案例5: metadata包含内容字段（不应该被提取）")
print("=" * 80)

content_str = "正确的章节内容"
metadata_with_content = {
    "full_content": "这是metadata里的错误内容",  # 不应该被提取
    "conversation_history": []
}

result = _normalize_version_content(content_str, metadata_with_content)
print(f"✅ 结果: {result}")
assert result == "正确的章节内容", "应该忽略metadata中的内容"
print("✅ 测试通过：正确忽略metadata中的内容字段\n")

print("=" * 80)
print("🎉 所有测试通过！修复正确！")
print("=" * 80)
