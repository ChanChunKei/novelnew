#!/usr/bin/env python3
"""
3Agent Full Content 保存问题 - 综合测试工具

这个工具提供多层次的测试来定位 full_content 保存问题：

测试层级：
1. 【数据库层】检查实际保存的数据
2. 【格式检测层】测试 Planner 格式检测逻辑
3. 【数据流层】追踪从生成到保存的完整数据流
4. 【边界测试】测试各种异常情况
5. 【实时监控】在生成过程中插桩记录

使用方法：
  python3 test_3agent_full_content_save.py --all              # 运行所有测试
  python3 test_3agent_full_content_save.py --db               # 只测试数据库
  python3 test_3agent_full_content_save.py --detection       # 只测试格式检测
  python3 test_3agent_full_content_save.py --flow            # 只测试数据流
  python3 test_3agent_full_content_save.py --chapter 5       # 测试特定章节
"""

import sys
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
from datetime import datetime

# ============================================================================
# 工具函数
# ============================================================================

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

def print_section(title: str, level: int = 1):
    """打印分隔线和标题"""
    if level == 1:
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80)
    else:
        print("\n" + "-" * 80)
        print(f"  {title}")
        print("-" * 80)

def print_test_result(test_name: str, passed: bool, details: str = ""):
    """打印测试结果"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status} | {test_name}")
    if details:
        for line in details.split("\n"):
            print(f"        {line}")

# ============================================================================
# 测试1：数据库层检查
# ============================================================================

class DatabaseTester:
    """数据库层测试"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
    
    def test_latest_chapters(self, n: int = 5) -> List[Dict]:
        """测试最近N个章节的数据质量"""
        print_section(f"数据库层测试 - 检查最近 {n} 个章节", level=2)
        
        self.cursor.execute("""
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
        LIMIT ?
        """, (n,))
        
        results = []
        rows = self.cursor.fetchall()
        
        for idx, row in enumerate(rows, 1):
            chapter_id, chapter_num, project_title, content, metadata_str, created, version = row
            
            print(f"\n[{idx}] 第 {chapter_num} 章 - {version}")
            print(f"    时间: {created}")
            
            result = self._analyze_chapter_data(content, metadata_str)
            result['chapter_number'] = chapter_num
            result['chapter_id'] = chapter_id
            results.append(result)
            
            # 打印诊断结果
            if result['has_planner_format']:
                print(f"    ❌ 内容是 Planner 格式！")
            elif result['is_json']:
                print(f"    ⚠️  内容是 JSON 格式")
            else:
                print(f"    ✅ 内容格式正常")
            
            if result['has_metadata']:
                print(f"    ✅ 有 metadata (迭代{result['iterations']}次, 评分{result['score']})")
            else:
                print(f"    ⚠️  缺少 metadata")
        
        return results
    
    def test_specific_chapter(self, chapter_num: int) -> Dict:
        """测试特定章节"""
        print_section(f"数据库层测试 - 检查第 {chapter_num} 章", level=2)
        
        self.cursor.execute("""
        SELECT 
            c.id,
            c.chapter_number, 
            cv.content, 
            cv.metadata,
            cv.created_at
        FROM chapters c
        JOIN chapter_versions cv ON c.selected_version_id = cv.id
        WHERE c.chapter_number = ?
        ORDER BY cv.created_at DESC
        LIMIT 1
        """, (chapter_num,))
        
        row = self.cursor.fetchone()
        if not row:
            print(f"❌ 未找到第 {chapter_num} 章")
            return {}
        
        chapter_id, chapter_num, content, metadata_str, created = row
        result = self._analyze_chapter_data(content, metadata_str)
        
        # 详细输出
        print(f"\n内容分析:")
        print(f"  长度: {result['content_length']} 字符")
        print(f"  是JSON: {result['is_json']}")
        print(f"  Planner格式: {result['has_planner_format']}")
        if result['planner_keywords']:
            print(f"  Planner关键词: {result['planner_keywords']}")
        
        print(f"\n前300字内容:")
        print(f"  {result['content_preview']}")
        
        if result['has_metadata']:
            print(f"\nMetadata分析:")
            print(f"  迭代次数: {result['iterations']}")
            print(f"  最终评分: {result['score']}")
            print(f"  总耗时: {result['total_time']}秒")
            print(f"  对话步骤: {result['conversation_steps']}")
        
        return result
    
    def _analyze_chapter_data(self, content: str, metadata_str: Optional[str]) -> Dict:
        """分析章节数据"""
        result = {
            'content_length': len(content) if content else 0,
            'content_preview': (content[:300] if content else ""),
            'is_json': False,
            'has_planner_format': False,
            'planner_keywords': [],
            'has_metadata': bool(metadata_str),
            'iterations': None,
            'score': None,
            'total_time': None,
            'conversation_steps': 0
        }
        
        if not content:
            return result
        
        # 检查是否是JSON
        content_stripped = content.strip()
        if content_stripped.startswith("{") and content_stripped.endswith("}"):
            result['is_json'] = True
            try:
                parsed = json.loads(content_stripped)
                
                # 检查Planner关键词
                planner_fields = ['analysis', 'plan', 'queries_summary', 'notes_for_writer']
                found = [f for f in planner_fields if f in parsed]
                result['planner_keywords'] = found
                
                if len(found) >= 2:  # 至少2个关键词
                    result['has_planner_format'] = True
            except json.JSONDecodeError:
                pass
        
        # 检查文本中的Planner关键词（非JSON情况）
        if not result['is_json']:
            check_content = content[:1000]
            planner_markers = ["analysis:", "plan:", "queries_summary:", "notes_for_writer:"]
            found_markers = [m for m in planner_markers if m in check_content]
            if len(found_markers) >= 2:
                result['has_planner_format'] = True
                result['planner_keywords'] = found_markers
        
        # 解析metadata
        if metadata_str:
            try:
                meta = json.loads(metadata_str)
                result['iterations'] = meta.get('iterations')
                result['score'] = meta.get('final_score')
                result['total_time'] = meta.get('total_time_seconds')
                if 'conversation_history' in meta:
                    result['conversation_steps'] = len(meta['conversation_history'])
            except json.JSONDecodeError:
                pass
        
        return result
    
    def close(self):
        self.conn.close()

