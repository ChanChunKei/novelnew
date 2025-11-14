#!/usr/bin/env python3
"""
快速检查 full_content 保存问题

这是一个快速诊断工具，用于立即检查特定章节或最新章节的问题。

使用方法：
  python3 quick_check_full_content.py              # 检查最新章节
  python3 quick_check_full_content.py 5            # 检查第5章
  python3 quick_check_full_content.py --all        # 检查所有章节
  python3 quick_check_full_content.py --summary    # 生成问题总结报告
"""

import sys
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

# ============================================================================
# 核心检测逻辑
# ============================================================================

def is_planner_format(content: str) -> tuple[bool, List[str]]:
    """
    检测内容是否是Planner格式
    返回: (是否是Planner格式, 发现的关键词列表)
    """
    if not content:
        return False, []
    
    planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
    found_keywords = []
    
    # 检查JSON格式
    content_stripped = content.strip()
    if content_stripped.startswith("{") and content_stripped.endswith("}"):
        try:
            parsed = json.loads(content_stripped)
            found_keywords = [kw for kw in planner_keywords if kw in parsed]
            if len(found_keywords) >= 2:
                return True, found_keywords
        except json.JSONDecodeError:
            pass
    
    # 检查文本格式（前1000字）
    check_content = content[:1000]
    text_keywords = []
    for kw in planner_keywords:
        if f'{kw}:' in check_content or f'"{kw}":' in check_content:
            text_keywords.append(kw)
    
    if len(text_keywords) >= 2:
        return True, text_keywords
    
    return False, []

def find_database() -> Optional[str]:
    """查找数据库文件"""
    candidates = [
        "backend/storage/arboris.db",
        "storage/arboris.db",
        "arboris.db"
    ]
    for candidate in candidates:
        db_file = Path.cwd() / candidate
        if db_file.exists():
            return str(db_file)
    return None

# ============================================================================
# 检查函数
# ============================================================================

def check_chapter(conn: sqlite3.Connection, chapter_num: Optional[int] = None) -> Dict:
    """检查单个章节"""
    cursor = conn.cursor()
    
    if chapter_num:
        cursor.execute("""
        SELECT 
            c.id,
            c.chapter_number, 
            p.title,
            cv.content, 
            cv.metadata,
            cv.created_at,
            cv.version_label
        FROM chapters c
        JOIN chapter_versions cv ON c.selected_version_id = cv.id
        JOIN novel_projects p ON c.project_id = p.id
        WHERE c.chapter_number = ?
        ORDER BY cv.created_at DESC
        LIMIT 1
        """, (chapter_num,))
    else:
        cursor.execute("""
        SELECT 
            c.id,
            c.chapter_number, 
            p.title,
            cv.content, 
            cv.metadata,
            cv.created_at,
            cv.version_label
        FROM chapters c
        JOIN chapter_versions cv ON c.selected_version_id = cv.id
        JOIN novel_projects p ON c.project_id = p.id
        ORDER BY cv.created_at DESC
        LIMIT 1
        """)
    
    row = cursor.fetchone()
    if not row:
        return None
    
    chapter_id, chapter_num, project_title, content, metadata_str, created, version = row
    
    # 检测Planner格式
    is_planner, keywords = is_planner_format(content)
    
    # 解析metadata
    has_metadata = bool(metadata_str)
    iterations = None
    score = None
    writer_count = 0
    
    if metadata_str:
        try:
            metadata = json.loads(metadata_str)
            iterations = metadata.get('iterations')
            score = metadata.get('final_score')
            if 'conversation_history' in metadata:
                writer_count = sum(
                    1 for item in metadata['conversation_history'] 
                    if item.get('agent') == 'writer'
                )
        except:
            pass
    
    return {
        'chapter_id': chapter_id,
        'chapter_number': chapter_num,
        'project_title': project_title,
        'version': version,
        'created_at': created,
        'content_length': len(content) if content else 0,
        'content_preview': content[:200] if content else "",
        'is_planner_format': is_planner,
        'planner_keywords': keywords,
        'has_metadata': has_metadata,
        'iterations': iterations,
        'score': score,
        'writer_count': writer_count
    }

