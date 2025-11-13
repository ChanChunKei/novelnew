#!/usr/bin/env python3
"""
诊断章节生成问题 - 灵活版本
用法: python3 diagnose_chapter_issue.py [数据库路径]
"""
import sqlite3
import json
import sys
from pathlib import Path

def diagnose_database(db_path: str):
    """诊断数据库中的章节问题"""

    if not Path(db_path).exists():
        print(f"❌ 数据库文件不存在: {db_path}")
        return False

    print(f"🔍 正在检查数据库: {db_path}")
    print()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 检查章节总数
    cursor.execute("SELECT COUNT(*) FROM chapters")
    total_chapters = cursor.fetchone()[0]
    print(f"📊 数据库中共有 {total_chapters} 个章节")

    if total_chapters == 0:
        print("❌ 数据库为空，没有章节数据")
        conn.close()
        return False

    # 检查版本总数
    cursor.execute("SELECT COUNT(*) FROM chapter_versions")
    total_versions = cursor.fetchone()[0]
    print(f"📊 数据库中共有 {total_versions} 个章节版本")
    print()

    # 获取最新的 5 个章节版本
    cursor.execute("""
        SELECT
            cv.id,
            cv.chapter_id,
            cv.content,
            cv.metadata,
            cv.created_at,
            c.chapter_number
        FROM chapter_versions cv
        JOIN chapters c ON cv.chapter_id = c.id
        ORDER BY cv.created_at DESC
        LIMIT 5
    """)

    rows = cursor.fetchall()

    print("=" * 80)
    print("📋 最新的 5 个章节版本")
    print("=" * 80)

    for idx, row in enumerate(rows, 1):
        version_id, chapter_id, content, metadata_str, created_at, chapter_number = row

        print(f"\n{idx}. 第 {chapter_number} 章 (版本ID: {version_id})")
        print(f"   创建时间: {created_at}")
        print(f"   内容长度: {len(content) if content else 0} 字符")

        if content:
            # 检查是否包含 Planner 关键词
            planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
            found_keywords = []
            content_preview = content[:300] if len(content) > 300 else content

            for kw in planner_keywords:
                if f'"{kw}":' in content_preview or f"'{kw}':" in content_preview:
                    found_keywords.append(kw)

            if found_keywords:
                print(f"   ⚠️  检测到 Planner 格式关键词: {found_keywords}")
            else:
                print(f"   ✅ 正常章节内容")

    # 详细分析最新的一章
    if rows:
        print("\n" + "=" * 80)
        print("🔍 详细分析最新章节")
        print("=" * 80)

        version_id, chapter_id, content, metadata_str, created_at, chapter_number = rows[0]

        print(f"\n第 {chapter_number} 章 (版本ID: {version_id})")
        print(f"创建时间: {created_at}")
        print()

        # 分析内容
        if content:
            print("📝 内容前 500 字符:")
            print("-" * 80)
            print(content[:500])
            print("-" * 80)

            # 检查 Planner 格式
            planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
            found_keywords = []
            for kw in planner_keywords:
                if f'"{kw}":' in content[:500]:
                    found_keywords.append(kw)

            if found_keywords:
                print(f"\n❌ 问题确认：内容包含 Planner 格式字段: {found_keywords}")

        # 分析 conversation_history
        if metadata_str:
            print("\n" + "=" * 80)
            print("🔍 分析生成过程")
            print("=" * 80)

            try:
                metadata = json.loads(metadata_str)
                conversation_history = metadata.get("conversation_history", [])

                if conversation_history:
                    print(f"\n对话轮次: {len(conversation_history)}")

                    # 找 Planner 输出
                    for item in conversation_history:
                        if item.get("agent") == "planner":
                            print("\n" + "-" * 80)
                            print("Planner 输出:")
                            print("-" * 80)
                            planner_content = item.get("content")
                            print(json.dumps(planner_content, ensure_ascii=False, indent=2)[:600])
                            print("...")
                            break

                    # 找 Writer 输出
                    writer_items = [item for item in conversation_history if item.get("agent") == "writer"]
                    if writer_items:
                        print("\n" + "-" * 80)
                        print(f"Writer 输出 (共 {len(writer_items)} 轮):")
                        print("-" * 80)

                        for idx, item in enumerate(writer_items, 1):
                            writer_content = item.get("content")
                            print(f"\n第 {idx} 轮:")
                            if isinstance(writer_content, dict):
                                full_content = writer_content.get("full_content", "")
                                if full_content:
                                    preview = full_content[:300]
                                    # 检查是否是 Planner 格式
                                    if any(f'"{kw}":' in preview for kw in planner_keywords):
                                        print("❌ Writer 返回了 Planner 格式！")
                                    else:
                                        print("✅ Writer 返回了正常内容")
                                    print(f"前 200 字符: {full_content[:200]}")
                            else:
                                print(f"内容: {str(writer_content)[:200]}")

            except Exception as e:
                print(f"⚠️  解析 metadata 失败: {e}")

    conn.close()
    return True


if __name__ == "__main__":
    # 尝试多个可能的数据库路径
    possible_paths = [
        "backend/storage/arboris.db",
        "storage/arboris.db",
        "../backend/storage/arboris.db",
        "/home/user/novelnew/backend/storage/arboris.db",
    ]

    # 如果命令行提供了路径，使用它
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        diagnose_database(db_path)
    else:
        # 自动尝试多个路径
        print("🔍 正在搜索数据库文件...")
        print()

        found = False
        for path in possible_paths:
            if Path(path).exists():
                print(f"✅ 找到数据库: {path}")
                print()
                diagnose_database(path)
                found = True
                break

        if not found:
            print("❌ 未找到数据库文件")
            print()
            print("请手动指定数据库路径:")
            print("  python3 diagnose_chapter_issue.py <数据库路径>")
            print()
            print("例如:")
            print("  python3 diagnose_chapter_issue.py ~/novel/backend/storage/arboris.db")
