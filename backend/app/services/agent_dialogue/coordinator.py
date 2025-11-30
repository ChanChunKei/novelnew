"""
Coordinator - 协调者

负责协调 Planner、Writer、Reviewer 三个 Agent 的对话。
这是讨论模式的核心调度器。
"""

from typing import Dict, Any, Optional, List, TYPE_CHECKING
import logging
import json
import asyncio

from .message import Message, AgentRole, MessageType, create_task_message
from .memory import SharedMemory
from .state import DialogueState, DialoguePhase, DialogueConfig
from .agents.planner_agent import PlannerAgent
from .agents.writer_agent import WriterAgent
from .agents.reviewer_agent import ReviewerAgent

if TYPE_CHECKING:
    from ..llm_service import LLMService
    from ..rag_service import RAGService

logger = logging.getLogger(__name__)


class Coordinator:
    """
    对话协调者
    
    负责：
    1. 决定发言顺序
    2. 分配任务
    3. 路由问题
    4. 召集讨论
    5. 仲裁冲突
    6. 判断结束
    """
    
    def __init__(
        self,
        llm_service: "LLMService",
        rag_service: Optional["RAGService"],
        planner_prompt: str,
        writer_prompt: str,
        reviewer_prompt: str,
        config: Optional[DialogueConfig] = None,
    ):
        self.llm_service = llm_service
        self.rag_service = rag_service
        self.config = config or DialogueConfig()
        
        # 初始化共享记忆
        self.memory = SharedMemory()
        
        # 初始化状态
        self.state = DialogueState(max_iterations=self.config.max_iterations)
        
        # 初始化 Agents
        self.planner = PlannerAgent(
            llm_service=llm_service,
            memory=self.memory,
            prompt_template=planner_prompt,
            rag_service=rag_service,
        )
        
        self.writer = WriterAgent(
            llm_service=llm_service,
            memory=self.memory,
            prompt_template=writer_prompt,
            rag_service=rag_service,
        )
        
        self.reviewer = ReviewerAgent(
            llm_service=llm_service,
            memory=self.memory,
            prompt_template=reviewer_prompt,
            rag_service=rag_service,
            approval_threshold=self.config.approval_threshold,
        )
        
        self.agents = {
            AgentRole.PLANNER: self.planner,
            AgentRole.WRITER: self.writer,
            AgentRole.REVIEWER: self.reviewer,
        }
    
    async def run_dialogue(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行完整的对话流程
        
        Args:
            context: 项目上下文（project_id, chapter_number, etc.）
            
        Returns:
            最终产出（章节内容、对话记录等）
        """
        logger.info("=" * 50)
        logger.info("🎬 [Coordinator] 开始协调对话")
        logger.info("=" * 50)
        
        # 初始化
        self.memory.context = context
        self.state.start()
        
        try:
            # 阶段 1：规划
            await self._phase_planning(context)
            
            # 阶段 2-N：起草 → 审核 → (讨论 →) 修改 循环
            while self.state.can_continue():
                self.state.increment_iteration()
                logger.info(f"\n{'='*40}")
                logger.info(f"📍 迭代 {self.state.iteration}/{self.state.max_iterations}")
                logger.info(f"{'='*40}")
                
                # 起草
                await self._phase_drafting(context)
                
                # 处理 Writer 的问题（如有）
                await self._handle_pending_questions()
                
                # 审核
                review_passed = await self._phase_reviewing(context)
                
                if review_passed:
                    logger.info("✅ 审核通过！")
                    
                    # 检查是否需要分卷决策
                    if self.config.enable_volume_decision and self._should_check_volume_split(context):
                        await self._phase_volume_decision(context)
                    
                    self.state.transition_to(DialoguePhase.APPROVED)
                    break
                
                # 检查是否需要三方讨论
                if self._needs_discussion():
                    await self._phase_discussing()
                
                # 修改
                await self._phase_revising(context)
            
            # 结束
            return await self._phase_end()
            
        except asyncio.TimeoutError:
            logger.error("对话超时")
            self.state.record_error("对话超时")
            self.state.transition_to(DialoguePhase.FAILED)
            return self._create_error_result("对话超时")
            
        except Exception as e:
            logger.error(f"对话异常: {e}", exc_info=True)
            self.state.record_error(str(e))
            self.state.transition_to(DialoguePhase.FAILED)
            return self._create_error_result(str(e))
    
    async def _phase_planning(self, context: Dict[str, Any]) -> None:
        """规划阶段"""
        self.state.transition_to(DialoguePhase.PLANNING, AgentRole.PLANNER)
        logger.info("\n📋 阶段: 规划")
        
        # 创建任务
        task = create_task_message(
            receiver=AgentRole.PLANNER,
            instruction="请分析项目背景，规划本章节的结构和内容方向。",
            context=context
        )
        self.memory.add_message(task)
        
        # Planner 响应
        response = await self.planner.respond(task)
        self.memory.add_message(response)
        
        logger.info(f"[Planner] 规划完成")
        
        # 处理 Planner 可能的问题
        if response.mentions:
            await self._route_questions_from(response)
    
    async def _phase_drafting(self, context: Dict[str, Any]) -> None:
        """起草阶段"""
        self.state.transition_to(DialoguePhase.DRAFTING, AgentRole.WRITER)
        logger.info("\n✍️ 阶段: 起草")
        
        task = create_task_message(
            receiver=AgentRole.WRITER,
            instruction="请根据 Planner 的规划撰写章节内容。",
            context=context
        )
        self.memory.add_message(task)
        
        response = await self.writer.respond(task)
        self.memory.add_message(response)
        
        logger.info(f"[Writer] 初稿完成")
        
        # 保存草稿到状态
        self.state.current_draft = response.content
    
    async def _phase_reviewing(self, context: Dict[str, Any]) -> bool:
        """审核阶段，返回是否通过"""
        self.state.transition_to(DialoguePhase.REVIEWING, AgentRole.REVIEWER)
        logger.info("\n📝 阶段: 审核")
        
        task = create_task_message(
            receiver=AgentRole.REVIEWER,
            instruction="请审核 Writer 的章节内容。",
            context=context
        )
        self.memory.add_message(task)
        
        response = await self.reviewer.respond(task)
        self.memory.add_message(response)
        
        # 保存审核结果
        self.state.current_review = response.content
        
        score = response.content.get("score", 0)
        self.state.record_score(score)
        
        approved = response.content.get("approved", False)
        logger.info(f"[Reviewer] 评分: {score}, 通过: {approved}")
        
        # 让 Planner 对审核结果做出反应
        planner_reaction = await self.planner.react_to(response)
        if planner_reaction:
            self.memory.add_message(planner_reaction)
            logger.info("[Planner] 对审核结果做出了反应")
        
        return approved
    
    async def _phase_discussing(self) -> None:
        """三方讨论阶段"""
        self.state.transition_to(DialoguePhase.DISCUSSING)
        logger.info("\n💬 阶段: 三方讨论")
        
        # 确定讨论主题
        topic = self._identify_discussion_topic()
        logger.info(f"讨论主题: {topic}")
        
        # 广播讨论请求
        broadcast = Message(
            sender=AgentRole.COORDINATOR,
            type=MessageType.CALL_DISCUSSION,
            content={
                "topic": topic,
                "instruction": "请就上述问题发表你的专业意见。"
            }
        )
        self.memory.add_message(broadcast)
        
        # 收集各方意见
        discussion_context = self.memory.get_all_messages()[-10:]  # 最近 10 条消息
        opinions = []
        
        for role, agent in self.agents.items():
            opinion = await agent.participate_discussion(topic, discussion_context)
            self.memory.add_message(opinion)
            opinions.append(opinion)
            logger.info(f"[{role.value}] 发表了意见")
        
        # 仲裁
        decision = await self._arbitrate(topic, opinions)
        self.memory.add_message(decision)
        
        logger.info(f"[Coordinator] 做出仲裁: {decision.content.get('decision', '')[:50]}...")
    
    async def _phase_revising(self, context: Dict[str, Any]) -> None:
        """修改阶段"""
        self.state.transition_to(DialoguePhase.REVISING, AgentRole.WRITER)
        logger.info("\n🔄 阶段: 修改")
        
        task = create_task_message(
            receiver=AgentRole.WRITER,
            instruction="请根据审核意见和讨论结论修改章节内容。",
            context=context
        )
        self.memory.add_message(task)
        
        response = await self.writer.respond(task)
        self.memory.add_message(response)
        
        # 更新草稿
        self.state.current_draft = response.content
        
        # 让 Reviewer 快速反馈
        reviewer_reaction = await self.reviewer.react_to(response)
        if reviewer_reaction:
            self.memory.add_message(reviewer_reaction)
            logger.info("[Reviewer] 对修改做出了快速反馈")
    
    async def _phase_end(self) -> Dict[str, Any]:
        """结束阶段"""
        if not self.state.is_approved():
            self.state.transition_to(DialoguePhase.END)
        
        logger.info("\n" + "=" * 50)
        logger.info("🎬 [Coordinator] 对话结束")
        logger.info(f"状态: {self.state.get_status_summary()}")
        logger.info("=" * 50)
        
        # 获取最终内容
        final_draft = self.memory.get_artifact("current_draft")
        if not final_draft:
            final_draft = self.state.current_draft
        
        # 构建结果
        result = {
            "success": self.state.is_approved(),
            "content": final_draft.get("content") if isinstance(final_draft, dict) else final_draft,
            "title": final_draft.get("title", "") if isinstance(final_draft, dict) else "",
            "final_score": self.state.best_score,
            "iterations": self.state.iteration,
            "total_duration_seconds": self.state.get_total_duration(),
            "dialogue_summary": self.memory.to_summary(),
            "decisions": self.memory.decisions,
            "dialogue_export": self.memory.export_dialogue(),
            # 分卷决策信息
            "volume_decision": {
                "should_create_volume": self.state.should_create_volume,
                "volume_title": self.state.volume_title,
                "reason": self.state.volume_decision_reason,
            } if self.config.enable_volume_decision else None,
        }
        
        return result
    
    async def _handle_pending_questions(self) -> None:
        """处理待回答的问题"""
        for role, agent in self.agents.items():
            pending = self.memory.get_pending_questions_for(role)
            
            for question in pending[:self.config.max_questions_per_round]:
                logger.info(f"[{role.value}] 回答问题")
                answer = await agent.answer_question(question)
                self.memory.add_message(answer)
    
    async def _route_questions_from(self, message: Message) -> None:
        """路由消息中的问题到对应的 Agent"""
        for mentioned in message.mentions:
            if mentioned in self.agents and mentioned != message.sender:
                # 创建问题消息
                questions = self._extract_questions_from_content(message.content)
                for q in questions:
                    if q.get("to") == mentioned or not q.get("to"):
                        question_msg = Message(
                            sender=message.sender,
                            receiver=mentioned,
                            type=MessageType.QUESTION,
                            content={"question": q.get("question", ""), "context": str(message.content)},
                            mentions=[mentioned]
                        )
                        self.memory.add_message(question_msg)
                        
                        # 立即回答
                        answer = await self.agents[mentioned].answer_question(question_msg)
                        self.memory.add_message(answer)
    
    def _needs_discussion(self) -> bool:
        """判断是否需要三方讨论"""
        if not self.state.current_review:
            return False
        
        review = self.state.current_review
        
        # 情况 1：Reviewer 明确要求 Planner 参与
        if review.get("needs_planner_input"):
            return True
        
        # 情况 2：评分低于讨论门槛
        if review.get("score", 100) < self.config.discussion_threshold:
            return True
        
        # 情况 3：存在严重问题
        issues = review.get("issues", [])
        critical_count = sum(1 for i in issues if i.get("severity") == "critical")
        if critical_count >= 2:
            return True
        
        return False
    
    def _should_check_volume_split(self, context: Dict[str, Any]) -> bool:
        """判断是否需要检查分卷"""
        # 获取当前卷的章节数
        current_volume_chapters = context.get("current_volume_chapters", 0)
        chapter_number = context.get("chapter_number", 1)
        
        # 更新状态
        self.state.current_volume_chapters = current_volume_chapters
        
        # 达到最小章节数才考虑分卷
        if current_volume_chapters < self.config.min_chapters_per_volume:
            return False
        
        # 达到最大章节数必须分卷
        if current_volume_chapters >= self.config.max_chapters_per_volume:
            return True
        
        # 检查审核结果中是否有分卷建议
        review = self.state.current_review or {}
        if review.get("suggest_volume_split"):
            return True
        
        # 检查是否有剧情高潮标记
        draft = self.state.current_draft or {}
        if isinstance(draft, dict):
            key_points = draft.get("key_points", [])
            for point in key_points:
                if isinstance(point, str) and any(kw in point for kw in ["高潮", "转折", "结局", "大战", "决战"]):
                    return True
        
        return False
    
    async def _phase_volume_decision(self, context: Dict[str, Any]) -> None:
        """分卷决策阶段：三方讨论是否分卷以及卷名"""
        self.state.transition_to(DialoguePhase.VOLUME_DECISION)
        logger.info("\n📚 阶段: 分卷决策")
        
        current_chapters = self.state.current_volume_chapters
        chapter_number = context.get("chapter_number", 1)
        
        # 构建分卷讨论主题
        topic = f"当前卷已有 {current_chapters} 章，本章是第 {chapter_number} 章。是否应该在此处开启新卷？如果是，卷名应该叫什么？"
        
        logger.info(f"分卷讨论主题: {topic}")
        
        # 广播讨论请求
        broadcast = Message(
            sender=AgentRole.COORDINATOR,
            type=MessageType.CALL_DISCUSSION,
            content={
                "topic": topic,
                "type": "volume_decision",
                "current_volume_chapters": current_chapters,
                "chapter_number": chapter_number,
                "instruction": "请就是否分卷以及卷名发表意见。输出 JSON：{\"should_split\": true/false, \"volume_title\": \"建议的卷名\", \"reason\": \"理由\"}"
            }
        )
        self.memory.add_message(broadcast)
        
        # 收集各方意见
        discussion_context = self.memory.get_all_messages()[-10:]
        opinions = []
        
        for role, agent in self.agents.items():
            opinion = await agent.participate_discussion(topic, discussion_context)
            self.memory.add_message(opinion)
            opinions.append(opinion)
            logger.info(f"[{role.value}] 发表了分卷意见")
        
        # 仲裁分卷决策
        decision = await self._arbitrate_volume_decision(opinions, current_chapters)
        self.memory.add_message(decision)
        
        # 更新状态
        decision_content = decision.content
        self.state.should_create_volume = decision_content.get("should_split", False)
        self.state.volume_title = decision_content.get("volume_title")
        self.state.volume_decision_reason = decision_content.get("reason")
        
        if self.state.should_create_volume:
            logger.info(f"📖 分卷决策: 是，新卷名《{self.state.volume_title}》")
            logger.info(f"   理由: {self.state.volume_decision_reason}")
        else:
            logger.info("📖 分卷决策: 否，继续当前卷")
    
    async def _arbitrate_volume_decision(self, opinions: List[Message], current_chapters: int) -> Message:
        """仲裁分卷决策"""
        opinions_text = "\n\n".join([
            f"**{o.sender.value.upper()}**:\n{json.dumps(o.content, ensure_ascii=False, indent=2)}"
            for o in opinions
        ])
        
        prompt = f"""作为协调者，请根据各方意见做出分卷决策。

## 当前情况
- 当前卷已有章节数: {current_chapters}
- 最少章节数要求: {self.config.min_chapters_per_volume}
- 最多章节数限制: {self.config.max_chapters_per_volume}

## 各方意见
{opinions_text}

## 分卷原则
1. 每卷应该有完整的故事弧（开始→发展→高潮→收尾）
2. 分卷点最好在剧情高潮或重大转折之后
3. 卷名应该有文学性，5-10 字，能概括本卷主题
4. 如果达到最大章节数限制，必须分卷

## 请输出 JSON
{{
    "should_split": true或false,
    "volume_title": "新卷名（如果分卷）",
    "reason": "决策理由",
    "confidence": "high|medium|low"
}}
"""
        
        response = await self.llm_service.invoke(
            provider=getattr(self.llm_service, "default_provider", "openai"),
            model=getattr(self.llm_service, "default_model", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=512,
        )
        
        decision_content = self._parse_json(response)
        
        # 强制分卷检查
        if current_chapters >= self.config.max_chapters_per_volume and not decision_content.get("should_split"):
            decision_content["should_split"] = True
            decision_content["reason"] = f"达到每卷最大章节数限制（{self.config.max_chapters_per_volume}章），强制分卷"
            if not decision_content.get("volume_title"):
                decision_content["volume_title"] = "新的篇章"
        
        # 记录决定
        self.memory.record_decision(
            decision=f"分卷决策: {'是' if decision_content.get('should_split') else '否'}",
            made_by=AgentRole.COORDINATOR,
            reason=decision_content.get("reason", ""),
        )
        
        return Message(
            sender=AgentRole.COORDINATOR,
            type=MessageType.ARBITRATE,
            content=decision_content
        )
    
    def _identify_discussion_topic(self) -> str:
        """识别讨论主题"""
        review = self.state.current_review or {}
        
        # 优先使用 Reviewer 的问题
        questions = review.get("questions_for_planner", [])
        if questions:
            return questions[0]
        
        # 使用最严重的问题
        issues = review.get("issues", [])
        critical = [i for i in issues if i.get("severity") == "critical"]
        if critical:
            return f"严重问题: {critical[0].get('description', '')}"
        
        if issues:
            return f"需要讨论: {issues[0].get('description', '')}"
        
        return "整体质量如何提升"
    
    async def _arbitrate(self, topic: str, opinions: List[Message]) -> Message:
        """仲裁各方意见"""
        opinions_text = "\n\n".join([
            f"**{o.sender.value.upper()}**:\n{json.dumps(o.content, ensure_ascii=False, indent=2)}"
            for o in opinions
        ])
        
        prompt = f"""作为协调者，请根据以下各方意见做出最终决定。

## 讨论主题
{topic}

## 各方意见
{opinions_text}

## 你的任务
请仲裁并做出决定。要求：
1. 权衡各方观点
2. 给出明确的决定
3. 说明理由
4. 给出下一步行动指令

输出 JSON：
{{
    "decision": "最终决定",
    "reason": "决定理由",
    "actions": {{
        "planner": "给 Planner 的指令（如有）",
        "writer": "给 Writer 的指令",
        "reviewer": "给 Reviewer 的注意事项（如有）"
    }},
    "priority": "high|medium|low"
}}
"""
        
        response = await self.llm_service.invoke(
            provider=getattr(self.llm_service, "default_provider", None) or "anthropic",
            model=getattr(self.llm_service, "default_model", None) or "claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024,
            user_id=self.memory.context.get("user_id") if isinstance(self.memory.context, dict) else None,
        )
        
        decision_content = self._parse_json(response)
        
        # 记录决定
        self.memory.record_decision(
            decision=decision_content.get("decision", ""),
            made_by=AgentRole.COORDINATOR,
            reason=decision_content.get("reason", ""),
        )
        
        return Message(
            sender=AgentRole.COORDINATOR,
            type=MessageType.ARBITRATE,
            content=decision_content
        )
    
    def _extract_questions_from_content(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从内容中提取问题"""
        questions = []
        
        if "questions" in content:
            for q in content["questions"]:
                if isinstance(q, dict):
                    questions.append(q)
                elif isinstance(q, str):
                    questions.append({"question": q})
        
        return questions
    
    def _parse_json(self, text: str) -> Dict[str, Any]:
        """解析 JSON"""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        
        try:
            return json.loads(text)
        except:
            return {"raw": text}
    
    def _create_error_result(self, error: str) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            "success": False,
            "error": error,
            "content": None,
            "iterations": self.state.iteration,
            "total_duration_seconds": self.state.get_total_duration(),
            "dialogue_export": self.memory.export_dialogue(),
        }
