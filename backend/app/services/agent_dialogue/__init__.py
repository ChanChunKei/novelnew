"""
讨论模式（Discussion Mode）

一个真正的多 Agent 对话系统，由 Coordinator 协调 Planner、Writer、Reviewer 进行协作对话。

与原 3-Agent 模式的区别：
- 原模式：流水线式，P→W→R→W，Agent 之间无交互
- 讨论模式：真正的对话，Agent 可以互相提问、回应、讨论

使用方式：
    from app.services.agent_dialogue import DiscussionMode
    
    mode = DiscussionMode(llm_service, rag_service)
    result = await mode.generate_chapter(project_id, chapter_number, context)
"""

from .coordinator import Coordinator
from .memory import SharedMemory
from .message import Message, AgentRole, MessageType
from .state import DialogueState, DialoguePhase
from .discussion_mode import DiscussionMode

__all__ = [
    "DiscussionMode",
    "Coordinator",
    "SharedMemory",
    "Message",
    "AgentRole",
    "MessageType",
    "DialogueState",
    "DialoguePhase",
]

