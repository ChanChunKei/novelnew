#!/usr/bin/env python3
"""
诊断3Agent模式为什么仍然保存Planner内容
"""

import asyncio
import json
import sys
from sqlalchemy import select

sys.path.insert(0, '/home/user/novelnew/backend')

from app.db.session import get_session_factory
from app.models.novel import ChapterVersion, Chapter


async def diagnose():
    """诊断最近的章节版本"""

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 查询最近生成的5个版本
        result = await session.execute(
            select(ChapterVersion)
            .join(Chapter)
            .order_by(ChapterVersion.created_at.desc())
            .limit(5)
        )
        versions = result.scalars().all()

        print("=" * 80)
        print("最近生成的5个章节版本分析：")
        print("=" * 80)

        for idx, v in enumerate(versions, 1):
            print(f"\n{'='*80}")
            print(f"版本 {idx}:")
            print(f"  章节ID: {v.chapter_id}")
            print(f"  版本ID: {v.id}")
            print(f"  创建时间: {v.created_at}")
            print(f"  版本标签: {v.version_label}")

            # 分析content
            content = v.content
            print(f"\n  📄 Content字段分析:")
            print(f"    类型: {type(content)}")
            print(f"    长度: {len(content) if content else 0}")

            # 检查是否是Planner格式
            is_planner = False
            try:
                content_json = json.loads(content)
                if isinstance(content_json, dict):
                    keys = list(content_json.keys())
                    print(f"    ⚠️  Content是JSON dict，包含字段: {keys}")

                    planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
                    found = [k for k in planner_keywords if k in content_json]

                    if len(found) >= 2 and "full_content" not in content_json:
                        is_planner = True
                        print(f"    ❌ **这是Planner格式！** 包含: {found}")
                    elif "full_content" in content_json:
                        print(f"    ✅ 包含full_content字段")
                        full_content_value = content_json["full_content"]
                        print(f"       full_content类型: {type(full_content_value)}")
                        print(f"       full_content长度: {len(full_content_value) if isinstance(full_content_value, str) else 'N/A'}")
                        print(f"       full_content前200字: {str(full_content_value)[:200]}...")
            except (json.JSONDecodeError, TypeError):
                print(f"    ✅ Content不是JSON，是纯文本")
                print(f"    前300字预览: {content[:300]}...")

            # 分析metadata
            print(f"\n  📊 Metadata字段分析:")
            if v.metadata_:
                metadata = v.metadata_
                print(f"    类型: {type(metadata)}")
                if isinstance(metadata, dict):
                    print(f"    包含字段: {list(metadata.keys())}")

                    # 检查conversation_history
                    if "conversation_history" in metadata:
                        history = metadata["conversation_history"]
                        print(f"    conversation_history长度: {len(history)}")

                        for item in history:
                            agent = item.get("agent", "unknown")
                            print(f"      - {agent}: ", end="")

                            if agent == "planner":
                                planner_content = item.get("content", {})
                                if isinstance(planner_content, dict):
                                    print(f"keys={list(planner_content.keys())}")
                            elif agent == "writer":
                                writer_content = item.get("content", {})
                                if isinstance(writer_content, dict):
                                    print(f"keys={list(writer_content.keys())}")
                                else:
                                    print(f"type={type(writer_content)}")
                            else:
                                print(f"type={type(item.get('content'))}")
            else:
                print(f"    无metadata")

            if is_planner:
                print(f"\n  ⚠️⚠️⚠️  问题确认：这个版本的content字段保存的是Planner格式！")

        print("\n" + "=" * 80)
        print("诊断完成")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(diagnose())