# ============================================================================
# 测试2：格式检测逻辑测试
# ============================================================================

class DetectionTester:
    """格式检测逻辑测试"""
    
    def test_planner_detection(self):
        """测试Planner格式检测逻辑"""
        print_section("格式检测测试 - Planner格式识别", level=2)
        
        test_cases = [
            {
                'name': '正常小说内容',
                'content': '第一章 危机降临\n\n林远站在村口，看着远处升起的黑烟。他的心中充满了不安...',
                'should_detect': False
            },
            {
                'name': 'JSON格式的Planner输出',
                'content': json.dumps({
                    "analysis": "本章需要展现主角的内心挣扎",
                    "plan": "开头铺垫、中间冲突、结尾留白",
                    "queries_summary": "查询了相关背景设定",
                    "notes_for_writer": "注意人物刻画"
                }, ensure_ascii=False),
                'should_detect': True
            },
            {
                'name': '文本格式的Planner输出',
                'content': 'analysis: 本章需要展现主角的内心挣扎\nplan: 开头铺垫、中间冲突、结尾留白\nqueries_summary: 查询了相关背景设定',
                'should_detect': True
            },
            {
                'name': '只有1个Planner关键词（不应触发）',
                'content': '这是一篇关于数据分析(analysis)的文章，讲述了一个计划(plan)。但这是正常内容。',
                'should_detect': False
            },
            {
                'name': '包含2个Planner关键词在前1000字（应触发）',
                'content': 'analysis: 详细分析\n' + 'x' * 500 + '\nplan: 详细规划',
                'should_detect': True
            },
            {
                'name': 'Planner关键词在1000字之后（不应触发）',
                'content': '正常内容' * 300 + '\nanalysis: 后面的分析\nplan: 后面的计划',
                'should_detect': False
            }
        ]
        
        passed = 0
        failed = 0
        
        for case in test_cases:
            detected = self._detect_planner_format(case['content'])
            expected = case['should_detect']
            
            if detected == expected:
                passed += 1
                print_test_result(case['name'], True)
            else:
                failed += 1
                details = f"期望: {'检测到' if expected else '未检测到'}\n实际: {'检测到' if detected else '未检测到'}"
                print_test_result(case['name'], False, details)
        
        print(f"\n总结: {passed} 通过, {failed} 失败")
        return failed == 0
    
    def _detect_planner_format(self, content: str) -> bool:
        """
        复现 ai_orchestrator_helper.py 中的检测逻辑
        检查内容是否包含Planner格式关键词
        """
        if not content:
            return False
        
        # 方法1：检查JSON格式
        content_stripped = content.strip()
        if content_stripped.startswith("{") and content_stripped.endswith("}"):
            try:
                parsed = json.loads(content_stripped)
                planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
                suspicious_count = sum(1 for kw in planner_keywords if kw in parsed)
                
                if suspicious_count >= 2:
                    return True
            except json.JSONDecodeError:
                pass
        
        # 方法2：检查文本格式（前1000字）
        check_length = min(1000, len(content))
        check_content = content[:check_length]
        
        planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
        suspicious_count = 0
        
        for kw in planner_keywords:
            if f'{kw}:' in check_content or f'"{kw}":' in check_content:
                suspicious_count += 1
        
        return suspicious_count >= 2

