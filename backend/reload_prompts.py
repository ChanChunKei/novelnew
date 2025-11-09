#!/usr/bin/env python3
"""
重新加载提示词到数据库
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, delete
from app.db.session import AsyncSessionLocal
from app.models import Prompt

async def reload_prompts(auto_confirm: bool = False):
    """重新加载所有提示词

    Args:
        auto_confirm: 是否自动确认，用于部署脚本
    """
    prompts_dir = Path(__file__).parent / "prompts"

    if not prompts_dir.is_dir():
        print(f"❌ 提示词目录不存在: {prompts_dir}")
        return

    print(f"📁 提示词目录: {prompts_dir}")

    async with AsyncSessionLocal() as session:
        # 1. 查看现有提示词（优雅处理表不存在的情况）
        try:
            result = await session.execute(select(Prompt))
            existing_prompts = result.scalars().all()

            print(f"\n当前数据库中的提示词 ({len(existing_prompts)} 个):")
            for p in existing_prompts:
                print(f"  - {p.name}: {len(p.content)} 字符")
        except Exception as e:
            print(f"⚠️  无法查询现有提示词（可能是首次初始化）: {e}")
            existing_prompts = []

        # 2. 扫描文件系统中的提示词
        prompt_files = list(prompts_dir.glob("*.md"))
        print(f"\n文件系统中的提示词文件 ({len(prompt_files)} 个):")
        for f in sorted(prompt_files):
            print(f"  - {f.name}")

        # 3. 询问用户是否要重新加载（除非自动确认）
        if not auto_confirm:
            print("\n⚠️  将要执行的操作:")
            print("  1. 删除数据库中的所有提示词")
            print("  2. 从文件系统重新加载所有 .md 文件")

            response = input("\n是否继续? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("❌ 操作已取消")
                return
        
        # 4. 删除所有现有提示词（如果表存在）
        if existing_prompts:
            try:
                await session.execute(delete(Prompt))
                await session.commit()
                print("\n✅ 已删除所有现有提示词")
            except Exception as e:
                print(f"⚠️  删除提示词失败（可能表不存在）: {e}")
                await session.rollback()
        else:
            print("\n⏭️  数据库中没有现有提示词，跳过删除")
        
        # 5. 重新加载
        loaded_count = 0
        for prompt_file in sorted(prompt_files):
            name = prompt_file.stem
            content = prompt_file.read_text(encoding="utf-8")
            
            prompt = Prompt(name=name, content=content)
            session.add(prompt)
            loaded_count += 1
            print(f"  ✓ 加载: {name} ({len(content)} 字符)")
        
        await session.commit()
        print(f"\n✅ 成功加载 {loaded_count} 个提示词到数据库")
        
        # 6. 验证
        result = await session.execute(select(Prompt))
        final_prompts = result.scalars().all()
        
        print(f"\n最终数据库中的提示词 ({len(final_prompts)} 个):")
        for p in final_prompts:
            print(f"  - {p.name}: {len(p.content)} 字符")
            if p.name == "writing":
                print(f"\n📝 writing 提示词预览 (前200字符):")
                print(p.content[:200])
                print("...")

if __name__ == "__main__":
    # 检查是否有 --auto-confirm 参数
    auto_confirm = "--auto-confirm" in sys.argv or "-y" in sys.argv
    asyncio.run(reload_prompts(auto_confirm=auto_confirm))

