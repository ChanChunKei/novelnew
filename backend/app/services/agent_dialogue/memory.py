"""
共享记忆模块

所有 Agent 共享的对话记忆，实现真正的信息共享。
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import logging

from .message import Message, AgentRole, MessageType

logger = logging.getLogger(__name__)


class SharedMemory:
    """
    共享对话记忆
    
    所有 Agent 都可以读取完整的对话历史，实现真正的信息共享。
    只有 Coordinator 可以管理（添加消息、记录决定）。
    
    Features:
        - 完整对话历史
        - 项目上下文
        - 产出物（大纲、章节等）
        - 重要决定记录
        - 问答追踪
    """
    
    def __init__(self):
        self.messages: List[Message] = []
        self.context: Dict[str, Any] = {}       # 项目上下文
        self.artifacts: Dict[str, Any] = {}     # 产出物
        self.decisions: List[Dict[str, Any]] = []  # 重要决定
        self._answered_questions: set = set()   # 已回答的问题 ID
    
    def add_message(self, message: Message) -> None:
        """添加消息到对话历史"""
        self.messages.append(message)
        logger.debug(f"[Memory] 添加消息: {message.sender.value} -> {message.type.value}")
        
        # 如果是回答，标记问题已回答
        if message.reply_to:
            self._answered_questions.add(message.reply_to)
    
    def get_all_messages(self) -> List[Message]:
        """获取所有消息"""
        return self.messages.copy()
    
    def get_messages_for_agent(self, agent: AgentRole, limit: int = 50) -> List[Message]:
        """
        获取对某个 Agent 相关的消息
        
        包括：
        - 所有广播消息
        - 发给该 Agent 的消息
        - @提及该 Agent 的消息
        - 该 Agent 发出的消息
        """
        relevant = []
        for msg in self.messages[-limit:]:
            if (msg.is_broadcast() or 
                msg.receiver == agent or 
                agent in msg.mentions or
                msg.sender == agent):
                relevant.append(msg)
        return relevant
    
    def get_messages_since(self, message_id: str) -> List[Message]:
        """获取某条消息之后的所有消息"""
        found = False
        result = []
        for msg in self.messages:
            if found:
                result.append(msg)
            if msg.id == message_id:
                found = True
        return result
    
    def get_pending_questions_for(self, agent: AgentRole) -> List[Message]:
        """获取指向某个 Agent 的未回答问题"""
        pending = []
        for msg in self.messages:
            if (msg.type == MessageType.QUESTION and
                agent in msg.mentions and
                msg.id not in self._answered_questions):
                pending.append(msg)
        return pending
    
    def get_latest_draft(self) -> Optional[Dict[str, Any]]:
        """获取最新的草稿内容"""
        for msg in reversed(self.messages):
            if msg.type in (MessageType.DRAFT, MessageType.REVISION):
                return msg.content
        return None
    
    def get_latest_review(self) -> Optional[Dict[str, Any]]:
        """获取最新的审核结果"""
        for msg in reversed(self.messages):
            if msg.type == MessageType.REVIEW:
                return msg.content
        return None
    
    def get_latest_plan(self) -> Optional[Dict[str, Any]]:
        """获取最新的规划"""
        for msg in reversed(self.messages):
            if msg.sender == AgentRole.PLANNER and msg.type == MessageType.RESPONSE:
                return msg.content
        return None
    
    def set_context(self, key: str, value: Any) -> None:
        """设置上下文信息"""
        self.context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文信息"""
        return self.context.get(key, default)
    
    def set_artifact(self, key: str, value: Any) -> None:
        """设置产出物"""
        self.artifacts[key] = value
        logger.info(f"[Memory] 保存产出物: {key}")
    
    def get_artifact(self, key: str) -> Optional[Any]:
        """获取产出物"""
        return self.artifacts.get(key)
    
    def record_decision(
        self, 
        decision: str, 
        made_by: AgentRole, 
        reason: str,
        related_message_ids: Optional[List[str]] = None
    ) -> None:
        """记录重要决定"""
        self.decisions.append({
            "decision": decision,
            "made_by": made_by.value,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "related_messages": related_message_ids or []
        })
        logger.info(f"[Memory] 记录决定: {decision[:50]}...")
    
    def to_context_string(self, for_agent: AgentRole, max_messages: int = 30) -> str:
        """
        将对话历史转换为可读的上下文字符串
        
        Args:
            for_agent: 为哪个 Agent 生成上下文
            max_messages: 最多显示多少条消息
        """
        lines = ["=== 对话历史 ===\n"]
        
        messages = self.get_messages_for_agent(for_agent, limit=max_messages)
        
        for msg in messages:
            lines.append(msg.format_for_display())
            lines.append("")
        
        # 添加重要决定摘要
        if self.decisions:
            lines.append("\n=== 已做出的决定 ===")
            for d in self.decisions[-5:]:  # 最近 5 个决定
                lines.append(f"- {d['decision']} (by {d['made_by']})")
        
        return "\n".join(lines)
    
    def to_summary(self) -> Dict[str, Any]:
        """生成对话摘要"""
        return {
            "total_messages": len(self.messages),
            "by_sender": self._count_by_sender(),
            "by_type": self._count_by_type(),
            "decisions_count": len(self.decisions),
            "artifacts": list(self.artifacts.keys()),
            "pending_questions": self._count_pending_questions(),
        }
    
    def _count_by_sender(self) -> Dict[str, int]:
        """按发送者统计消息数"""
        counts = {}
        for msg in self.messages:
            sender = msg.sender.value
            counts[sender] = counts.get(sender, 0) + 1
        return counts
    
    def _count_by_type(self) -> Dict[str, int]:
        """按类型统计消息数"""
        counts = {}
        for msg in self.messages:
            msg_type = msg.type.value
            counts[msg_type] = counts.get(msg_type, 0) + 1
        return counts
    
    def _count_pending_questions(self) -> int:
        """统计未回答问题数"""
        count = 0
        for msg in self.messages:
            if msg.type == MessageType.QUESTION and msg.id not in self._answered_questions:
                count += 1
        return count
    
    def export_dialogue(self) -> Dict[str, Any]:
        """导出完整对话记录"""
        return {
            "messages": [m.to_dict() for m in self.messages],
            "context": self.context,
            "decisions": self.decisions,
            "artifacts": {
                k: v if isinstance(v, (str, int, float, bool, list, dict)) else str(v)
                for k, v in self.artifacts.items()
            },
            "summary": self.to_summary(),
        }
    
    def clear(self) -> None:
        """清空记忆（用于新对话）"""
        self.messages.clear()
        self.context.clear()
        self.artifacts.clear()
        self.decisions.clear()
        self._answered_questions.clear()

