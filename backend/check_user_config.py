#!/usr/bin/env python3
"""检查用户的LLM配置"""
import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.llm_config import LLMConfig


async def check_user_config():
    """检查用户的LLM路由配置"""
    async with AsyncSessionLocal() as db:
        # 获取所有用户
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        if not users:
            print("❌ 数据库中没有用户")
            return
        
        print(f"\n📋 找到 {len(users)} 个用户\n")
        
        for user in users:
            print(f"{'='*60}")
            print(f"👤 用户: {user.username} (ID: {user.id})")
            print(f"   管理员: {'是' if user.is_admin else '否'}")
            
            # 获取该用户的LLM配置
            result = await db.execute(
                select(LLMConfig).where(LLMConfig.user_id == user.id)
            )
            config = result.scalar_one_or_none()
            
            if not config:
                print(f"   ❌ 未配置API密钥")
                print(f"   💡 请在前端设置页面配置: http://174.138.17.158/settings")
            else:
                print(f"   ✅ 已配置API密钥")
                
                # 尝试解析配置
                if config.llm_provider_api_key:
                    try:
                        parsed = json.loads(config.llm_provider_api_key)
                        
                        # 检查是否是新格式（路由配置）
                        if isinstance(parsed, dict) and "routes" in parsed:
                            routes = parsed.get("routes", [])
                            functions = parsed.get("functions", [])
                            
                            print(f"\n   📡 路由配置:")
                            enabled_count = 0
                            for i, route in enumerate(routes):
                                if route.get("enabled"):
                                    enabled_count += 1
                                    print(f"      路由 {i+1}: ✅ 已启用")
                                    print(f"         URL: {route.get('url', 'N/A')}")
                                    api_key = route.get('apiKey', '')
                                    if api_key:
                                        print(f"         API Key: {api_key[:20]}...{api_key[-4:]}")
                                    else:
                                        print(f"         API Key: ❌ 未设置")
                                    print(f"         模型: {route.get('model', 'N/A')}")
                                else:
                                    print(f"      路由 {i+1}: ⚪ 未启用")
                            
                            print(f"\n   🎯 AI功能配置: {len(functions)} 个功能")
                            if enabled_count == 0:
                                print(f"   ⚠️  警告: 没有启用任何路由！")
                            else:
                                print(f"   ✅ 已启用 {enabled_count} 个路由")
                        else:
                            # 旧格式
                            print(f"   📝 配置格式: 旧格式（逗号分隔的API Key）")
                            print(f"   💡 建议在前端更新为新的路由配置格式")
                    except json.JSONDecodeError:
                        print(f"   ⚠️  配置格式: 纯文本（旧格式）")
                        print(f"   💡 建议在前端更新为新的路由配置格式")
            
            print()


async def check_system_config():
    """检查系统级配置"""
    from app.models import SystemConfig
    
    async with AsyncSessionLocal() as db:
        print(f"{'='*60}")
        print(f"🔧 系统级配置（后备配置）\n")
        
        keys = ["llm.api_key", "llm.base_url", "llm.model"]
        has_config = False
        
        for key in keys:
            config = await db.get(SystemConfig, key)
            if config and config.value:
                has_config = True
                if key == "llm.api_key":
                    value = config.value
                    print(f"   {key}: {value[:20]}...{value[-4:]}")
                else:
                    print(f"   {key}: {config.value}")
            else:
                print(f"   {key}: ❌ 未设置")
        
        if not has_config:
            print(f"\n   ⚠️  系统级配置未设置")
            print(f"   💡 如果用户未配置个人API密钥，将无法使用AI功能")
        else:
            print(f"\n   ✅ 系统级配置已设置（作为后备）")


async def main():
    print("\n" + "="*60)
    print("🔍 LLM配置检查工具")
    print("="*60)
    
    await check_user_config()
    await check_system_config()
    
    print("\n" + "="*60)
    print("💡 提示:")
    print("   1. 用户配置优先级 > 系统配置")
    print("   2. 在前端设置页面配置: http://174.138.17.158/settings")
    print("   3. 至少启用一个路由，并填写完整的 URL、API Key 和模型")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

