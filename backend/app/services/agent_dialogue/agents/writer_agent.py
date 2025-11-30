"""
Writer Agent - 创作者

负责根据规划撰写章节内容，并在对话中与其他 Agent 协作。
"""

from typing import Dict, Any, Optional, List, TYPE_CHECKING
import logging

from .base_agent import BaseAgent
from ..message import Message, AgentRole, MessageType
from ..memory import SharedMemory

if TYPE_CHECKING:
    from ...llm_service import LLMService
    from ...rag_service import RAGService

logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """
    创作者 Agent
    
    职责：
    1. 根据 Planner 的规划撰写章节
    2. 向 Planner 澄清规划细节
    3. 根据 Reviewer 反馈修改内容
    4. 在讨论中提供创作视角的意见
    """
    
    def __init__(
        self,
        llm_service: "LLMService",
        memory: SharedMemory,
        prompt_template: str,
        rag_service: Optional["RAGService"] = None,
    ):
        # Writer 的工具
        tools = [
            {
                "name": "search_writing_style",
                "description": "搜索历史章节的写作风格参考",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "aspect": {
                            "type": "string",
                            "description": "要参考的方面：dialogue, action, description, emotion"
                        }
                    },
                    "required": ["aspect"]
                }
            },
            {
                "name": "get_character_voice",
                "description": "获取角色的说话风格和性格特点",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "character_name": {
                            "type": "string",
                            "description": "角色名称"
                        }
                    },
                    "required": ["character_name"]
                }
            },
            {
                "name": "get_scene_reference",
                "description": "获取类似场景的历史描写参考",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scene_type": {
                            "type": "string",
                            "description": "场景类型：battle, dialogue, romance, mystery"
                        }
                    },
                    "required": ["scene_type"]
                }
            }
        ]
        
        super().__init__(
            role=AgentRole.WRITER,
            llm_service=llm_service,
            memory=memory,
            prompt_template=prompt_template,
            rag_service=rag_service,
            tools=tools,
        )
    
    async def respond(self, task: Message) -> Message:
        """
        响应 Coordinator 分配的任务
        
        主要任务类型：
        1. 初稿撰写：根据规划写章节
        2. 修改内容：根据审核反馈修改
        3. 回应问题：回答其他 Agent 的问题
        """
        instruction = task.content.get("instruction", "")
        context = task.content.get("context", {})
        
        logger.info(f"[Writer] 收到任务: {instruction[:50]}...")
        
        # 判断任务类型
        if "修改" in instruction or "revise" in instruction.lower():
            return await self._handle_revision(task)
        else:
            return await self._handle_drafting(task)
    
    async def _handle_drafting(self, task: Message) -> Message:
        """处理初稿撰写任务"""
        context = task.content.get("context", {})
        
        # 获取 Planner 的规划
        plan = self.memory.get_artifact("current_plan")
        if not plan:
            # 从对话历史中获取
            plan = self.memory.get_latest_plan()
        
        # 构建 Prompt
        prompt = self._build_drafting_prompt(plan, context)
        
        # 调用 LLM
        response = await self._call_llm(prompt, use_tools=True, temperature=0.8)
        
        # 解析响应
        parsed = self._parse_json_response(response)
        
        # 提取可能的问题
        questions = self._extract_questions(parsed)
        mentions = [q.get("to") for q in questions if q.get("to")]
        
        # 保存草稿
        if "content" in parsed:
            self.memory.set_artifact("current_draft", parsed["content"])
        
        return self._create_message(
            type=MessageType.DRAFT,
            content=parsed,
            mentions=mentions
        )
    
    async def _handle_revision(self, task: Message) -> Message:
        """处理修改任务"""
        context = task.content.get("context", {})
        
        # 获取当前草稿和审核结果
        current_draft = self.memory.get_artifact("current_draft")
        review = self.memory.get_latest_review()
        
        # 获取讨论决定（如有）
        decisions = self.memory.decisions
        recent_decision = decisions[-1] if decisions else None
        
        prompt = self._build_revision_prompt(current_draft, review, recent_decision, context)
        
        response = await self._call_llm(prompt, use_tools=True, temperature=0.7)
        
        parsed = self._parse_json_response(response)
        
        # 更新草稿
        if "content" in parsed:
            self.memory.set_artifact("current_draft", parsed["content"])
        
        return self._create_message(
            type=MessageType.REVISION,
            content=parsed
        )
    
    async def answer_question(self, question: Message) -> Message:
        """回答其他 Agent 的问题"""
        q_content = question.content.get("question", "")
        q_context = question.content.get("context", "")
        
        logger.info(f"[Writer] 回答问题: {q_content[:50]}...")
        
        current_draft = self.memory.get_artifact("current_draft")
        
        prompt = f"""{self.prompt_template}

## 当前草稿
{current_draft[:2000] if current_draft else "尚未开始撰写"}

## 问题
{q_content}

## 问题背景
{q_context}

## 你的任务
请回答上述问题。要求：
1. 从创作者角度解释你的选择
2. 如果问题涉及修改，表明你的态度（同意/部分同意/不同意）
3. 如有需要，可以反问或请求澄清

输出 JSON：
{{
    "answer": "你的答复",
    "stance": "agree|partial|disagree|need_clarification",
    "follow_up": "反问或需要澄清的点（如有）"
}}
"""
        
        response = await self._call_llm(prompt)
        parsed = self._parse_json_response(response)
        
        return self._create_message(
            type=MessageType.ANSWER,
            content=parsed,
            reply_to=question.id
        )
    
    async def react_to(self, message: Message) -> Optional[Message]:
        """对消息做出反应"""
        # Writer 对 Planner 的规划调整做出反应
        if message.type == MessageType.PROPOSAL and message.sender == AgentRole.PLANNER:
            proposal = message.content
            
            if proposal.get("plan_revision"):
                logger.info("[Writer] 对规划调整提议做出反应")
                
                prompt = f"""{self.prompt_template}

## Planner 的规划调整提议
{proposal}

## 当前草稿
{self.memory.get_artifact("current_draft")[:1000] if self.memory.get_artifact("current_draft") else "尚未撰写"}

## 你的任务
请评估这个规划调整对你当前创作的影响，并表态：
1. 是否同意这个调整
2. 如果同意，你将如何修改
3. 如果不同意，你的理由

输出 JSON：
{{
    "stance": "agree|partial|disagree",
    "impact_analysis": "对创作的影响",
    "action_plan": "你的行动计划"
}}
"""
                response = await self._call_llm(prompt)
                parsed = self._parse_json_response(response)
                
                return self._create_message(
                    type=MessageType.RESPONSE,
                    content=parsed,
                    mentions=[AgentRole.PLANNER, AgentRole.COORDINATOR]
                )
        
        return None
    
    def _build_drafting_prompt(
        self, 
        plan: Optional[Dict[str, Any]], 
        context: Dict[str, Any]
    ) -> str:
        """构建初稿撰写 Prompt"""
        dialogue_context = self._build_context()
        
        plan_str = ""
        if plan:
            if isinstance(plan, dict):
                plan_str = f"""
- 本章目标: {plan.get('chapter_goal', '未指定')}
- 关键事件: {', '.join(plan.get('key_events', []))}
- 重点角色: {', '.join(plan.get('character_focus', []))}
- 要回收的伏笔: {', '.join(plan.get('foreshadowing_to_resolve', []))}
- 情感走向: {plan.get('emotional_arc', '未指定')}
- 节奏建议: {plan.get('pacing', '未指定')}
"""
            else:
                plan_str = str(plan)
        
        return f"""{self.prompt_template}

## Planner 的规划
{plan_str if plan_str else "Planner 尚未提供规划，请根据项目背景自行规划"}

## 项目背景
- 章节号: 第 {context.get('chapter_number', 1)} 章
- 类型: {context.get('genre', '未知')}
- 字数要求: {context.get('word_count', 3000)} 字左右

## 前情提要
{context.get('previous_summary', '暂无')}

## 角色状态
{context.get('character_states', '暂无')}

## 对话上下文
{dialogue_context}

## 你的任务
请撰写本章内容。要求：
1. 严格遵循 Planner 的规划（如有）
2. 保持与前文的连贯性
3. 如有任何疑问，可以向 @Planner 提问
4. 字数符合要求

## 输出格式
{{
    "content": "章节正文内容（纯文本，不含 Markdown）",
    "title": "章节标题",
    "word_count": 实际字数,
    "key_points": ["本章要点1", "本章要点2"],
    "questions": [
        {{"question": "问题", "to": "planner"}}
    ],
    "notes": "创作笔记（供其他 Agent 参考）"
}}
"""
    
    def _build_revision_prompt(
        self,
        current_draft: Optional[str],
        review: Optional[Dict[str, Any]],
        decision: Optional[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> str:
        """构建修改 Prompt"""
        dialogue_context = self._build_context()
        
        review_str = ""
        if review:
            review_str = f"""
- 评分: {review.get('score', 'N/A')}
- 问题: {review.get('issues', [])}
- 修改计划: {review.get('revision_plan', [])}
"""
        
        decision_str = ""
        if decision:
            decision_str = f"""
- 决定: {decision.get('decision', '')}
- 理由: {decision.get('reason', '')}
"""
        
        return f"""{self.prompt_template}

## 当前草稿
{current_draft[:3000] if current_draft else "无草稿"}

## 审核反馈
{review_str if review_str else "无审核反馈"}

## 协调者决定
{decision_str if decision_str else "无特别决定"}

## 对话上下文
{dialogue_context}

## 你的任务
请根据审核反馈和协调者决定修改章节内容。要求：
1. 针对性地解决每个提出的问题
2. 保持原有优点不变
3. 如有困难或分歧，说明原因

## 输出格式
{{
    "content": "修改后的章节正文",
    "title": "章节标题",
    "word_count": 实际字数,
    "changes_made": [
        {{"issue": "原问题", "fix": "修改方式"}}
    ],
    "notes": "修改说明"
}}
"""

