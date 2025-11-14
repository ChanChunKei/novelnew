#!/usr/bin/env python3
"""
为3Agent添加调试日志 - 自动插桩工具

这个工具会在关键位置自动添加调试日志，帮助追踪full_content的数据流。

使用方法：
  python3 add_3agent_debug_logging.py --preview   # 预览要添加的日志
  python3 add_3agent_debug_logging.py --apply     # 实际添加日志
  python3 add_3agent_debug_logging.py --remove    # 移除添加的日志
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

# ============================================================================
# 要添加的日志点配置
# ============================================================================

DEBUG_INSERTIONS = [
    {
        'file': 'backend/app/services/ai_orchestrator_helper.py',
        'locations': [
            {
                'after_line': 'response = json.loads(response_str)',
                'indent': '            ',
                'code': '''
# 🔍 DEBUG: Writer返回的原始数据
logger.info(f"[3AGENT_DEBUG] Writer返回类型: {type(response).__name__}")
logger.info(f"[3AGENT_DEBUG] Writer返回字段: {list(response.keys()) if isinstance(response, dict) else 'N/A'}")
if isinstance(response, dict) and "full_content" in response:
    fc = response["full_content"]
    fc_str = str(fc)
    logger.info(f"[3AGENT_DEBUG] full_content类型: {type(fc).__name__}")
    logger.info(f"[3AGENT_DEBUG] full_content长度: {len(fc_str)}")
    logger.info(f"[3AGENT_DEBUG] full_content前300字: {fc_str[:300]}")
    # 检测Planner格式
    if fc_str.strip().startswith("{"):
        try:
            import json as json_module
            parsed = json_module.loads(fc_str)
            planner_kw = ["analysis", "plan", "queries_summary", "notes_for_writer"]
            found_kw = [k for k in planner_kw if k in parsed]
            if len(found_kw) >= 2:
                logger.error(f"[3AGENT_DEBUG] ❌ Writer的full_content是Planner格式！包含: {found_kw}")
            else:
                logger.info(f"[3AGENT_DEBUG] ✅ full_content不是Planner格式")
        except:
            pass
'''
            },
            {
                'after_line': 'cleaned_content = _clean_full_content(response_str,',
                'indent': '                ',
                'code': '''
# 🔍 DEBUG: 清理后的内容（非JSON情况）
logger.info(f"[3AGENT_DEBUG] 清理后内容长度: {len(cleaned_content)}")
logger.info(f"[3AGENT_DEBUG] 清理后内容前300字: {cleaned_content[:300]}")
planner_kw = ["analysis:", "plan:", "queries_summary:", "notes_for_writer:"]
found_kw = [k for k in planner_kw if k in cleaned_content[:1000]]
if len(found_kw) >= 2:
    logger.error(f"[3AGENT_DEBUG] ❌ 清理后内容包含Planner关键词: {found_kw}")
'''
            }
        ]
    },
    {
        'file': 'backend/app/services/auto_generator_service.py',
        'locations': [
            {
                'after_line': 'full_content = variant.get("full_content")',
                'indent': '                ',
                'code': '''
# 🔍 DEBUG: 提取full_content
logger.info(f"[3AGENT_DEBUG] 从variant提取full_content")
logger.info(f"[3AGENT_DEBUG] variant字段: {list(variant.keys()) if isinstance(variant, dict) else 'N/A'}")
if full_content:
    logger.info(f"[3AGENT_DEBUG] full_content类型: {type(full_content).__name__}")
    logger.info(f"[3AGENT_DEBUG] full_content长度: {len(str(full_content))}")
    fc_str = str(full_content)
    logger.info(f"[3AGENT_DEBUG] full_content前300字: {fc_str[:300]}")
    # 检测Planner格式
    planner_kw = ["analysis:", "plan:", "queries_summary:", "notes_for_writer:"]
    found_kw = [k for k in planner_kw if k in fc_str[:1000]]
    if len(found_kw) >= 2:
        logger.error(f"[3AGENT_DEBUG] ❌ 提取的full_content包含Planner关键词: {found_kw}")
'''
            },
            {
                'after_line': 'await novel_service.replace_chapter_versions(chapter, contents,',
                'indent': '            ',
                'code': '''
# 🔍 DEBUG: 保存前的最终检查
logger.info(f"[3AGENT_DEBUG] 准备保存 {len(contents)} 个版本")
for idx, content in enumerate(contents):
    logger.info(f"[3AGENT_DEBUG] 版本{idx+1}长度: {len(content)}")
    logger.info(f"[3AGENT_DEBUG] 版本{idx+1}前200字: {content[:200]}")
    planner_kw = ["analysis:", "plan:", "queries_summary:"]
    found_kw = [k for k in planner_kw if k in content[:1000]]
    if found_kw:
        logger.error(f"[3AGENT_DEBUG] ❌ 版本{idx+1}包含Planner关键词: {found_kw}")
'''
            }
        ]
    }
]

# 标记开始和结束
DEBUG_MARKER_START = "# === 3AGENT DEBUG START (auto-generated) ==="
DEBUG_MARKER_END = "# === 3AGENT DEBUG END ==="

# ============================================================================
# 工具函数
# ============================================================================

def find_line_number(lines: List[str], search_text: str, start_from: int = 0) -> int:
    """查找包含指定文本的行号"""
    for i in range(start_from, len(lines)):
        if search_text in lines[i]:
            return i
    return -1

def has_debug_markers(file_path: Path) -> bool:
    """检查文件是否已经添加了调试日志"""
    if not file_path.exists():
        return False
    
    content = file_path.read_text(encoding='utf-8')
    return DEBUG_MARKER_START in content

def preview_insertions():
    """预览要添加的日志"""
    print("=" * 80)
    print("预览调试日志插入点")
    print("=" * 80)
    
    for config in DEBUG_INSERTIONS:
        print(f"\n文件: {config['file']}")
        print("-" * 80)
        
        file_path = Path(config['file'])
        if not file_path.exists():
            print(f"  ❌ 文件不存在")
            continue
        
        if has_debug_markers(file_path):
            print(f"  ⚠️  文件已包含调试日志标记")
        
        for idx, location in enumerate(config['locations'], 1):
            print(f"\n  位置 {idx}:")
            print(f"    在此行之后: {location['after_line'][:50]}...")
            print(f"    要插入的代码:")
            for line in location['code'].strip().split('\n'):
                print(f"      {line}")

def apply_insertions():
    """应用调试日志插入"""
    print("=" * 80)
    print("添加调试日志")
    print("=" * 80)
    
    modified_files = []
    
    for config in DEBUG_INSERTIONS:
        print(f"\n处理文件: {config['file']}")
        
        file_path = Path(config['file'])
        if not file_path.exists():
            print(f"  ❌ 文件不存在，跳过")
            continue
        
        if has_debug_markers(file_path):
            print(f"  ⚠️  文件已包含调试日志，跳过（先运行 --remove）")
            continue
        
        # 读取文件
        lines = file_path.read_text(encoding='utf-8').split('\n')
        
        # 倒序插入（避免行号偏移）
        locations_sorted = sorted(
            config['locations'],
            key=lambda loc: find_line_number(lines, loc['after_line']),
            reverse=True
        )
        
        inserted_count = 0
        for location in locations_sorted:
            line_num = find_line_number(lines, location['after_line'])
            
            if line_num == -1:
                print(f"  ⚠️  未找到行: {location['after_line'][:50]}...")
                continue
            
            # 准备要插入的代码
            indent = location['indent']
            debug_code_lines = [
                f"{indent}{DEBUG_MARKER_START}"
            ]
            for line in location['code'].strip().split('\n'):
                if line.strip():  # 跳过空行
                    debug_code_lines.append(f"{indent}{line}")
            debug_code_lines.append(f"{indent}{DEBUG_MARKER_END}")
            
            # 插入
            lines = lines[:line_num+1] + debug_code_lines + lines[line_num+1:]
            inserted_count += 1
            
            print(f"  ✅ 在第 {line_num+1} 行后插入调试日志")
        
        if inserted_count > 0:
            # 写回文件
            file_path.write_text('\n'.join(lines), encoding='utf-8')
            modified_files.append(config['file'])
            print(f"  ✅ 文件已更新，插入了 {inserted_count} 处日志")
        else:
            print(f"  ⚠️  没有插入任何日志")
    
    if modified_files:
        print("\n" + "=" * 80)
        print("✅ 调试日志添加完成")
        print("=" * 80)
        print("\n已修改的文件:")
        for f in modified_files:
            print(f"  - {f}")
        print("\n下一步:")
        print("  1. 重启后端服务")
        print("  2. 生成一个新章节")
        print("  3. 查看日志:")
        print("     tail -f backend/storage/logs/app.log | grep '3AGENT_DEBUG'")
        print("  4. 测试完成后运行:")
        print("     python3 add_3agent_debug_logging.py --remove")
    else:
        print("\n❌ 没有修改任何文件")

def remove_insertions():
    """移除调试日志"""
    print("=" * 80)
    print("移除调试日志")
    print("=" * 80)
    
    modified_files = []
    
    for config in DEBUG_INSERTIONS:
        print(f"\n处理文件: {config['file']}")
        
        file_path = Path(config['file'])
        if not file_path.exists():
            print(f"  ❌ 文件不存在，跳过")
            continue
        
        if not has_debug_markers(file_path):
            print(f"  ℹ️  文件不包含调试日志标记，跳过")
            continue
        
        # 读取文件
        lines = file_path.read_text(encoding='utf-8').split('\n')
        
        # 移除标记之间的所有行
        new_lines = []
        skip = False
        removed_count = 0
        
        for line in lines:
            if DEBUG_MARKER_START in line:
                skip = True
                removed_count += 1
                continue
            elif DEBUG_MARKER_END in line:
                skip = False
                continue
            
            if not skip:
                new_lines.append(line)
        
        if removed_count > 0:
            # 写回文件
            file_path.write_text('\n'.join(new_lines), encoding='utf-8')
            modified_files.append(config['file'])
            print(f"  ✅ 移除了 {removed_count} 处调试日志")
        else:
            print(f"  ℹ️  没有找到要移除的日志")
    
    if modified_files:
        print("\n" + "=" * 80)
        print("✅ 调试日志移除完成")
        print("=" * 80)
        print("\n已修改的文件:")
        for f in modified_files:
            print(f"  - {f}")
        print("\n提示: 重启后端服务以应用更改")
    else:
        print("\n❌ 没有修改任何文件")

def main():
    parser = argparse.ArgumentParser(
        description='为3Agent添加调试日志 - 自动插桩工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--preview', action='store_true', 
                       help='预览要添加的日志（不修改文件）')
    parser.add_argument('--apply', action='store_true',
                       help='实际添加调试日志')
    parser.add_argument('--remove', action='store_true',
                       help='移除已添加的调试日志')
    
    args = parser.parse_args()
    
    if not any([args.preview, args.apply, args.remove]):
        parser.print_help()
        return
    
    if args.preview:
        preview_insertions()
    elif args.apply:
        apply_insertions()
    elif args.remove:
        remove_insertions()

if __name__ == '__main__':
    main()