# ============================================================================
# 测试3：数据流追踪测试
# ============================================================================

class DataFlowTester:
    """数据流追踪测试"""
    
    def test_conversation_history(self, db_path: str, chapter_num: Optional[int] = None):
        """分析conversation_history中的数据流"""
        print_section("数据流测试 - Conversation History分析", level=2)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if chapter_num:
            cursor.execute("""
            SELECT c.chapter_number, cv.content, cv.metadata
            FROM chapters c
            JOIN chapter_versions cv ON c.selected_version_id = cv.id
            WHERE c.chapter_number = ?
            LIMIT 1
            """, (chapter_num,))
        else:
            cursor.execute("""
            SELECT c.chapter_number, cv.content, cv.metadata
            FROM chapters c
            JOIN chapter_versions cv ON c.selected_version_id = cv.id
            ORDER BY cv.created_at DESC
            LIMIT 1
            """)
        
        row = cursor.fetchone()
        if not row:
            print("❌ 未找到章节")
            conn.close()
            return
        
        chapter_num, content, metadata_str = row
        
        print(f"\n分析第 {chapter_num} 章的生成流程")
        
        if not metadata_str:
            print("❌ 没有metadata，无法分析")
            conn.close()
            return
        
        try:
            metadata = json.loads(metadata_str)
        except json.JSONDecodeError:
            print("❌ metadata解析失败")
            conn.close()
            return
        
        if 'conversation_history' not in metadata:
            print("❌ metadata中没有conversation_history")
            conn.close()
            return
        
        history = metadata['conversation_history']
        print(f"\n对话历史: 共 {len(history)} 步")
        
        # 分析每一步
        planner_output = None
        writer_outputs = []
        reviewer_outputs = []
        
        for idx, item in enumerate(history, 1):
            agent = item.get('agent', 'unknown')
            iteration = item.get('iteration', '')
            content_data = item.get('content', {})
            
            print(f"\n步骤 {idx}: {agent.upper()}", end="")
            if iteration:
                print(f" (迭代 {iteration})", end="")
            print()
            
            if agent == 'planner':
                planner_output = content_data
                # 检查Planner输出的结构
                if isinstance(content_data, dict):
                    keys = list(content_data.keys())
                    print(f"  输出字段: {keys}")
                    planner_keywords = ['analysis', 'plan', 'queries_summary', 'notes_for_writer']
                    has_keywords = [k for k in planner_keywords if k in content_data]
                    if has_keywords:
                        print(f"  Planner关键字段: {has_keywords}")
            
            elif agent == 'writer':
                writer_outputs.append({
                    'iteration': iteration,
                    'content': content_data
                })
                
                if isinstance(content_data, dict):
                    print(f"  输出字段: {list(content_data.keys())}")
                    
                    # 检查是否有full_content
                    if 'full_content' in content_data:
                        fc = content_data['full_content']
                        fc_str = str(fc)
                        print(f"  full_content长度: {len(fc_str)}")
                        
                        # 关键检查：full_content是否是Planner格式
                        is_planner = self._check_if_planner_format(fc_str)
                        if is_planner:
                            print(f"  ❌❌❌ Writer的full_content是Planner格式！")
                            print(f"  这就是问题所在！")
                        else:
                            print(f"  ✅ full_content格式正常")
                        
                        # 显示预览
                        preview = fc_str[:200].replace('\n', ' ')
                        print(f"  预览: {preview}...")
            
            elif agent == 'reviewer':
                reviewer_outputs.append({
                    'iteration': iteration,
                    'content': content_data
                })
                
                if isinstance(content_data, dict):
                    approved = content_data.get('approved', False)
                    score = content_data.get('score', 0)
                    print(f"  审核: {'✅通过' if approved else '❌未通过'} (评分: {score})")
        
        # 最终对比
        print("\n" + "=" * 60)
        print("最终对比分析")
        print("=" * 60)
        
        print(f"\n1. 最终保存的content:")
        print(f"   长度: {len(content)}")
        content_is_planner = self._check_if_planner_format(content)
        if content_is_planner:
            print(f"   ❌ 最终保存的content是Planner格式！")
        else:
            print(f"   ✅ 最终保存的content格式正常")
        print(f"   前200字: {content[:200].replace(chr(10), ' ')}...")
        
        print(f"\n2. Writer的输出 (共{len(writer_outputs)}次):")
        for w in writer_outputs:
            iter_info = f"迭代{w['iteration']}" if w['iteration'] else "单次"
            if 'full_content' in w['content']:
                fc = str(w['content']['full_content'])
                is_planner = self._check_if_planner_format(fc)
                status = "❌Planner格式" if is_planner else "✅正常"
                print(f"   {iter_info}: {status}, 长度{len(fc)}")
        
        # 诊断结论
        print(f"\n3. 诊断结论:")
        if content_is_planner:
            print(f"   ❌ 最终content有问题 - 是Planner格式")
            
            # 检查Writer的输出
            writer_has_planner = any(
                self._check_if_planner_format(str(w['content'].get('full_content', '')))
                for w in writer_outputs
                if 'full_content' in w['content']
            )
            
            if writer_has_planner:
                print(f"   ❌ Writer的输出就已经是Planner格式")
                print(f"   根因: Writer Agent错误地返回了Planner的内容")
                print(f"   建议: 检查Writer的prompt和上下文")
            else:
                print(f"   ✅ Writer的输出是正常的")
                print(f"   根因: 保存过程中使用了错误的变量")
                print(f"   建议: 检查auto_generator_service.py的变量传递")
        else:
            print(f"   ✅ 没有发现问题")
        
        conn.close()
    
    def _check_if_planner_format(self, content: str) -> bool:
        """检查内容是否是Planner格式"""
        if not content or not isinstance(content, str):
            return False
        
        content_stripped = content.strip()
        
        # JSON格式检查
        if content_stripped.startswith("{") and content_stripped.endswith("}"):
            try:
                parsed = json.loads(content_stripped)
                planner_keywords = ['analysis', 'plan', 'queries_summary', 'notes_for_writer']
                count = sum(1 for kw in planner_keywords if kw in parsed)
                return count >= 2
            except:
                pass
        
        # 文本格式检查
        check_content = content[:1000]
        planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
        count = sum(1 for kw in planner_keywords 
                   if f'{kw}:' in check_content or f'"{kw}":' in check_content)
        return count >= 2

