"""
Planner Agent - 规划者

负责分析项目、规划章节结构，并在对话过程中提供规划建议。
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


class PlannerAgent(BaseAgent):
    """
    规划者 Agent
    
    职责：
    1. 分析项目背景和当前进度
    2. 规划章节结构和内容方向
    3. 回答其他 Agent 关于规划的问题
    4. 在讨论中提供规划视角的意见
    """
    
    def __init__(
        self,
        llm_service: "LLMService",
        memory: SharedMemory,
        prompt_template: str,
        rag_service: Optional["RAGService"] = None,
    ):
        # Planner 的工具
        tools = [
            {
                "name": "search_chapters",
                "description": "搜索历史章节，查找相关情节和设定",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词或问题"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "check_plot_consistency",
                "description": "检查剧情一致性，查看某个设定或事件在历史中的记录",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "element": {
                            "type": "string",
                            "description": "要检查的剧情元素"
                        }
                    },
                    "required": ["element"]
                }
            },
            {
                "name": "find_foreshadowing",
                "description": "查找未回收的伏笔",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scope": {
                            "type": "string",
                            "description": "查找范围：all, recent, critical",
                            "enum": ["all", "recent", "critical"]
                        }
                    },
                    "required": ["scope"]
                }
            }
        ]
        
        super().__init__(
            role=AgentRole.PLANNER,
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
        1. 初始规划：分析项目，制定章节计划
        2. 澄清请求：回答关于规划的问题
        3. 调整规划：根据反馈调整计划
        """
        instruction = task.content.get("instruction", "")
        context = task.content.get("context", {})
        
        logger.info(f"[Planner] 收到任务: {instruction[:50]}...")
        
        # 获取项目上下文
        project_context = await self._get_project_context(context)
        
        # 构建 Prompt
        prompt = self._build_planning_prompt(instruction, project_context, context)
        
        # 调用 LLM
        response = await self._call_llm(prompt, use_tools=True)
        
        # 解析响应
        parsed = self._parse_json_response(response)
        
        # 检查是否有问题要问其他 Agent
        questions = self._extract_questions(parsed)
        mentions = []
        if questions:
            mentions = [q.get("to") for q in questions if q.get("to")]
        
        # 保存规划到记忆
        if "plan" in parsed:
            self.memory.set_artifact("current_plan", parsed["plan"])
        
        return self._create_message(
            type=MessageType.RESPONSE,
            content=parsed,
            mentions=mentions
        )
    
    async def answer_question(self, question: Message) -> Message:
        """回答其他 Agent 关于规划的问题"""
        q_content = question.content.get("question", "")
        q_context = question.content.get("context", "")
        
        logger.info(f"[Planner] 回答问题: {q_content[:50]}...")
        
        # 获取当前规划
        current_plan = self.memory.get_artifact("current_plan")
        
        prompt = f"""{self.prompt_template}

## 当前规划
{current_plan if current_plan else "暂无明确规划"}

## 对话上下文
{self._build_context()}

## 问题
{q_content}

## 问题背景
{q_context}

## 你的任务
请回答上述问题。要求：
1. 基于你的规划给出明确答复
2. 如果需要调整规划，说明调整内容
3. 如果问题涉及创作细节，可以给出建议但表明由 Writer 决定

输出 JSON：
{{
    "answer": "你的答复",
    "plan_adjustment": "规划调整（如有）",
    "suggestions_for_writer": "给 Writer 的建议（如有）"
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
        # Planner 对审核结果做出反应
        if message.type == MessageType.REVIEW and message.sender == AgentRole.REVIEWER:
            review_content = message.content
            
            # 如果审核提到规划问题
            issues = review_content.get("issues", [])
            plan_related = any(
                "规划" in str(issue) or "结构" in str(issue) or "矛盾" in str(issue)
                for issue in issues
            )
            
            if plan_related or review_content.get("needs_planner_input"):
                logger.info("[Planner] 检测到规划相关问题，主动回应")
                
                prompt = f"""{self.prompt_template}

## 审核结果
{review_content}

## 当前规划
{self.memory.get_artifact("current_plan")}

## 你的任务
审核中提到了与规划相关的问题，请：
1. 分析问题根源
2. 提出规划调整建议
3. 说明如何避免类似问题

输出 JSON：
{{
    "analysis": "问题分析",
    "plan_revision": "规划调整建议",
    "prevention": "预防措施"
}}
"""
                response = await self._call_llm(prompt)
                parsed = self._parse_json_response(response)
                
                return self._create_message(
                    type=MessageType.PROPOSAL,
                    content=parsed,
                    mentions=[AgentRole.WRITER, AgentRole.COORDINATOR]
                )
        
        return None
    
    def _build_planning_prompt(
        self, 
        instruction: str, 
        project_context: Dict[str, Any],
        task_context: Dict[str, Any]
    ) -> str:
        """构建规划 Prompt"""
        dialogue_context = self._build_context()
        
        return f"""{self.prompt_template}

## 项目信息
- 项目名称: {project_context.get('project_name', '未知')}
- 当前章节: 第 {project_context.get('current_chapter', 1)} 章
- 总计划章节: {project_context.get('total_chapters', '未设定')}
- 类型: {project_context.get('genre', '未知')}

## 蓝图摘要
{project_context.get('blueprint_summary', '暂无蓝图')}

## 最近章节摘要
{project_context.get('recent_summary', '暂无')}

## 角色状态
{project_context.get('character_states', '暂无')}

## 未回收伏笔
{project_context.get('open_foreshadowing', '暂无')}

## 对话上下文
{dialogue_context}

## 你的任务
{instruction}

## 输出要求
请输出 JSON 格式：
{{
    "analysis": "项目分析（当前进度、关键点）",
    "plan": {{
        "chapter_goal": "本章目标",
        "key_events": ["事件1", "事件2"],
        "character_focus": ["角色1", "角色2"],
        "foreshadowing_to_resolve": ["伏笔1"],
        "new_foreshadowing": ["新伏笔"],
        "emotional_arc": "情感走向",
        "pacing": "节奏建议"
    }},
    "suggestions_for_writer": [
        "建议1",
        "建议2"
    ],
    "questions": [
        {{"question": "问题内容", "to": "writer|reviewer"}}
    ],
    "warnings": ["需要注意的点"]
}}
"""
    
    async def _get_project_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """获取项目上下文"""
        project_id = context.get("project_id")
        
        result = {
            "project_name": context.get("project_name", "未知项目"),
            "current_chapter": context.get("chapter_number", 1),
            "total_chapters": context.get("total_chapters"),
            "genre": context.get("genre", ""),
            "blueprint_summary": context.get("blueprint_summary", ""),
            "recent_summary": context.get("recent_summary", ""),
            "character_states": context.get("character_states", ""),
            "open_foreshadowing": context.get("open_foreshadowing", ""),
        }
        
        # 如果有 RAG 服务，尝试获取更多上下文
        if self.rag_service and project_id:
            try:
                # 获取未回收伏笔
                foreshadowing = await self._call_rag(
                    "未回收的伏笔和悬念",
                    project_id,
                    top_k=5
                )
                if foreshadowing:
                    result["open_foreshadowing"] = "\n".join([
                        f"- {f.get('content', '')[:100]}" for f in foreshadowing
                    ])
            except Exception as e:
                logger.warning(f"获取项目上下文失败: {e}")
        
        return result

