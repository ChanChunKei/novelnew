"""
Reviewer Agent - 审核者

负责审核章节质量，提供结构化的反馈和修改建议。
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


class ReviewerAgent(BaseAgent):
    """
    审核者 Agent
    
    职责：
    1. 审核章节质量（剧情、角色、文笔、节奏）
    2. 提供结构化的修改建议
    3. 使用工具验证内容一致性
    4. 决定是否通过
    """
    
    def __init__(
        self,
        llm_service: "LLMService",
        memory: SharedMemory,
        prompt_template: str,
        rag_service: Optional["RAGService"] = None,
        approval_threshold: int = 80,
    ):
        # Reviewer 的工具
        tools = [
            {
                "name": "verify_character_action",
                "description": "验证角色行为是否符合其人设和历史表现",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "character_name": {
                            "type": "string",
                            "description": "角色名称"
                        },
                        "action": {
                            "type": "string",
                            "description": "要验证的行为"
                        }
                    },
                    "required": ["character_name", "action"]
                }
            },
            {
                "name": "verify_timeline",
                "description": "验证时间线是否正确，事件顺序是否合理",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "events": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要验证的事件列表"
                        }
                    },
                    "required": ["events"]
                }
            },
            {
                "name": "verify_world_rules",
                "description": "验证内容是否符合世界观设定",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "element": {
                            "type": "string",
                            "description": "要验证的设定元素"
                        }
                    },
                    "required": ["element"]
                }
            },
            {
                "name": "check_plot_holes",
                "description": "检查剧情漏洞",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content_summary": {
                            "type": "string",
                            "description": "内容摘要"
                        }
                    },
                    "required": ["content_summary"]
                }
            }
        ]
        
        super().__init__(
            role=AgentRole.REVIEWER,
            llm_service=llm_service,
            memory=memory,
            prompt_template=prompt_template,
            rag_service=rag_service,
            tools=tools,
        )
        
        self.approval_threshold = approval_threshold
    
    async def respond(self, task: Message) -> Message:
        """
        响应 Coordinator 分配的任务
        
        主要任务：审核章节内容
        """
        instruction = task.content.get("instruction", "")
        context = task.content.get("context", {})
        
        logger.info(f"[Reviewer] 收到任务: {instruction[:50]}...")
        
        # 获取要审核的内容
        draft = self.memory.get_artifact("current_draft")
        if not draft:
            draft = self.memory.get_latest_draft()
        
        if not draft:
            return self._create_message(
                type=MessageType.REVIEW,
                content={
                    "error": "没有找到要审核的内容",
                    "approved": False
                }
            )
        
        # 获取规划用于对比
        plan = self.memory.get_artifact("current_plan")
        
        # 构建审核 Prompt
        prompt = self._build_review_prompt(draft, plan, context)
        
        # 调用 LLM（启用工具）
        response = await self._call_llm(prompt, use_tools=True, temperature=0.3)
        
        # 解析响应
        parsed = self._parse_json_response(response)
        
        # 判断是否通过
        score = parsed.get("score", 0)
        approved = score >= self.approval_threshold
        parsed["approved"] = approved
        
        # 判断是否需要 Planner 介入
        needs_planner = self._check_needs_planner(parsed)
        parsed["needs_planner_input"] = needs_planner
        
        mentions = []
        if needs_planner:
            mentions.append(AgentRole.PLANNER)
        if not approved:
            mentions.append(AgentRole.WRITER)
        
        return self._create_message(
            type=MessageType.REVIEW,
            content=parsed,
            mentions=mentions
        )
    
    async def answer_question(self, question: Message) -> Message:
        """回答其他 Agent 的问题"""
        q_content = question.content.get("question", "")
        
        logger.info(f"[Reviewer] 回答问题: {q_content[:50]}...")
        
        latest_review = self.memory.get_latest_review()
        
        prompt = f"""{self.prompt_template}

## 最近的审核结果
{latest_review if latest_review else "尚未审核"}

## 问题
{q_content}