# ============================================================================
# 测试4：边界情况测试
# ============================================================================

class BoundaryTester:
    """边界情况测试"""
    
    def test_edge_cases(self):
        """测试各种边界情况"""
        print_section("边界情况测试", level=2)
        
        test_cases = [
            {
                'name': '空内容',
                'content': '',
                'should_pass': True
            },
            {
                'name': 'None值',
                'content': None,
                'should_pass': True
            },
            {
                'name': '只有空格',
                'content': '   \n\n   ',
                'should_pass': True
            },
            {
                'name': '不完整的JSON',
                'content': '{"analysis": "test"',
                'should_pass': True
            },
            {
                'name': '嵌套的JSON',
                'content': json.dumps({
                    "full_content": json.dumps({
                        "analysis": "test",
                        "plan": "test"
                    })
                }),
                'should_pass': False  # 应该被检测为Planner格式
            },
            {
                'name': '超长内容',
                'content': 'x' * 10000 + '\nanalysis: test\nplan: test',
                'should_pass': True  # 关键词在1000字之后，不应触发
            }
        ]
        
        detector = DetectionTester()
        
        for case in test_cases:
            try:
                if case['content'] is None:
                    detected = False
                else:
                    detected = detector._detect_planner_format(case['content'])
                
                # should_pass=True 表示应该通过检测（不被识别为Planner格式）
                passed = (not detected) if case['should_pass'] else detected
                
                print_test_result(case['name'], passed)
            except Exception as e:
                print_test_result(case['name'], False, f"异常: {str(e)}")

# ============================================================================
# 测试5：生成新内容测试实时数据流
# ============================================================================

