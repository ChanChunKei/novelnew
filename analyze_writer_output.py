#!/usr/bin/env python3
"""
分析 Writer Agent 的实际输出

从 conversation_history 中提取 Writer 的原始输出，分析其返回格式

使用方法：
  python3 analyze_writer_output.py [数据库路径] [章节号]

示例：
  python3 analyze_writer_output.py                    # 分析最新章节
  python3 analyze_writer_output.py /path/db.db        # 指定数据库
  python3 analyze_writer_output.py /path/db.db 1      # 分析第1章
"""

import sqlite3
import sys
import json
from pathlib import Path

def find_database():
    """自动查找数据库"""
    candidates = ["backend/storage/arboris.db", "storage/arboris.db", "arboris.db"]
    for candidate in candidates:
        db_file = Path.cwd() / candidate
        if db_file.exists():
            return str(db_file)
    return None

def analyze_writer_response(writer_content):
    """分析 Writer 的返回内容"""
    print("\n" + "-" * 80)
    print("📝 Writer 返回内容分析")
    print("-" * 80)

    # 1. 类型检查
    print(f"\n1️⃣  数据类型: {type(writer_content).__name__}")

    if isinstance(writer_content, dict):
        print(f"   字段列表: {list(writer_content.keys())}")

        # 2. 检查是否有 full_content
        if 'full_content' in writer_content:
            full_content = writer_content['full_content']
            print(f"\n2️⃣  ✅ 包含 full_content 字段")
            print(f"   类型: {type(full_content).__name__}")
            print(f"   长度: {len(str(full_content))} 字符")

            # 检查内容格式
            content_str = str(full_content)
            if content_str.strip().startswith("{"):
                print(f"   ⚠️  full_content 内容看起来是 JSON")
                try:
                    nested = json.loads(content_str)
                    print(f"   嵌套 JSON 字段: {list(nested.keys())}")
                except:
                    pass
            elif any(kw in content_str[:500] for kw in ["analysis:", "plan:", "queries_summary:"]):
                print(f"   ❌ full_content 包含 Planner 格式关键词")
            else:
                print(f"   ✅ full_content 看起来是正常的文本内容")

            # 显示预览
            print(f"\n   内容前500字:")
            print(f"   " + "·" * 76)
            preview = content_str[:500].replace('\n', '\n   ')
            print(f"   {preview}")
            print(f"   ...")
        else:
            print(f"\n2️⃣  ❌ 缺少 full_content 字段")
            print(f"   可用字段: {', '.join(writer_content.keys())}")

            # 尝试找替代字段
            for key in ['content', 'text', 'chapter_content', 'body']:
                if key in writer_content:
                    print(f"   💡 找到可能的替代字段: {key}")
                    print(f"      长度: {len(str(writer_content[key]))} 字符")

        # 3. 其他字段
        print(f"\n3️⃣  其他字段:")
        for key, value in writer_content.items():
            if key != 'full_content':
                value_type = type(value).__name__
                if isinstance(value, (str, list, dict)):
                    value_len = len(value)
                    print(f"   • {key}: {value_type} (长度: {value_len})")
                else:
                    print(f"   • {key}: {value_type} = {value}")

    elif isinstance(writer_content, str):
        print(f"   长度: {len(writer_content)} 字符")

        # 检查是否是 JSON 字符串
        if writer_content.strip().startswith("{"):
            print(f"\n2️⃣  ⚠️  返回的是 JSON 字符串，尝试解析...")
            try:
                parsed = json.loads(writer_content)
                print(f"   ✅ 解析成功")
                print(f"   字段: {list(parsed.keys())}")
                return analyze_writer_response(parsed)  # 递归分析
            except Exception as e:
                print(f"   ❌ 解析失败: {e}")

        # 检查是否包含 Planner 关键词
        elif any(kw in writer_content[:500] for kw in ["analysis:", "plan:", "queries_summary:"]):
            print(f"\n2️⃣  ❌ 内容包含 Planner 格式关键词")
        else:
            print(f"\n2️⃣  ✅ 看起来是正常的文本内容")

        # 显示预览
        print(f"\n   内容前500字:")
        print(f"   " + "·" * 76)
        preview = writer_content[:500].replace('\n', '\n   ')
        print(f"   {preview}")
        print(f"   ...")

    else:
        print(f"   ⚠️  未知类型: {type(writer_content)}")

# 解析参数
db_path = sys.argv[1] if len(sys.argv) > 1 else find_database()
chapter_num = int(sys.argv[2]) if len(sys.argv) > 2 else None

