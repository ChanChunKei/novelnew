"""
消息定义模块

定义 Agent 之间通信的消息格式。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
import uuid


class AgentRole(Enum):
    """Agent 角色"""
    COORDINATOR = "coordinator"  # 协调者
    PLANNER = "planner"          # 规划者
    WRITER = "writer"            # 创作者
    REVIEWER = "reviewer"        # 审核者


class MessageType(Enum):
    """消息类型"""
    # Coordinator 消息
    ASSIGN_TASK = "assign_task"                    # 分配任务
    REQUEST_CLARIFICATION = "request_clarification"  # 请求澄清
    CALL_DISCUSSION = "call_discussion"            # 召集讨论
    SUMMARIZE = "summarize"                        # 总结进度
    ARBITRATE = "arbitrate"                        # 仲裁决定
    END_DIALOGUE = "end_dialogue"                  # 结束对话
    
    # Agent 消息
    RESPONSE = "response"           # 正常回应
    QUESTION = "question"           # 提问
    ANSWER = "answer"               # 回答问题
    AGREE = "agree"                 # 同意
    DISAGREE = "disagree"           # 不同意
    PROPOSAL = "proposal"           # 提议
    REVISION = "revision"           # 修改版本
    DRAFT = "draft"                 # 草稿内容
    REVIEW = "review"               # 审核结果
    TOOL_CALL = "tool_call"         # 工具调用
    TOOL_RESULT = "tool_result"     # 工具结果


@dataclass
class Message:
    """
    对话消息
    
    Attributes:
        id: 消息唯一标识
        sender: 发送者角色
        receiver: 接收者角色，None 表示广播给所有人
        type: 消息类型
        content: 消息内容（结构化 Dict）
        timestamp: 时间戳
        reply_to: 回复的消息 ID
        mentions: @提及的 Agent 列表
        metadata: 额外元数据
    """
    sender: AgentRole
    type: MessageType
    content: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    receiver: Optional[AgentRole] = None
    timestamp: datetime = field(default_factory=datetime.now)
    reply_to: Optional[str] = None
    mentions: List[AgentRole] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "sender": self.sender.value,
            "receiver": self.receiver.value if self.receiver else None,
            "type": self.type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "reply_to": self.reply_to,
            "mentions": [m.value for m in self.mentions],
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典创建"""
        return cls(
            id=data["id"],
            sender=AgentRole(data["sender"]),
            receiver=AgentRole(data["receiver"]) if data.get("receiver") else None,
            type=MessageType(data["type"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            reply_to=data.get("reply_to"),
            mentions=[AgentRole(m) for m in data.get("mentions", [])],
            metadata=data.get("metadata", {}),
        )
    
    def is_broadcast(self) -> bool:
        """是否是广播消息"""
        return self.receiver is None
    
    def is_directed_to(self, role: AgentRole) -> bool:
        """是否指向特定角色"""
        return self.receiver == role or role in self.mentions
    
    def format_for_display(self) -> str:
        """格式化为可读字符串"""
        sender = self.sender.value.upper()
        receiver = f" → {self.receiver.value}" if self.receiver else " → ALL"
        mentions = f" @{','.join(m.value for m in self.mentions)}" if self.mentions else ""
        
        lines = [f"[{sender}{receiver}{mentions}] ({self.type.value})"]
        
        if isinstance(self.content, dict):
            for k, v in self.content.items():
                if isinstance(v, str):
                    v_display = v[:150] + "..." if len(v) > 150 else v
                else:
                    v_display = str(v)[:150]
                lines.append(f"  {k}: {v_display}")
        else:
            lines.append(f"  {self.content}")
        
        return "\n".join(lines)


def create_task_message(
    receiver: AgentRole,
    instruction: str,
    context: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Message:
    """创建任务消息的快捷方法"""
    return Message(
        sender=AgentRole.COORDINATOR,
        receiver=receiver,
        type=MessageType.ASSIGN_TASK,
        content={
            "instruction": instruction,
            "context": context or {},
            **kwargs
        }
    )


def create_question_message(
    sender: AgentRole,
    question: str,
    to: AgentRole,
    context: Optional[str] = None
) -> Message:
    """创建提问消息的快捷方法"""
    return Message(
        sender=sender,
        receiver=to,
        type=MessageType.QUESTION,
        content={
            "question": question,
            "context": context
        },
        mentions=[to]
    )

