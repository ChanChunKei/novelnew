"""
单元测试：Planner格式检测功能

测试 _detect_planner_format() 函数的各种场景
"""
import pytest
from app.services.ai_orchestrator_helper import _detect_planner_format


class TestPlannerFormatDetection:
    """测试Planner格式检测功能"""

    def test_basic_planner_format(self):
        """测试基础Planner格式：使用冒号"""
        content = """
analysis: 这是对当前章节的详细分析。我们需要考虑人物动机、情节发展和冲突设置。

plan: 本章的写作规划如下：
1. 开场描写主角的心理状态
2. 引入新的冲突
3. 推进主线剧情
        """
        is_planner, count, matched = _detect_planner_format(content)
        assert is_planner == True
        assert count == 2
        assert any("analysis" in m for m in matched)
        assert any("plan" in m for m in matched)

    def test_markdown_bold_format(self):
        """测试Markdown粗体格式：**analysis**"""
        content = """
**analysis**
这是对章节的分析

**plan**
这是写作规划
        """
        is_planner, count, matched = _detect_planner_format(content)
        assert is_planner == True
        assert count >= 2

    def test_markdown_header_format(self):
        """测试Markdown标题格式：## analysis"""
        content = """
## Analysis
当前章节需要处理的核心问题是...

## Plan
写作规划如下...
        """
        is_planner, count, matched = _detect_planner_format(content)
        assert is_planner == True
        assert count >= 2

    def test_json_format_planner(self):
        """测试JSON格式的Planner"""
        content = """
{
    "analysis": "这是章节分析",
    "plan": "这是内容规划",
    "queries_summary": "查询结果总结",
    "notes_for_writer": "给Writer的建议"
}
        """
        is_planner, count, matched = _detect_planner_format(content)
        assert is_planner == True
        assert count >= 2

    def test_normal_novel_content(self):
        """测试正常的小说内容不被误判"""
        content = """
第一章

张三走在路上，心中暗自分析着局势。他知道，接下来必须制定一个周密的计划。

"我需要仔细分析一下。" 他喃喃自语道。

李四看着他，问道："你有什么打算吗？"

"是的，我有一个计划。" 张三回答。
        """
        is_planner, count, matched = _detect_planner_format(content)
        # 可能会检测到 "分析" 和 "计划" 等词，但因为没有特定格式，应该不触发
        assert is_planner == False

    def test_single_keyword_not_triggered(self):
        """测试只有一个关键词不触发"""
        content = """
analysis: 这是唯一的一个关键词

其他都是正常的小说内容，没有其他Planner关键词。
        """
        is_planner, count, matched = _detect_planner_format(content)
        assert is_planner == False
        assert count == 1

    def test_planner_keywords_beyond_check_length(self):
        """测试关键词在检测范围之外（>1000字符）"""
        # 创建一个前1000字符是正常内容，之后才有Planner关键词的文本
        normal_content = "这是正常的小说内容。" * 100  # 大约1500字符
        planner_content = "\n\nanalysis: 这是分析\nplan: 这是规划"
        content = normal_content + planner_content

        is_planner, count, matched = _detect_planner_format(content)
        # 因为Planner关键词在1000字符之后，应该不被检测到
        assert is_planner == False

    def test_planner_keywords_at_beginning(self):
        """测试关键词在开头位置（前200字）"""
        content = """
analysis: 开头就有分析内容
plan: 紧接着是规划

这样的内容应该被立即检测到。
        """
        is_planner, count, matched = _detect_planner_format(content)
        assert is_planner == True
        assert count == 2

    def test_mixed_format_planner(self):
        """测试混合格式的Planner"""
        content = """
**analysis**: 粗体加冒号格式

### plan
标题格式

"queries_summary": JSON格式
        """
        is_planner, count, matched = _detect_planner_format(content)
        assert is_planner == True
        assert count >= 2

    def test_case_insensitive_detection(self):
        """测试大小写不敏感检测"""
        content = """
ANALYSIS: 大写的分析
Plan: 首字母大写的规划
        """
        is_planner, count, matched = _detect_planner_format(content)
        assert is_planner == True
        assert count == 2

    def test_all_four_keywords(self):
        """测试包含所有4个Planner关键词"""
        content = """
analysis: 分析内容
plan: 规划内容
queries_summary: 查询总结
notes_for_writer: 给Writer的建议
        """
        is_planner, count, matched = _detect_planner_format(content)
        assert is_planner == True
        assert count == 4

    def test_empty_string(self):
        """测试空字符串"""
        content = ""
        is_planner, count, matched = _detect_planner_format(content)
        assert is_planner == False
        assert count == 0
        assert matched == []

    def test_custom_check_length(self):
        """测试自定义检测长度"""
        content = "analysis: 分析\n" + "x" * 500 + "\nplan: 规划"

        # 检测前100字符（只能检测到analysis）
        is_planner, count, matched = _detect_planner_format(content, check_length=100)
        assert count == 1

        # 检测前600字符（能检测到两个）
        is_planner, count, matched = _detect_planner_format(content, check_length=600)
        assert count >= 2

    def test_markdown_italic_format(self):
        """测试Markdown斜体格式：*analysis*"""
        content = """
*analysis*: 这是斜体格式的分析
_plan_: 这是下划线斜体格式的规划
        """
        is_planner, count, matched = _detect_planner_format(content)
        assert is_planner == True
        assert count >= 2

    def test_real_world_planner_output(self):
        """测试真实的Planner输出示例"""
        content = """
{
  "analysis": "当前章节位于故事的关键转折点，主角即将面临重大抉择。前两章已经铺垫了主角的内心矛盾和外部压力，本章需要将这些冲突推向高潮。",
  "plan": "1. 开场：主角独自思考（300字）\\n2. 对手出现，提出挑战（500字）\\n3. 主角内心挣扎（400字）\\n4. 做出决定（300字）\\n总计约1500字",
  "queries_summary": "查询了前两章中关于主角性格的描写，发现主角一直在理性和感性之间摇摆。同时查询了对手的背景设定，确认其动机合理。",
  "notes_for_writer": "注意保持主角性格的一致性。对手的言行要符合其背景设定。结尾的决定要有充分的铺垫，不要突兀。"
}
        """
        is_planner, count, matched = _detect_planner_format(content)
        assert is_planner == True
        assert count >= 3  # 至少检测到3个关键词

    def test_real_world_novel_content(self):
        """测试真实的小说内容示例"""
        content = """
第三章 抉择

夜幕降临，张三独自站在窗前，望着外面的霓虹灯。这两天发生的事情像电影一样在脑海中闪过。

"你必须做出选择。" 李四的话还在耳边回响。

他知道，每一个选择都会带来完全不同的结果。是继续坚持原则，还是向现实妥协？这个问题困扰了他整整两天。

手机响了，是王五发来的消息："明天见面谈谈？"

张三深吸一口气，回复道："好，就明天。"

窗外的城市灯火通明，一如他此刻复杂的心情。他知道，明天的会面将决定他未来的道路。
        """
        is_planner, count, matched = _detect_planner_format(content)
        # 正常的小说内容不应该被检测为Planner格式
        assert is_planner == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