def check_all_chapters(conn: sqlite3.Connection) -> List[Dict]:
    """检查所有章节"""
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT DISTINCT c.chapter_number
    FROM chapters c
    ORDER BY c.chapter_number
    """)
    
    chapter_numbers = [row[0] for row in cursor.fetchall()]
    
    results = []
    for chapter_num in chapter_numbers:
        result = check_chapter(conn, chapter_num)
        if result:
            results.append(result)
    
    return results

# ============================================================================
# 输出函数
# ============================================================================

def print_chapter_result(result: Dict, detailed: bool = False):
    """打印单个章节的检查结果"""
    chapter_num = result['chapter_number']
    
    # 状态图标
    if result['is_planner_format']:
        status = "❌"
        status_text = "问题"
    else:
        status = "✅"
        status_text = "正常"
    
    print(f"\n{status} 第 {chapter_num} 章 - {status_text}")
    print(f"   时间: {result['created_at']}")
    print(f"   长度: {result['content_length']} 字符")
    
    if result['is_planner_format']:
        print(f"   ⚠️  检测到 Planner 格式！")
        print(f"   关键词: {', '.join(result['planner_keywords'])}")
    
    if result['has_metadata']:
        info_parts = []
        if result['iterations']:
            info_parts.append(f"迭代{result['iterations']}次")
        if result['score']:
            info_parts.append(f"评分{result['score']}")
        if result['writer_count']:
            info_parts.append(f"{result['writer_count']}次Writer调用")
        if info_parts:
            print(f"   Metadata: {', '.join(info_parts)}")
    
    if detailed:
        print(f"\n   内容预览:")
        preview = result['content_preview'].replace('\n', ' ')
        print(f"   {preview}...")

def print_summary(results: List[Dict]):
    """打印总结报告"""
    total = len(results)
    problematic = [r for r in results if r['is_planner_format']]
    normal = [r for r in results if not r['is_planner_format']]
    
    with_metadata = [r for r in results if r['has_metadata']]
    without_metadata = [r for r in results if not r['has_metadata']]
    
    print("\n" + "=" * 80)
    print("  总结报告")
    print("=" * 80)
    
    print(f"\n📊 整体统计:")
    print(f"   总章节数: {total}")
    print(f"   正常章节: {len(normal)} ({len(normal)/total*100:.1f}%)")
    print(f"   问题章节: {len(problematic)} ({len(problematic)/total*100:.1f}%)")
    
    if problematic:
        print(f"\n❌ 问题章节列表:")
        for r in problematic:
            keywords = ', '.join(r['planner_keywords'])
            print(f"   第 {r['chapter_number']} 章: {keywords}")
    
    print(f"\n📈 Metadata统计:")
    print(f"   有metadata: {len(with_metadata)} ({len(with_metadata)/total*100:.1f}%)")
    print(f"   无metadata: {len(without_metadata)} ({len(without_metadata)/total*100:.1f}%)")
    
    if with_metadata:
        avg_iterations = sum(r['iterations'] for r in with_metadata if r['iterations']) / len([r for r in with_metadata if r['iterations']])
        avg_score = sum(r['score'] for r in with_metadata if r['score']) / len([r for r in with_metadata if r['score']])
        
        print(f"   平均迭代次数: {avg_iterations:.1f}")
        print(f"   平均评分: {avg_score:.1f}")
    
    print(f"\n💡 建议:")
    if problematic:
        print(f"   - 发现 {len(problematic)} 个问题章节，建议重新生成")
        print(f"   - 运行以下命令查看详细信息:")
        for r in problematic[:3]:  # 只显示前3个
            print(f"     python3 quick_check_full_content.py {r['chapter_number']}")
    else:
        print(f"   - 所有章节都正常！")
    
    if without_metadata:
        print(f"   - 有 {len(without_metadata)} 个章节缺少metadata")
        print(f"   - 这可能是旧版本生成的章节，或非3Agent模式生成")

# ============================================================================
# 主程序
# ============================================================================

def main():
    # 解析参数
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == '--all':
            mode = 'all'
            chapter_num = None
        elif arg == '--summary':
            mode = 'summary'
            chapter_num = None
        elif arg == '--help' or arg == '-h':
            print(__doc__)
            return
        else:
            try:
                mode = 'single'
                chapter_num = int(arg)
            except ValueError:
                print(f"❌ 无效的章节号: {arg}")
                print("使用 --help 查看帮助")
                return
    else:
        mode = 'single'
        chapter_num = None
    
    # 查找数据库
    db_path = find_database()
    if not db_path:
        print("❌ 未找到数据库文件")
        print("请确保在项目根目录运行")
        return
    
    conn = sqlite3.connect(db_path)
    
    try:
        if mode == 'single':
            # 检查单个章节
            print("=" * 80)
            if chapter_num:
                print(f"  检查第 {chapter_num} 章")
            else:
                print(f"  检查最新章节")
            print("=" * 80)
            
            result = check_chapter(conn, chapter_num)
            
            if not result:
                print(f"\n❌ 未找到章节")
                return
            
            print_chapter_result(result, detailed=True)
            
            # 给出建议
            print("\n" + "=" * 80)
            print("  诊断建议")
            print("=" * 80)
            
            if result['is_planner_format']:
                print("\n❌ 此章节的内容是 Planner 格式，不是正常的小说内容！")
                print("\n可能原因:")
                print("  1. Writer Agent 错误地返回了 Planner 的分析内容")
                print("  2. 保存时使用了错误的变量")
                print("\n建议操作:")
                print(f"  1. 查看完整生成流程:")
                print(f"     python3 show_latest_generation_flow.py")
                print(f"  2. 深入分析数据流:")
                print(f"     python3 test_3agent_full_content_save.py --flow --chapter {result['chapter_number']}")
                print(f"  3. 重新生成此章节")
            else:
                print("\n✅ 此章节内容正常！")
        
        elif mode == 'all':
            # 检查所有章节
            print("=" * 80)
            print("  检查所有章节")
            print("=" * 80)
            
            results = check_all_chapters(conn)
            
            if not results:
                print("\n❌ 未找到任何章节")
                return
            
            for result in results:
                print_chapter_result(result, detailed=False)
            
            print_summary(results)
        
        elif mode == 'summary':
            # 生成总结报告
            results = check_all_chapters(conn)
            
            if not results:
                print("\n❌ 未找到任何章节")
                return
            
            print_summary(results)
    
    finally:
        conn.close()
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
