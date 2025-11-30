"""
对话状态模块

管理讨论模式的状态机。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime

from .message import AgentRole


class DialoguePhase(Enum):
    """对话阶段"""
    START = "start"                 # 开始
    PLANNING = "planning"           # 规划阶段
    DRAFTING = "drafting"           # 起草阶段
    REVIEWING = "reviewing"         # 审核阶段
    DISCUSSING = "discussing"       # 三方讨论
    CLARIFYING = "clarifying"       # 澄清阶段
    REVISING = "revising"           # 修改阶段
    VOLUME_DECISION = "volume_decision"  # 分卷决策阶段
    APPROVED = "approved"           # 已通过
    FAILED = "failed"               # 失败
    END = "end"                     # 结束


@dataclass
class DialogueState:
    """
    对话状态
    
    维护当前对话的完整状态信息。
    """
    
    # 基本状态
    phase: DialoguePhase = DialoguePhase.START
    current_speaker: Optional[AgentRole] = None
    
    # 迭代控制
    iteration: int = 0
    max_iterations: int = 5
    
    # 内容状态
    current_plan: Optional[Dict[str, Any]] = None
    current_draft: Optional[Dict[str, Any]] = None
    current_review: Optional[Dict[str, Any]] = None
    
    # 讨论状态
    discussion_topic: Optional[str] = None
    discussion_participants: List[AgentRole] = field(default_factory=list)
    
    # 分卷状态
    should_create_volume: bool = False
    volume_title: Optional[str] = None
    volume_decision_reason: Optional[str] = None
    current_volume_chapters: int = 0  # 当前卷已有章节数
    
    # 质量指标
    best_score: int = 0
    score_history: List[int] = field(default_factory=list)
    
    # 时间追踪
    started_at: Optional[datetime] = None
    phase_started_at: Optional[datetime] = None
    
    # 错误追踪
    errors: List[str] = field(default_factory=list)
    
    def start(self) -> None:
        """开始对话"""
        self.started_at = datetime.now()
        self.phase = DialoguePhase.START
    
    def transition_to(self, phase: DialoguePhase, speaker: Optional[AgentRole] = None) -> None:
        """状态转换"""
        self.phase = phase
        self.current_speaker = speaker
        self.phase_started_at = datetime.now()
    
    def increment_iteration(self) -> bool:
        """
        增加迭代次数
        
        Returns:
            是否还可以继续迭代
        """
        self.iteration += 1
        return self.iteration < self.max_iterations
    
    def record_score(self, score: int) -> None:
        """记录评分"""
        self.score_history.append(score)
        if score > self.best_score:
            self.best_score = score
    
    def record_error(self, error: str) -> None:
        """记录错误"""
        self.errors.append(f"[{datetime.now().isoformat()}] {error}")
    
    def is_approved(self) -> bool:
        """是否已通过"""
        return self.phase == DialoguePhase.APPROVED
    
    def is_ended(self) -> bool:
        """是否已结束"""
        return self.phase in (DialoguePhase.END, DialoguePhase.FAILED, DialoguePhase.APPROVED)
    
    def can_continue(self) -> bool:
        """是否可以继续"""
        return not self.is_ended() and self.iteration < self.max_iterations
    
    def get_phase_duration(self) -> float:
        """获取当前阶段持续时间（秒）"""
        if self.phase_started_at:
            return (datetime.now() - self.phase_started_at).total_seconds()
        return 0
    
    def get_total_duration(self) -> float:
        """获取总持续时间（秒）"""
        if self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "phase": self.phase.value,
            "current_speaker": self.current_speaker.value if self.current_speaker else None,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "best_score": self.best_score,
            "score_history": self.score_history,
            "total_duration_seconds": self.get_total_duration(),
            "errors_count": len(self.errors),
        }
    
    def get_status_summary(self) -> str:
        """获取状态摘要"""
        return (
            f"阶段: {self.phase.value} | "
            f"迭代: {self.iteration}/{self.max_iterations} | "
            f"最高分: {self.best_score} | "
            f"耗时: {self.get_total_duration():.1f}s"
        )


class DialogueConfig:
    """对话配置"""
    
    def __init__(
        self,
        max_iterations: int = 5,
        approval_threshold: int = 80,
        discussion_threshold: int = 60,
        max_questions_per_round: int = 3,
        timeout_seconds: int = 300,
        enable_tools: bool = True,
        verbose: bool = False,
        # 分卷配置
        enable_volume_decision: bool = True,
        min_chapters_per_volume: int = 15,
        max_chapters_per_volume: int = 30,
    ):
        """
        Args:
            max_iterations: 最大迭代次数
            approval_threshold: 通过门槛分数
            discussion_threshold: 需要讨论的分数门槛（低于此分数需要三方讨论）
            max_questions_per_round: 每轮最多处理多少个问题
            timeout_seconds: 超时时间（秒）
            enable_tools: 是否启用工具调用
            verbose: 是否详细日志
            enable_volume_decision: 是否启用分卷决策
            min_chapters_per_volume: 每卷最少章节数
            max_chapters_per_volume: 每卷最多章节数（强制分卷）
        """
        self.max_iterations = max_iterations
        self.approval_threshold = approval_threshold
        self.discussion_threshold = discussion_threshold
        self.max_questions_per_round = max_questions_per_round
        self.timeout_seconds = timeout_seconds
        self.enable_tools = enable_tools
        self.verbose = verbose
        self.enable_volume_decision = enable_volume_decision
        self.min_chapters_per_volume = min_chapters_per_volume
        self.max_chapters_per_volume = max_chapters_per_volume
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "approval_threshold": self.approval_threshold,
            "discussion_threshold": self.discussion_threshold,
            "max_questions_per_round": self.max_questions_per_round,
            "timeout_seconds": self.timeout_seconds,
            "enable_tools": self.enable_tools,
            "verbose": self.verbose,
            "enable_volume_decision": self.enable_volume_decision,
            "min_chapters_per_volume": self.min_chapters_per_volume,
            "max_chapters_per_volume": self.max_chapters_per_volume,
        }

