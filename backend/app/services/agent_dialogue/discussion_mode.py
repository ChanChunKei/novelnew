"""
讨论模式主入口

提供简洁的接口来使用讨论模式生成章节。
"""

from typing import Dict, Any, Optional, TYPE_CHECKING
import logging
import os
import asyncio

from .coordinator import Coordinator
from .state import DialogueConfig

if TYPE_CHECKING:
    from ..llm_service import LLMService
    from ..rag_service import RAGService

logger = logging.getLogger(__name__)

# Prompt 模板目录
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts", "dialogue")


def _load_prompt(filename: str) -> str:
    """加载 Prompt 模板"""
    filepath = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Prompt 文件不存在: {filepath}，使用默认模板")
        return _get_default_prompt(filename)


def _get_default_prompt(filename: str) -> str:
    """获取默认 Prompt"""
    defaults = {
        "planner_dialogue.md": DEFAULT_PLANNER_PROMPT,
        "writer_dialogue.md": DEFAULT_WRITER_PROMPT,
        "reviewer_dialogue.md": DEFAULT_REVIEWER_PROMPT,
    }
    return defaults.get(filename, "")


# 默认 Prompt 模板
DEFAULT_PLANNER_PROMPT = """# 角色：规划者 (Planner)

你是小说创作团队中的**规划者**，负责分析项目、规划章节结构。

## 你的职责
1. 分析项目背景和当前进度
2. 规划本章的内容方向和关键事件
3. 确保剧情连贯、伏笔合理
4. 回答其他成员关于规划的问题

## 工作原则
- 基于 RAG 检索的历史信息做决策
- 规划要具体可执行，不要过于抽象
- 考虑节奏和情感走向
- 标注需要回收的伏笔

## 与其他成员的协作
- 你的规划将指导 Writer 创作
- Reviewer 可能会就剧情一致性向你提问
- 你可以主动向 Writer 提供建议
- 遇到争议时，用事实和数据支持你的观点
"""

DEFAULT_WRITER_PROMPT = """# 角色：创作者 (Writer)

你是小说创作团队中的**创作者**，负责撰写精彩的章节内容。

## 你的职责
1. 根据 Planner 的规划撰写章节
2. 塑造生动的角色和场景
3. 把控叙事节奏和情感张力
4. 根据 Reviewer 反馈修改内容

## 写作原则
- 输出纯文本，不使用 Markdown 格式
- 保持与前文的风格一致
- 角色行为要符合人设
- 对话要自然，避免说教

## 与其他成员的协作
- 遵循 Planner 的规划，但可以提出疑问
- 认真对待 Reviewer 的反馈
- 如有创作上的困惑，主动询问
- 修改时说明你的改动和理由
"""

DEFAULT_REVIEWER_PROMPT = """# 角色：审核者 (Reviewer)

你是小说创作团队中的**审核者**，负责把控内容质量。

## 你的职责
1. 从剧情、角色、文笔、节奏四个维度审核
2. 指出问题并给出具体修改建议
3. 使用工具验证内容一致性
4. 决定是否通过

## 审核标准
- **剧情逻辑** (25分)：情节是否合理，有无漏洞
- **角色塑造** (25分)：行为是否符合人设
- **文笔质量** (25分)：语言表达、描写能力
- **节奏把控** (25分)：叙事节奏、张弛有度

## 与其他成员的协作
- 发现规划问题时，向 Planner 求证
- 给 Writer 的反馈要具体可执行
- 评价要客观公正，有理有据
- 肯定优点，指出问题
"""


