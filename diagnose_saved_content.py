#!/usr/bin/env python3
"""
诊断ChapterVersion中实际保存的内容
检查是否有Planner格式被错误保存
"""

import asyncio
import json
import sys
from sqlalchemy import select, desc

sys.path.insert(0, '/home/user/novelnew/backend')

from app.db.session import get_session_factory
from app.models.novel import ChapterVersion, Chapter


async def diagnose():
    """检查最近的5个章节版本"""

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 查询最近生成的10个版本
        result = await session.execute(
            select(ChapterVersion)
            .join(Chapter)
            .order_by(desc(ChapterVersion.created_at))
            .limit(10)
        )
        versions = result.scalars().all()

        print("=" * 80)
        print("最近生成的10个章节版本内容诊断：")
        print("=" * 80)

        planner_count = 0
        normal_count = 0

        for idx, v in enumerate(versions, 1):
            print(f"\n{'='*80}")
            print(f"版本 {idx}:")
            print(f"  章节ID: {v.chapter_id}")
            print(f"  版本ID: {v.id}")
            print(f"  创建时间: {v.created_at}")

            # 分析content字段
            content = v.content
            print(f"\n  📄 Content字段:")
            print(f"    类型: {type(content)}")
            print(f"    长度: {len(content) if content else 0}")

            # 检查是否是JSON
            is_json = False
            is_planner = False
            try:
                if content and (content.strip().startswith('{') or content.strip().startswith('[')):
                    content_parsed = json.loads(content)
                    is_json = True
                    print(f"    ⚠️  Content是JSON！")

                    if isinstance(content_parsed, dict):
                        keys = list(content_parsed.keys())
                        print(f"    JSON包含字段: {keys}")

                        # 检查是否是Planner格式
                        planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
                        found = [k for k in planner_keywords if k in content_parsed]

                        if len(found) >= 2:
                            is_planner = True
                            planner_count += 1
                            print(f"    ❌❌❌ **这是Planner格式！** 包含字段: {found}")
                            print(f"    Planner内容预览:")
                            if "analysis" in content_parsed:
                                print(f"      analysis: {str(content_parsed['analysis'])[:200]}...")
                            if "plan" in content_parsed:
                                print(f"      plan: {str(content_parsed['plan'])[:200]}...")
                        else:
                            print(f"    ℹ️  是JSON但不是Planner格式")
            except (json.JSONDecodeError, TypeError):
                pass

            if not is_json:
                normal_count += 1
                print(f"    ✅ Content是纯文本（正常）")
                print(f"    前200字预览: {content[:200] if content else ''}...")

            # 分析metadata
            print(f"\n  📊 Metadata字段:")
            if v.metadata_:
                print(f"    存在metadata")
                if isinstance(v.metadata_, dict):
                    if "conversation_history" in v.metadata_:
                        history = v.metadata_["conversation_history"]
                        print(f"    conversation_history包含 {len(history)} 个对话记录")
                        agents = [h.get("agent", "unknown") for h in history]
                        print(f"    Agent顺序: {' → '.join(agents)}")
            else:
                print(f"    无metadata")

        print(f"\n" + "=" * 80)
        print(f"统计结果:")
        print(f"  ✅ 正常保存(纯文本): {normal_count}")
        print(f"  ❌ 错误保存(Planner格式): {planner_count}")
        print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(diagnose())
    except ModuleNotFoundError as e:
        print(f"❌ 缺少依赖模块: {e}")
        print(f"提示: 需要在backend目录下运行,或安装相关依赖")
    except Exception as e:
        print(f"❌ 执行出错: {e}")
        import traceback
        traceback.print_exc()