if not db_path:
    print("❌ 未找到数据库")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查询章节
if chapter_num:
    cursor.execute("""
    SELECT c.chapter_number, p.title, cv.content, cv.metadata, cv.created_at
    FROM chapters c
    JOIN chapter_versions cv ON c.selected_version_id = cv.id
    JOIN novel_projects p ON c.project_id = p.id
    WHERE c.chapter_number = ?
    ORDER BY cv.created_at DESC
    LIMIT 1
    """, (chapter_num,))
else:
    cursor.execute("""
    SELECT c.chapter_number, p.title, cv.content, cv.metadata, cv.created_at
    FROM chapters c
    JOIN chapter_versions cv ON c.selected_version_id = cv.id
    JOIN novel_projects p ON c.project_id = p.id
    ORDER BY cv.created_at DESC
    LIMIT 1
    """)

result = cursor.fetchone()

if not result:
    print("❌ 未找到章节")
    sys.exit(1)

chapter_num, project_title, content, metadata, created = result

print("\n" + "=" * 80)
print(f"🔍 分析第 {chapter_num} 章 - {project_title}")
print(f"⏰ 创建时间: {created}")
print("=" * 80)

# 解析 metadata
if not metadata:
    print("\n❌ 没有 metadata 信息，无法分析 Writer 输出")
    conn.close()
    sys.exit(1)

try:
    meta = json.loads(metadata)

    if "conversation_history" not in meta:
        print("\n❌ metadata 中没有 conversation_history")
        conn.close()
        sys.exit(1)

    history = meta["conversation_history"]

    # 提取所有 Writer 的输出
    writer_outputs = []
    for idx, item in enumerate(history, 1):
        if item.get("agent") == "writer":
            iteration = item.get("iteration", "")
            content_data = item.get("content", {})
            writer_outputs.append({
                'index': idx,
                'iteration': iteration,
                'content': content_data
            })

    if not writer_outputs:
        print("\n❌ conversation_history 中没有找到 Writer 的输出")
        conn.close()
        sys.exit(1)

    print(f"\n找到 {len(writer_outputs)} 次 Writer 调用")

    # 分析每次 Writer 输出
    for output in writer_outputs:
        print("\n" + "=" * 80)
        print(f"📊 第 {output['index']} 步 - Writer 输出（迭代 {output['iteration']}）")
        print("=" * 80)

        analyze_writer_response(output['content'])

    # 分析最终存储的内容
    print("\n" + "=" * 80)
    print("📄 最终存储的章节内容")
    print("=" * 80)

    print(f"\n长度: {len(content)} 字符")

    # 检查格式
    issues = []
    if content.strip().startswith("{") and content.strip().endswith("}"):
        try:
            json.loads(content)
            issues.append("❌ 是纯 JSON 格式")
        except:
            pass

    if any(kw in content[:500] for kw in ["analysis:", "plan:", "queries_summary:", "notes_for_writer:"]):
        issues.append("❌ 包含 Planner 格式关键词")

    if issues:
        print("\n问题:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n✅ 格式正常")

    print(f"\n内容前500字:")
    print("-" * 80)
    print(content[:500])
    print("...")

    # 给出建议
    print("\n" + "=" * 80)
    print("💡 诊断结论")
    print("=" * 80)

    # 检查 Writer 输出和最终内容的一致性
    if writer_outputs:
        last_writer = writer_outputs[-1]['content']

        if isinstance(last_writer, dict) and 'full_content' in last_writer:
            writer_content = last_writer['full_content']
            if content == writer_content:
                print("\n✅ Writer 输出的 full_content 与最终存储内容一致")
            else:
                print("\n⚠️  Writer 输出的 full_content 与最终存储内容不一致")
                print("   可能原因：")
                print("   1. 内容提取逻辑有问题")
                print("   2. 存储时被修改")
        elif isinstance(last_writer, dict):
            print("\n❌ Writer 返回了 dict 但没有 full_content 字段")
            print(f"   实际字段: {list(last_writer.keys())}")
            print("   建议：检查 Writer 的 prompt 和输出解析逻辑")
        elif isinstance(last_writer, str):
            if last_writer == content:
                print("\n✅ Writer 直接返回字符串，与最终内容一致")
            else:
                print("\n⚠️  Writer 返回字符串，但与最终内容不一致")

except json.JSONDecodeError as e:
    print(f"❌ Metadata 解析失败: {e}")
except Exception as e:
    print(f("❌ 分析失败: {e}")

conn.close()

print("\n" + "=" * 80)
print("✅ 分析完成")
print("=" * 80 + "\n")