class DiscussionMode:
    """
    讨论模式
    
    一个真正的多 Agent 对话系统，由 Coordinator 协调 Planner、Writer、Reviewer 进行协作对话。
    
    使用方式：
        mode = DiscussionMode(llm_service, rag_service)
        result = await mode.generate_chapter(
            project_id=1,
            chapter_number=10,
            context={...}
        )
    """
    
    def __init__(
        self,
        llm_service: "LLMService",
        rag_service: Optional["RAGService"] = None,
        config: Optional[DialogueConfig] = None,
    ):
        """
        初始化讨论模式
        
        Args:
            llm_service: LLM 服务
            rag_service: RAG 服务（可选）
            config: 对话配置
        """
        self.llm_service = llm_service
        self.rag_service = rag_service
        self.config = config or DialogueConfig()
        
        # 加载 Prompt 模板
        self.planner_prompt = _load_prompt("planner_dialogue.md")
        self.writer_prompt = _load_prompt("writer_dialogue.md")
        self.reviewer_prompt = _load_prompt("reviewer_dialogue.md")
    
    async def generate_chapter(
        self,
        project_id: int,
        chapter_number: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        使用讨论模式生成章节
        
        Args:
            project_id: 项目 ID
            chapter_number: 章节号
            context: 额外上下文
            
        Returns:
            生成结果，包含：
            - success: 是否成功
            - content: 章节内容
            - title: 章节标题
            - final_score: 最终评分
            - iterations: 迭代次数
            - dialogue_export: 完整对话记录
        """
        logger.info(f"[DiscussionMode] 开始生成章节 {chapter_number}")
        
        # 构建完整上下文
        full_context = {
            "project_id": project_id,
            "chapter_number": chapter_number,
            **(context or {})
        }
        
        # 如果有 RAG 服务，获取更多上下文
        if self.rag_service:
            full_context = await self._enrich_context(full_context)
        
        # 创建 Coordinator
        coordinator = Coordinator(
            llm_service=self.llm_service,
            rag_service=self.rag_service,
            planner_prompt=self.planner_prompt,
            writer_prompt=self.writer_prompt,
            reviewer_prompt=self.reviewer_prompt,
            config=self.config,
        )
        
        # 运行对话
        result = await asyncio.wait_for(
            coordinator.run_dialogue(full_context),
            timeout=self.config.timeout_seconds
        )
        
        logger.info(f"[DiscussionMode] 章节 {chapter_number} 生成完成，成功: {result.get('success')}")
        
        return result
    
    async def generate_outline(
        self,
        project_id: int,
        start_chapter: int,
        end_chapter: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        使用讨论模式生成大纲
        
        Args:
            project_id: 项目 ID
            start_chapter: 起始章节号
            end_chapter: 结束章节号
            context: 额外上下文
            
        Returns:
            生成结果
        """
        logger.info(f"[DiscussionMode] 开始生成大纲 {start_chapter}-{end_chapter}")
        
        full_context = {
            "project_id": project_id,
            "task_type": "outline",
            "start_chapter": start_chapter,
            "end_chapter": end_chapter,
            **(context or {})
        }
        
        if self.rag_service:
            full_context = await self._enrich_context(full_context)
        
        # 使用特定的大纲生成配置
        outline_config = DialogueConfig(
            max_iterations=3,
            approval_threshold=75,
            discussion_threshold=50,
        )
        
        coordinator = Coordinator(
            llm_service=self.llm_service,
            rag_service=self.rag_service,
            planner_prompt=self._get_outline_planner_prompt(),
            writer_prompt=self._get_outline_writer_prompt(),
            reviewer_prompt=self._get_outline_reviewer_prompt(),
            config=outline_config,
        )
        
        result = await coordinator.run_dialogue(full_context)
        
        return result
    
    async def _enrich_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """使用 RAG 丰富上下文"""
        project_id = context.get("project_id")
        if not project_id or not self.rag_service:
            return context
        
        try:
            # 获取前情提要
            chapter_number = context.get("chapter_number", 1)
            if chapter_number > 1:
                summary_results = await self.rag_service.search(
                    project_id=project_id,
                    query=f"第{chapter_number-1}章的内容摘要",
                    top_k=3
                )
                if summary_results:
                    context["previous_summary"] = "\n".join([
                        r.get("content", "")[:500] for r in summary_results
                    ])
            
            # 获取角色状态
            character_results = await self.rag_service.search(
                project_id=project_id,
                query="主要角色当前状态",
                top_k=5
            )
            if character_results:
                context["character_states"] = "\n".join([
                    r.get("content", "")[:300] for r in character_results
                ])
            
        except Exception as e:
            logger.warning(f"RAG 获取上下文失败: {e}")
        
        return context
    
    def _get_outline_planner_prompt(self) -> str:
        """获取大纲规划者 Prompt"""
        return """# 角色：大纲规划者

你是小说创作团队的大纲规划者，负责规划章节大纲的整体结构。

## 职责
1. 分析当前剧情进度和蓝图
2. 规划指定范围内每章的主要内容
3. 设计情节起伏和转折点
4. 安排伏笔的埋设和回收

## 输出要求
为每章提供：标题、主要事件、情感走向、关键角色
"""
    
    def _get_outline_writer_prompt(self) -> str:
        """获取大纲撰写者 Prompt"""
        return """# 角色：大纲撰写者

你是小说创作团队的大纲撰写者，负责编写详细的章节大纲。

## 职责
1. 根据规划者的框架编写大纲
2. 为每章提供 100-200 字的内容概要
3. 设计具体的场景和对话要点
4. 确保章节之间的衔接流畅

## 输出格式
每章包含：标题、概要、关键场景、角色行动
"""
    
    def _get_outline_reviewer_prompt(self) -> str:
        """获取大纲审核者 Prompt"""
        return """# 角色：大纲审核者

你是小说创作团队的大纲审核者，负责审核大纲质量。

## 审核维度
1. 整体结构：起承转合是否合理
2. 节奏把控：张弛有度，高潮分布
3. 角色发展：人物弧光是否清晰
4. 伏笔设计：埋设和回收是否合理

## 审核标准
- 通过门槛：75 分
- 需要指出问题并给出改进建议
"""
    
    def update_config(self, **kwargs) -> None:
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
    
    def set_prompts(
        self,
        planner_prompt: Optional[str] = None,
        writer_prompt: Optional[str] = None,
        reviewer_prompt: Optional[str] = None,
    ) -> None:
        """设置自定义 Prompt"""
        if planner_prompt:
            self.planner_prompt = planner_prompt
        if writer_prompt:
            self.writer_prompt = writer_prompt
        if reviewer_prompt:
            self.reviewer_prompt = reviewer_prompt
