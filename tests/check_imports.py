#!/usr/bin/env python3
"""检查所有导入是否正确"""
import sys
import os

# 添加 backend 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

print("🔍 检查导入...")

errors = []

# 检查 auto_generator_service
try:
    print("  检查 auto_generator_service...")
    from app.services import auto_generator_service
    print("  ✅ auto_generator_service 导入成功")
except Exception as e:
    errors.append(f"❌ auto_generator_service: {e}")
    print(f"  ❌ auto_generator_service: {e}")

# 检查 super_analysis_service
try:
    print("  检查 super_analysis_service...")
    from app.services import super_analysis_service
    print("  ✅ super_analysis_service 导入成功")
except Exception as e:
    errors.append(f"❌ super_analysis_service: {e}")
    print(f"  ❌ super_analysis_service: {e}")

# 检查 json_utils
try:
    print("  检查 json_utils...")
    from app.utils import json_utils
    print("  ✅ json_utils 导入成功")
except Exception as e:
    errors.append(f"❌ json_utils: {e}")
    print(f"  ❌ json_utils: {e}")

# 检查 llm_service
try:
    print("  检查 llm_service...")
    from app.services import llm_service
    print("  ✅ llm_service 导入成功")
except Exception as e:
    errors.append(f"❌ llm_service: {e}")
    print(f"  ❌ llm_service: {e}")

print("\n" + "="*50)
if errors:
    print(f"❌ 发现 {len(errors)} 个错误:")
    for error in errors:
        print(f"  {error}")
    sys.exit(1)
else:
    print("✅ 所有导入检查通过！")
    sys.exit(0)

