#!/usr/bin/env python3
"""
检查并修复数据库中错误保存的Planner内容

问题：在修复之前，某些章节的content字段可能保存了Planner格式的JSON
修复：检测并清理这些错误数据
"""

import asyncio
import json
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 添加项目路径
sys.path.insert(0, '/home/user/novelnew/backend')

from app.db.session import get_session_factory
from app.models.novel import ChapterVersion


async def check_and_fix_planner_content():
    """检查并修复错误的Planner内容"""

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 查询所有章节版本
        result = await session.execute(select(ChapterVersion))
        versions = result.scalars().all()

        print(f"共找到 {len(versions)} 个章节版本")
        print("=" * 80)

        planner_count = 0
        fixed_count = 0

        for version in versions:
            content = version.content

            # 检查是否是Planner格式的JSON
            is_planner_format = False
            planner_fields = []

            try:
                # 尝试解析为JSON
                content_json = json.loads(content)

                # 检查是否包含Planner特征字段
                planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
                found_fields = [k for k in planner_keywords if k in content_json]

                if len(found_fields) >= 2 and "full_content" not in content_json:
                    is_planner_format = True
                    planner_fields = found_fields

            except (json.JSONDecodeError, TypeError):
                # 不是JSON，跳过
                pass

            if is_planner_format:
                planner_count += 1
                print(f"\n❌ 发现Planner格式内容:")
                print(f"  章节ID: {version.chapter_id}")
                print(f"  版本ID: {version.id}")
                print(f"  包含字段: {planner_fields}")
                print(f"  内容前200字: {content[:200]}...")

                # 检查metadata中是否有正确的内容
                if version.metadata_:
                    metadata = version.metadata_ if isinstance(version.metadata_, dict) else {}

                    # 查找conversation_history中的writer内容
                    writer_content = None
                    if "conversation_history" in metadata:
                        for item in metadata["conversation_history"]:
                            if item.get("agent") == "writer":
                                writer_data = item.get("content", {})
                                if isinstance(writer_data, dict):
                                    writer_content = writer_data.get("full_content")
                                    break

                    if writer_content:
                        print(f"  ✅ 在metadata中找到正确的Writer内容（长度: {len(writer_content)}）")
                        print(f"  是否修复? (y/n): ", end="")

                        # 自动修复模式，直接修复
                        print("自动修复中...")
                        version.content = writer_content
                        fixed_count += 1
                        print(f"  ✅ 已修复")
                    else:
                        print(f"  ⚠️  metadata中未找到正确的Writer内容，需要重新生成")
                else:
                    print(f"  ⚠️  没有metadata，需要重新生成")

        if fixed_count > 0:
            print("\n" + "=" * 80)
            print(f"准备提交 {fixed_count} 个修复...")
            await session.commit()
            print(f"✅ 已修复 {fixed_count} 个章节版本")

        print("\n" + "=" * 80)
        print(f"检查完成:")
        print(f"  总版本数: {len(versions)}")
        print(f"  Planner格式: {planner_count}")
        print(f"  已修复: {fixed_count}")
        print(f"  需要重新生成: {planner_count - fixed_count}")
        print("=" * 80)


if __name__ == "__main__":
    print("开始检查数据库中的Planner格式内容...")
    asyncio.run(check_and_fix_planner_content())