## 你的任务
请回答上述问题。要求：
1. 解释你的审核标准和依据
2. 如果被质疑，重新评估是否需要调整意见
3. 保持客观公正

输出 JSON：
{{
    "answer": "你的答复",
    "stance_change": "是否改变立场（如有）",
    "revised_suggestion": "修改后的建议（如有）"
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
        # Reviewer 对 Writer 的修改做出快速反馈
        if message.type == MessageType.REVISION and message.sender == AgentRole.WRITER:
            revision = message.content
            changes = revision.get("changes_made", [])
            
            if changes:
                logger.info("[Reviewer] 对修改做出快速反馈")
                
                prompt = f"""{self.prompt_template}

## Writer 的修改
{changes}

## 我之前的审核意见
{self.memory.get_latest_review()}

## 你的任务
快速评估这些修改是否解决了之前提出的问题。
不需要完整重新审核，只需确认修改是否到位。

输出 JSON：
{{
    "changes_addressed": ["已解决的问题"],
    "still_pending": ["仍需处理的问题"],
    "quick_verdict": "满意|基本满意|需要进一步修改"
}}
"""
                response = await self._call_llm(prompt, temperature=0.3)
                parsed = self._parse_json_response(response)
                
                return self._create_message(
                    type=MessageType.RESPONSE,
                    content=parsed,
                    mentions=[AgentRole.COORDINATOR]
                )
        
        return None
    
    def _build_review_prompt(
        self,
        draft: Any,
        plan: Optional[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> str:
        """构建审核 Prompt"""
        dialogue_context = self._build_context()
        
        # 处理草稿内容
        if isinstance(draft, dict):
            content = draft.get("content", str(draft))
            title = draft.get("title", "")
        else:
            content = str(draft)
            title = ""
        
        plan_str = ""
        if plan:
            plan_str = f"""
- 本章目标: {plan.get('chapter_goal', '未指定')}
- 关键事件: {', '.join(plan.get('key_events', []))}
- 重点角色: {', '.join(plan.get('character_focus', []))}
"""
        
        return f"""{self.prompt_template}

## 待审核内容
标题: {title}
正文:
{content[:4000]}{"..." if len(content) > 4000 else ""}

## Planner 的规划（对照检查）
{plan_str if plan_str else "无规划信息"}

## 项目背景
- 章节号: 第 {context.get('chapter_number', 1)} 章
- 类型: {context.get('genre', '未知')}

## 对话上下文
{dialogue_context}

## 审核要求
请从以下维度审核：
1. **剧情逻辑** (0-25分): 情节是否合理，有无漏洞
2. **角色塑造** (0-25分): 角色行为是否符合人设
3. **文笔质量** (0-25分): 语言表达、描写能力
4. **节奏把控** (0-25分): 叙事节奏、张弛有度

通过门槛: {self.approval_threshold} 分

## 输出格式
{{
    "score": 总分(0-100),
    "dimension_scores": {{
        "plot": 分数,
        "character": 分数,
        "writing": 分数,
        "pacing": 分数
    }},
    "approved": true/false,
    "strengths": ["优点1", "优点2"],
    "issues": [
        {{
            "severity": "critical|major|minor",
            "category": "plot|character|writing|pacing",
            "description": "问题描述",
            "location": "问题位置（引用原文）"
        }}
    ],
    "revision_plan": [
        {{
            "priority": 1,
            "issue": "问题",
            "instruction": "修改指令",
            "location": "位置"
        }}
    ],
    "questions_for_planner": [
        "需要 Planner 澄清的问题（如有）"
    ],
    "overall_comment": "总体评价"
}}
"""
    
    def _check_needs_planner(self, review: Dict[str, Any]) -> bool:
        """检查是否需要 Planner 介入"""
        # 有明确的问题要问 Planner
        if review.get("questions_for_planner"):
            return True
        
        # 存在严重的剧情问题
        issues = review.get("issues", [])
        for issue in issues:
            if issue.get("severity") == "critical" and issue.get("category") == "plot":
                return True
        
        # 评分很低
        if review.get("score", 100) < 50:
            return True
        
        return False

