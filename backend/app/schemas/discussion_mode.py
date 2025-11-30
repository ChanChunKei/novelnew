"""
讨论模式相关的 Pydantic Schema
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class DiscussionModeConfig(BaseModel):
    """讨论模式配置"""
    max_iterations: int = Field(default=5, ge=1, le=10, description="最大迭代次数")
    approval_threshold: int = Field(default=80, ge=0, le=100, description="通过门槛分数")
    discussion_threshold: int = Field(default=60, ge=0, le=100, description="触发讨论的分数门槛")
    timeout_seconds: int = Field(default=300, ge=60, le=600, description="超时时间（秒）")
    enable_tools: bool = Field(default=True, description="是否启用工具调用")
    verbose: bool = Field(default=False, description="是否详细日志")
    # 分卷配置
    enable_volume_decision: bool = Field(default=True, description="是否启用分卷决策")
    min_chapters_per_volume: int = Field(default=15, ge=5, le=50, description="每卷最少章节数")
    max_chapters_per_volume: int = Field(default=30, ge=10, le=100, description="每卷最多章节数")


class GenerateChapterRequest(BaseModel):
    """使用讨论模式生成章节的请求"""
    project_id: int = Field(..., description="项目 ID")
    chapter_number: int = Field(..., ge=1, description="章节号")
    
    # 可选上下文
    genre: Optional[str] = Field(None, description="小说类型")
    word_count: Optional[int] = Field(default=3000, ge=1000, le=10000, description="目标字数")
    previous_summary: Optional[str] = Field(None, description="前情提要")
    character_states: Optional[str] = Field(None, description="角色状态")
    blueprint_summary: Optional[str] = Field(None, description="蓝图摘要")
    volumes_snapshot: Optional[List[Dict[str, Any]]] = Field(None, description="分卷快照（可选）")
    
    # 分卷相关上下文
    current_volume_chapters: int = Field(default=0, ge=0, description="当前卷已有章节数（用于分卷决策）")
    current_volume_number: int = Field(default=1, ge=1, description="当前卷号")
    
    # 上传控制
    auto_upload: bool = Field(default=False, description="是否自动上传到番茄")
    fanqie_account: Optional[str] = Field(default=None, description="番茄账号标识（auto_upload=True 时必填）")
    
    # 配置
    config: Optional[DiscussionModeConfig] = Field(None, description="讨论模式配置")


class GenerateOutlineRequest(BaseModel):
    """使用讨论模式生成大纲的请求"""
    project_id: int = Field(..., description="项目 ID")
    start_chapter: int = Field(..., ge=1, description="起始章节号")
    end_chapter: int = Field(..., ge=1, description="结束章节号")
    
    # 可选上下文
    genre: Optional[str] = Field(None, description="小说类型")
    blueprint_summary: Optional[str] = Field(None, description="蓝图摘要")
    current_progress: Optional[str] = Field(None, description="当前进度描述")
    
    # 配置
    config: Optional[DiscussionModeConfig] = Field(None, description="讨论模式配置")


class DialogueMessage(BaseModel):
    """对话消息"""
    id: str
    sender: str
    receiver: Optional[str]
    type: str
    content: Dict[str, Any]
    timestamp: str
    mentions: List[str] = []


class DialogueSummary(BaseModel):
    """对话摘要"""
    total_messages: int
    by_sender: Dict[str, int]
    by_type: Dict[str, int]
    decisions_count: int
    artifacts: List[str]
    pending_questions: int


class VolumeDecision(BaseModel):
    """分卷决策结果"""
    should_create_volume: bool = Field(default=False, description="是否应该创建新卷")
    volume_title: Optional[str] = Field(None, description="新卷标题")
    reason: Optional[str] = Field(None, description="决策理由")


class GenerateChapterResponse(BaseModel):
    """生成章节的响应"""
    success: bool = Field(..., description="是否成功")
    content: Optional[str] = Field(None, description="章节内容")
    title: Optional[str] = Field(None, description="章节标题")
    
    # 质量指标
    final_score: int = Field(default=0, description="最终评分")
    iterations: int = Field(default=0, description="迭代次数")
    total_duration_seconds: float = Field(default=0, description="总耗时（秒）")
    
    # 分卷决策
    volume_decision: Optional[VolumeDecision] = Field(None, description="分卷决策结果")
    
    # 对话记录
    dialogue_summary: Optional[DialogueSummary] = Field(None, description="对话摘要")
    decisions: List[Dict[str, Any]] = Field(default_factory=list, description="做出的决定")
    
    # 详细记录（可选）
    dialogue_export: Optional[Dict[str, Any]] = Field(None, description="完整对话记录")
    
    # 错误信息
    error: Optional[str] = Field(None, description="错误信息")


class GenerateOutlineResponse(BaseModel):
    """生成大纲的响应"""
    success: bool
    outline: Optional[List[Dict[str, Any]]] = Field(None, description="大纲列表")
    
    # 质量指标
    final_score: int = Field(default=0)
    iterations: int = Field(default=0)
    total_duration_seconds: float = Field(default=0)
    
    # 对话记录
    dialogue_summary: Optional[DialogueSummary] = None
    decisions: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 错误信息
    error: Optional[str] = None


class DiscussionModeStatus(BaseModel):
    """讨论模式状态"""
    phase: str
    current_speaker: Optional[str]
    iteration: int
    max_iterations: int
    best_score: int
    total_duration_seconds: float
