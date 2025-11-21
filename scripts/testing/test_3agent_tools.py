#!/usr/bin/env python3
"""测试3Agent工具调用是否正常工作"""

import asyncio
import sys
sys.path.insert(0, '/home/user/novelnew/backend')

from app.db.session import get_session_factory
from app.services.ai_orchestrator_helper import _execute_tools


async def test_tools():
    """测试工具调用"""
    # 需要一个实际的project_id
    project_id = input("请输入project_id（小说ID）: ").strip()
    if not project_id:
        print("未提供project_id，退出")
        return

    chapter_number = 70

    session_factory = get_session_factory()
    async with session_factory() as session:
        print("=" * 80)
        print("测试1: search_chapters 工具")
        print("=" * 80)

        tool_calls = [{
            "id": "call_test_1",
            "function": {
                "name": "search_chapters",
                "arguments": '{"keyword": "顾清渊", "limit": 3}'
            }
        }]

        try:
            results = await _execute_tools(
                db_session=session,
                project_id=project_id,
                chapter_number=chapter_number,
                tool_calls=tool_calls
            )
            print(f"\n✅ 工具调用成功\n返回结果:\n{results[0]}\n")
        except Exception as e:
            print(f"\n❌ 工具调用失败: {e}")
            import traceback
            traceback.print_exc()

        print("\n" + "=" * 80)
        print("测试2: check_plot_consistency 工具")
        print("=" * 80)

        tool_calls = [{
            "id": "call_test_2",
            "function": {
                "name": "check_plot_consistency",
                "arguments": '{"check_items": ["顾清渊的境界"]}'
            }
        }]

        try:
            results = await _execute_tools(
                db_session=session,
                project_id=project_id,
                chapter_number=chapter_number,
                tool_calls=tool_calls
            )
            print(f"\n✅ 工具调用成功\n返回结果:\n{results[0][:500]}...\n")
        except Exception as e:
            print(f"\n❌ 工具调用失败: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("开始测试3Agent工具...")
    asyncio.run(test_tools())
    print("\n测试完成！")