class LiveTestGenerator:
    """实时测试生成器"""
    
    def generate_test_instructions(self):
        """生成实时测试的说明"""
        print_section("实时测试指南", level=2)
        
        print(r"""
要测试实时生成过程中的数据流，需要在代码中添加调试日志。

推荐修改点：

1. backend/app/services/ai_orchestrator_helper.py
   在 _call_writer_agent 函数中添加：
   
   ```python
   # 在第1706行之后（JSON解析后）
   logger.info(f"[DEBUG] Writer返回类型: {type(response_str)}")
   logger.info(f"[DEBUG] Writer返回前500字: {response_str[:500]}")
   
   # 在第1718行之后（提取full_content后）
   if "full_content" in response:
       fc = response["full_content"]
       logger.info(f"[DEBUG] full_content类型: {type(fc)}")
       logger.info(f"[DEBUG] full_content长度: {len(str(fc))}")
       logger.info(f"[DEBUG] full_content前200字: {str(fc)[:200]}")
       
       # 检测Planner格式
       if isinstance(fc, str):
           planner_check = ["analysis", "plan", "queries_summary"]
           found = [k for k in planner_check if f'{k}:' in fc[:1000]]
           if found:
               logger.warning(f"[DEBUG] ⚠️  full_content包含Planner关键词: {found}")
   ```

2. backend/app/services/auto_generator_service.py
   在第994行之后添加：
   
   ```python
   logger.info(f"[DEBUG] 提取的full_content长度: {len(full_content)}")
   logger.info(f"[DEBUG] 提取的full_content前200字: {full_content[:200]}")
   
   # 检测Planner格式
   planner_check = ["analysis", "plan", "queries_summary"]
   found = [k for k in planner_check if f'{k}:' in full_content[:1000]]
   if found:
       logger.warning(f"[DEBUG] ⚠️  提取的full_content包含Planner关键词: {found}")
   ```

3. 启用调试模式生成一章
   然后查看日志：
   
   ```bash
   tail -f backend/storage/logs/app.log | grep "\[DEBUG\]"
   ```

这样可以实时看到数据在各个环节的变化。
""")

# ============================================================================
# 主程序
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='3Agent Full Content 保存问题综合测试工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--all', action='store_true', help='运行所有测试')
    parser.add_argument('--db', action='store_true', help='运行数据库测试')
    parser.add_argument('--detection', action='store_true', help='运行格式检测测试')
    parser.add_argument('--flow', action='store_true', help='运行数据流测试')
    parser.add_argument('--boundary', action='store_true', help='运行边界测试')
    parser.add_argument('--live', action='store_true', help='显示实时测试指南')
    parser.add_argument('--chapter', type=int, help='指定要测试的章节号')
    parser.add_argument('--recent', type=int, default=5, help='测试最近N个章节（默认5）')
    
    args = parser.parse_args()
    
    # 如果没有指定任何选项，显示帮助
    if not any([args.all, args.db, args.detection, args.flow, args.boundary, args.live]):
        parser.print_help()
        return
    
    print_section("3Agent Full Content 保存问题 - 综合测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 查找数据库
    db_path = find_database()
    if not db_path and (args.all or args.db or args.flow):
        print("\n❌ 未找到数据库文件")
        print("请确保在项目根目录运行，或数据库文件存在")
        return
    
    if db_path:
        print(f"数据库: {db_path}")
    
    # 运行测试
    run_all = args.all
    
    # 1. 数据库测试
    if run_all or args.db:
        db_tester = DatabaseTester(db_path)
        try:
            if args.chapter:
                db_tester.test_specific_chapter(args.chapter)
            else:
                db_tester.test_latest_chapters(args.recent)
        finally:
            db_tester.close()
    
    # 2. 格式检测测试
    if run_all or args.detection:
        detection_tester = DetectionTester()
        detection_tester.test_planner_detection()
    
    # 3. 数据流测试
    if run_all or args.flow:
        flow_tester = DataFlowTester()
        flow_tester.test_conversation_history(db_path, args.chapter)
    
    # 4. 边界测试
    if run_all or args.boundary:
        boundary_tester = BoundaryTester()
        boundary_tester.test_edge_cases()
    
    # 5. 实时测试指南
    if run_all or args.live:
        live_tester = LiveTestGenerator()
        live_tester.generate_test_instructions()
    
    print_section("测试完成")
    print("\n建议下一步操作:")
    print("  1. 如果发现数据库中有Planner格式的章节，运行: ")
    print("     python3 test_3agent_full_content_save.py --flow --chapter <章节号>")
    print("  2. 如果要深入分析，按照 --live 指南添加调试日志")
    print("  3. 如果要重新生成问题章节，使用前端的重新生成功能")
    print()

if __name__ == '__main__':
    main()
