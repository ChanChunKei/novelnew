#!/usr/bin/env python3
"""Quick Gemini API Key validation test"""

import sys

try:
    import google.generativeai as genai
except ImportError:
    print("❌ 缺少依赖: google-generativeai")
    print("请运行: pip install google-generativeai")
    sys.exit(1)

# Test the provided API key
API_KEY = "AIzaSyA5t2XnnCMsCg7SE-odHhX1o5gHIxX2kBQ"

print("🔍 正在测试 Gemini API Key...")
print(f"📋 API Key: {API_KEY[:10]}...{API_KEY[-4:]}")
print()

try:
    # Configure the API
    genai.configure(api_key=API_KEY)

    # Try to list models (this validates the key is valid)
    print("📡 尝试连接到 Google AI...")
    models = list(genai.list_models())

    print()
    print("=" * 60)
    print("✅ API Key 有效！")
    print(f"✅ 已成功连接到 Google AI")
    print(f"📚 可用模型数量: {len(models)}")
    print("=" * 60)
    print()

    # Now try to access corpora (Semantic Retrieval API)
    try:
        from google.generativeai import retriever
        corpora_list = list(retriever.list_corpora())
        corpus_count = len(corpora_list)

        print(f"📚 Semantic Retrieval API 可用")
        print(f"📚 找到 {corpus_count} 个 Corpus")
        print()

        if corpus_count > 0:
            print("已有的 Corpus 列表:")
            for corpus in corpora_list:
                print(f"  - {corpus.name} (display_name: {corpus.display_name})")
        else:
            print("💡 提示: 当前没有 Corpus，这是正常的。")
            print("   当你生成第一章内容时，系统会自动创建 Corpus。")
    except Exception as e:
        print(f"⚠️  Semantic Retrieval API 不可用: {e}")
        print("💡 这可能是因为:")
        print("   1. API Key 没有 Semantic Retrieval 权限")
        print("   2. 需要在 Google AI Studio 中启用该功能")
        print("   但基础 Gemini API 功能正常。")

    print()
    print("🎉 测试成功！API Key 可用。")
    sys.exit(0)

except Exception as e:
    print()
    print("=" * 60)
    print("❌ API Key 测试失败")
    print("=" * 60)
    print(f"错误类型: {type(e).__name__}")
    print(f"错误详情: {str(e)}")
    print()

    # Provide helpful hints
    if "API key not valid" in str(e) or "PERMISSION_DENIED" in str(e):
        print("💡 可能的原因:")
        print("  1. API Key 已过期或被撤销")
        print("  2. API Key 没有 Semantic Retrieval API 权限")
        print("  3. API Key 格式不正确")
        print()
        print("🔧 解决方案:")
        print("  访问 https://aistudio.google.com/app/apikey 重新生成 API Key")
    elif "quota" in str(e).lower():
        print("💡 可能的原因:")
        print("  API 配额已用完（免费额度: 1500次/天）")
    else:
        print("💡 请检查网络连接，或稍后重试")

    sys.exit(1)
