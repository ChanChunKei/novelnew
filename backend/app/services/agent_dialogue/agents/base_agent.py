"""
Agent 基类

定义所有 Agent 的共同接口和基础功能。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, TYPE_CHECKING
import logging
import json
import re

from ..message import Message, AgentRole, MessageType
from ..memory import SharedMemory
from ....config.ai_function_config import get_function_config, AIFunctionType

if TYPE_CHECKING:
    from ...llm_service import LLMService
    from ...rag_service import RAGService

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Agent 基类
    
    所有 Agent（Planner、Writer、Reviewer）的父类。
    定义了共同的接口和基础功能。
    """
    
    def __init__(
        self,
        role: AgentRole,
        llm_service: "LLMService",
        memory: SharedMemory,
        prompt_template: str,
        rag_service: Optional["RAGService"] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Args:
            role: Agent 角色
            llm_service: LLM 服务
            memory: 共享记忆
            prompt_template: Prompt 模板
            rag_service: RAG 服务（可选）
            tools: 可用工具列表（可选）
        """
        self.role = role
        self.llm_service = llm_service
        self.memory = memory
        self.prompt_template = prompt_template
        self.rag_service = rag_service
        self.tools = tools or []
    
    @abstractmethod
    async def respond(self, task: Message) -> Message:
        """
        响应 Coordinator 分配的任务
        
        这是 Agent 的主要入口方法。
        
        Args:
            task: Coordinator 分配的任务消息
            
        Returns:
            Agent 的响应消息
        """
        pass
    
    @abstractmethod
    async def answer_question(self, question: Message) -> Message:
        """
        回答其他 Agent 的问题
        
        Args:
            question: 问题消息
            
        Returns:
            回答消息
        """
        pass
    
    async def react_to(self, message: Message) -> Optional[Message]:
        """
        对其他消息做出反应（可选）
        
        默认实现不做反应，子类可以覆盖。
        
        Args:
            message: 要反应的消息
            
        Returns:
            反应消息，或 None 表示不反应
        """
        return None
    
    async def participate_discussion(self, topic: str, context: List[Message]) -> Message:
        """
        参与讨论
        
        Args:
            topic: 讨论主题
            context: 讨论上下文消息
            
        Returns:
            讨论发言
        """
        prompt = self._build_discussion_prompt(topic, context)
        response = await self._call_llm(prompt)
        
        return self._create_message(
            type=MessageType.RESPONSE,
            content={"opinion": response, "topic": topic}
        )
    
    def _build_context(self) -> str:
        """构建上下文字符串"""
        return self.memory.to_context_string(self.role)
    
    def _build_base_prompt(self, instruction: str, additional_context: str = "") -> str:
        """
        构建基础 Prompt
        
        Args:
            instruction: 具体指令
            additional_context: 额外上下文
        """
        dialogue_context = self._build_context()
        
        return f"""{self.prompt_template}

## 当前对话上下文
{dialogue_context}

## 额外信息
{additional_context}

## 你的任务
{instruction}
"""
    
    def _build_discussion_prompt(self, topic: str, context: List[Message]) -> str:
        """构建讨论 Prompt"""
        context_str = "\n".join([m.format_for_display() for m in context])
        
        # 检查是否是分卷决策讨论
        is_volume_decision = "分卷" in topic or "新卷" in topic
        
        if is_volume_decision:
            return f"""{self.prompt_template}

## 讨论主题
{topic}

## 讨论上下文
{context_str}

## 你的任务
请就是否分卷以及卷名发表你的专业意见。要求：
1. 从你的角色专业角度分析是否应该分卷
2. 如果同意分卷，给出你建议的卷名（5-10字，有文学性）
3. 说明你的理由

输出 JSON：
{{
    "should_split": true或false,
    "volume_title": "你建议的卷名（如果分卷）",
    "reason": "你的理由（简洁明了）"
}}
"""
        else:
            return f"""{self.prompt_template}

## 讨论主题
{topic}

## 讨论上下文
{context_str}

## 你的任务
请就上述主题发表你的专业意见。要求：
1. 从你的角色专业角度出发
2. 明确表达同意或不同意
3. 如有建议，给出具体可执行的方案
4. 简洁明了，不超过 200 字

输出格式：
{{
    "stance": "agree|disagree|partial",
    "opinion": "你的意见",
    "suggestion": "具体建议（如有）"
}}
"""
    
    async def _call_llm(
        self, 
        prompt: str, 
        use_tools: bool = False,
        temperature: float = 0.7
    ) -> str:
        """
        调用 LLM
        
        Args:
            prompt: Prompt
            use_tools: 是否使用工具
            temperature: 温度
            
        Returns:
            LLM 响应
        """
        messages = [{"role": "user", "content": prompt}]
        
        # 从 ai_function_config 获取配置（和 3-Agent 模式一致）
        config = get_function_config(AIFunctionType.CHAPTER_CONTENT_WRITING)
        provider = config.primary.provider
        model = config.primary.model
        
        context = self.memory.context if isinstance(self.memory.context, dict) else {}

        kwargs = {
            "provider": provider,
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
            "user_id": context.get("user_id"),
        }
        
        if use_tools and self.tools:
            kwargs["tools"] = self.tools
        
        # 最多两轮工具调用
        for _ in range(2):
            response = await self.llm_service.invoke(**kwargs)

            # 优先尝试解析 JSON
            parsed = None
            try:
                parsed = json.loads(response)
            except Exception:
                pass

            # 如果有工具调用且允许使用工具
            if use_tools and parsed and isinstance(parsed, dict) and parsed.get("tool_calls"):
                tool_calls = parsed["tool_calls"]
                tool_results = []
                for tc in tool_calls:
                    tool_results.append(await self._execute_tool_call(tc))

                # 追加对话，再次调用 LLM
                kwargs["messages"] = kwargs["messages"] + [
                    {
                        "role": "assistant",
                        "content": parsed.get("content", ""),
                        "tool_calls": tool_calls
                    },
                    *[
                        {
                            "role": "tool",
                            "tool_call_id": tc.get("id", f"tool_{idx}"),
                            "content": res
                        }
                        for idx, (tc, res) in enumerate(zip(tool_calls, tool_results))
                    ]
                ]
                continue

            return response

        return response

    async def _execute_tool_call(self, tool_call: Dict[str, Any]) -> str:
        """
        简单的工具执行器（仅支持 planner 工具）
        """
        name = (tool_call.get("function") or {}).get("name")
        args_raw = (tool_call.get("function") or {}).get("arguments", {})

        try:
            args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
        except Exception:
            args = {}

        project_id = None
        if isinstance(self.memory.context, dict):
            project_id = self.memory.context.get("project_id")

        if name == "search_chapters":
            query = args.get("query") or args.get("keyword")
            if not query:
                return "错误：缺少搜索关键词"
            if not self.rag_service:
                return "⚠️ RAG 未配置，无法搜索历史章节"
            try:
                results = await self.rag_service.search(project_id=project_id, query=query, top_k=3)
                if not results:
                    return "未找到相关章节"
                formatted = []
                for r in results:
                    chapter_title = getattr(r, "chapter_title", "") or (r.get("chapter_title") if isinstance(r, dict) else "")
                    snippet = getattr(r, "content_snippet", "") or (r.get("content_snippet") if isinstance(r, dict) else r.get("content", "") if isinstance(r, dict) else "")
                    formatted.append(f"章节: {chapter_title}\n相关片段: {snippet[:300]}...")
                return "\n\n".join(formatted)
            except Exception as e:
                return f"搜索失败: {e}"

        if name == "check_plot_consistency":
            element = args.get("element") or args.get("plot_point") or ""
            if not element:
                return "错误：缺少 element"
            if not self.rag_service:
                return "⚠️ RAG 未配置，无法检查剧情一致性"
            try:
                results = await self.rag_service.search(project_id=project_id, query=element, top_k=3)
                if not results:
                    return f"未找到与「{element}」相关的描述"
                formatted = []
                for r in results:
                    snippet = getattr(r, "content_snippet", "") or (r.get("content_snippet") if isinstance(r, dict) else "")
                    formatted.append(f"- {snippet[:200]}")
                return "以下是相关描述，请检查是否矛盾：\n" + "\n".join(formatted)
            except Exception as e:
                return f"一致性检查失败: {e}"

        if name == "find_foreshadowing":
            scope = args.get("scope", "recent")
            query = "未回收的伏笔" if scope == "critical" else "伏笔"
            if not self.rag_service:
                return "⚠️ RAG 未配置，无法查找伏笔"
            try:
                results = await self.rag_service.search(project_id=project_id, query=query, top_k=5)
                if not results:
                    return "未找到明显的伏笔线索"
                formatted = []
                for r in results:
                    chapter_title = getattr(r, "chapter_title", "") or (r.get("chapter_title") if isinstance(r, dict) else "")
                    snippet = getattr(r, "content_snippet", "") or (r.get("content_snippet") if isinstance(r, dict) else "")
                    formatted.append(f"{chapter_title}: {snippet[:200]}...")
                return "\n".join(formatted)
            except Exception as e:
                return f"查找伏笔失败: {e}"

        if name == "verify_character_action":
            character = args.get("character_name") or args.get("character")
            action = args.get("action") or args.get("action_description")
            if not character or not action:
                return "错误：缺少 character_name 或 action"
            if not self.rag_service:
                return "⚠️ RAG 未配置，无法验证角色行为"
            try:
                query = f"{character} {action}"
                results = await self.rag_service.search(project_id=project_id, query=query, top_k=3)
                if not results:
                    return f"未找到【{character}】相关行为的历史参考"
                formatted = []
                for r in results:
                    snippet = getattr(r, "content_snippet", "") or (r.get("content_snippet") if isinstance(r, dict) else "")
                    formatted.append(snippet[:200])
                return "以下为历史参考，请核查是否OOC：\n" + "\n---\n".join(formatted)
            except Exception as e:
                return f"验证角色行为失败: {e}"

        if name == "verify_timeline":
            events = args.get("events") or []
            if not events or not isinstance(events, list):
                return "错误：缺少 events 列表"
            if not self.rag_service:
                return "⚠️ RAG 未配置，无法验证时间线"
            try:
                formatted = []
                for ev in events[:5]:
                    results = await self.rag_service.search(project_id=project_id, query=str(ev), top_k=2)
                    if results:
                        for r in results:
                            snippet = getattr(r, "content_snippet", "") or (r.get("content_snippet") if isinstance(r, dict) else "")
                            formatted.append(f"{ev}: {snippet[:200]}")
                if not formatted:
                    return "未找到足够的时间线参考，请人工判断事件顺序。"
                return "时间相关参考（请检查顺序/间隔是否合理）：\n" + "\n".join(formatted)
            except Exception as e:
                return f"时间线验证失败: {e}"

        if name == "verify_world_rules":
            element = args.get("element") or ""
            if not element:
                return "错误：缺少 element"
            blueprint_summary = None
            if isinstance(self.memory.context, dict):
                blueprint_summary = self.memory.context.get("blueprint_summary")
            parts = []
            if blueprint_summary:
                parts.append(f"蓝图设定：{blueprint_summary[:500]}")
            if self.rag_service:
                try:
                    results = await self.rag_service.search(project_id=project_id, query=element, top_k=3)
                    for r in results or []:
                        snippet = getattr(r, "content_snippet", "") or (r.get("content_snippet") if isinstance(r, dict) else "")
                        parts.append(f"设定参考：{snippet[:200]}")
                except Exception as e:
                    parts.append(f"RAG 查询失败: {e}")
            if not parts:
                return f"未找到关于「{element}」的设定参考，请人工比对世界观。"
            return "\n".join(parts)

        if name == "check_plot_holes":
            summary = args.get("content_summary") or ""
            if not summary:
                return "错误：缺少 content_summary"
            if not self.rag_service:
                return "⚠️ RAG 未配置，无法检索剧情漏洞参考"
            try:
                results = await self.rag_service.search(project_id=project_id, query="剧情矛盾 漏洞", top_k=3)
                formatted = []
                for r in results or []:
                    snippet = getattr(r, "content_snippet", "") or (r.get("content_snippet") if isinstance(r, dict) else "")
                    formatted.append(snippet[:200])
                if not formatted:
                    return "未检出明显剧情漏洞，请结合审核评分判断。"
                return "以下是可能的矛盾点参考，请结合当前摘要核查：\n" + "\n---\n".join(formatted)
            except Exception as e:
                return f"剧情漏洞检查失败: {e}"

        if name == "search_writing_style":
            aspect = args.get("aspect") or "dialogue"
            if not self.rag_service:
                return "⚠️ RAG 未配置，无法检索写作风格参考"
            try:
                results = await self.rag_service.search(
                    project_id=project_id,
                    query=f"写作风格参考 {aspect}",
                    top_k=3
                )
                if not results:
                    return f"未找到与 {aspect} 相关的写作风格参考"
                formatted = []
                for r in results:
                    snippet = getattr(r, "content_snippet", "") or (r.get("content_snippet") if isinstance(r, dict) else "")
                    formatted.append(snippet[:300])
                return "\n---\n".join(formatted)
            except Exception as e:
                return f"写作风格检索失败: {e}"

        if name == "get_character_voice":
            character_name = args.get("character_name") or ""
            if not character_name:
                return "错误：缺少 character_name"
            if not self.rag_service:
                return "⚠️ RAG 未配置，无法获取角色语气"
            try:
                results = await self.rag_service.search(
                    project_id=project_id,
                    query=f"{character_name} 说话风格",
                    top_k=3
                )
                if not results:
                    return f"未找到角色【{character_name}】的语气参考"
                formatted = []
                for r in results:
                    snippet = getattr(r, "content_snippet", "") or (r.get("content_snippet") if isinstance(r, dict) else "")
                    formatted.append(snippet[:200])
                return "\n".join(formatted)
            except Exception as e:
                return f"角色语气查询失败: {e}"

        if name == "get_scene_reference":
            scene_type = args.get("scene_type") or ""
            if not scene_type:
                return "错误：缺少 scene_type"
            if not self.rag_service:
                return "⚠️ RAG 未配置，无法获取场景参考"
            try:
                results = await self.rag_service.search(
                    project_id=project_id,
                    query=f"{scene_type} 场景描写示例",
                    top_k=3
                )
                if not results:
                    return f"未找到 {scene_type} 场景的参考"
                formatted = []
                for r in results:
                    snippet = getattr(r, "content_snippet", "") or (r.get("content_snippet") if isinstance(r, dict) else "")
                    formatted.append(snippet[:200])
                return "\n---\n".join(formatted)
            except Exception as e:
                return f"场景参考查询失败: {e}"

        return f"⚠️ 未知工具或未实现: {name}"
    
    async def _call_rag(self, query: str, project_id: int, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        调用 RAG 检索
        
        Args:
            query: 查询
            project_id: 项目 ID
            top_k: 返回数量
            
        Returns:
            检索结果
        """
        if not self.rag_service:
            return []
        
        try:
            results = await self.rag_service.search(
                project_id=project_id,
                query=query,
                top_k=top_k
            )
            return results
        except Exception as e:
            logger.warning(f"RAG 检索失败: {e}")
            return []
    
    def _create_message(
        self,
        type: MessageType,
        content: Dict[str, Any],
        receiver: Optional[AgentRole] = None,
        mentions: Optional[List[AgentRole]] = None,
        reply_to: Optional[str] = None
    ) -> Message:
        """创建消息"""
        return Message(
            sender=self.role,
            receiver=receiver,
            type=type,
            content=content,
            mentions=mentions or [],
            reply_to=reply_to
        )
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        解析 JSON 响应
        
        处理可能的 markdown 代码块包装
        """
        # 移除可能的 markdown 代码块
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        response = response.strip()
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}")
            # 尝试提取 JSON 部分
            match = re.search(r'\{[\s\S]*\}', response)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
            return {"raw": response, "parse_error": str(e)}
    
    def _extract_mentions(self, text: str) -> List[AgentRole]:
        """从文本中提取 @mentions"""
        mentions = []
        patterns = {
            r'@planner': AgentRole.PLANNER,
            r'@writer': AgentRole.WRITER,
            r'@reviewer': AgentRole.REVIEWER,
            r'@coordinator': AgentRole.COORDINATOR,
        }
        
        text_lower = text.lower()
        for pattern, role in patterns.items():
            if re.search(pattern, text_lower):
                mentions.append(role)
        
        return mentions
    
    def _extract_questions(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从响应中提取问题"""
        questions = []
        
        # 检查是否有 questions 字段
        if "questions" in content:
            for q in content["questions"]:
                if isinstance(q, dict):
                    questions.append(q)
                elif isinstance(q, str):
                    mentions = self._extract_mentions(q)
                    questions.append({
                        "question": q,
                        "to": mentions[0] if mentions else None
                    })
        
        # 检查是否有 @mentions 形式的问题
        if "text" in content:
            mentions = self._extract_mentions(content["text"])
            if mentions and "?" in content["text"]:
                questions.append({
                    "question": content["text"],
                    "to": mentions[0]
                })
        
        return questions
