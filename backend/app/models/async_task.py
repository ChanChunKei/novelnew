"""
异步任务模型

用于增强模式的异步处理：
1. 章节生成后立即返回
2. 增强分析在后台执行
3. 通过轮询或WebSocket通知前端
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

# ✅ 修复：从正确路径导入Base
from ..db.base import Base


class PendingAnalysis(Base):
    """
    待处理的增强分析任务
    
    工作流程：
    1. 章节生成完成后，创建pending状态的记录
    2. 后台处理器扫描pending记录
    3. 执行增强分析，更新状态为processing
    4. 完成后更新状态为completed
    5. 失败时更新状态为failed，记录错误信息
    """
    __tablename__ = "pending_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联信息
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("novel_projects.id"), nullable=False, index=True)  # ✅ 修复：改为String(36)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("auto_generator_tasks.id"), nullable=True, index=True)
    
    # 任务状态
    status = Column(
        String(32), 
        nullable=False, 
        default="pending",
        index=True,
        comment="pending, processing, completed, failed"
    )
    
    # 优先级（1-10，数字越大优先级越高）
    priority = Column(Integer, default=5, nullable=False, index=True)
    
    # 重试信息
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    
    # 配置信息（从task继承）
    generation_config = Column(JSON, nullable=True, comment="生成配置（功能开关、阈值等）")
    
    # 结果信息
    result = Column(JSON, nullable=True, comment="增强分析结果")
    error_message = Column(Text, nullable=True, comment="错误信息")
    error_type = Column(String(64), nullable=True, comment="错误类型")
    
    # 时间信息
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True, comment="开始处理时间")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 性能指标
    duration_seconds = Column(Integer, nullable=True, comment="处理耗时（秒）")
    token_usage = Column(JSON, nullable=True, comment="Token消耗统计")
    
    # 关系
    chapter = relationship("Chapter", back_populates="pending_analyses")
    project = relationship("NovelProject")
    user = relationship("User")
    task = relationship("AutoGeneratorTask")
    
    def __repr__(self):
        return f"<PendingAnalysis(id={self.id}, chapter_id={self.chapter_id}, status={self.status})>"
    
    @property
    def is_pending(self) -> bool:
        """是否待处理"""
        return self.status == "pending"
    
    @property
    def is_processing(self) -> bool:
        """是否处理中"""
        return self.status == "processing"
    
    @property
    def is_completed(self) -> bool:
        """是否已完成"""
        return self.status == "completed"
    
    @property
    def is_failed(self) -> bool:
        """是否失败"""
        return self.status == "failed"
    
    @property
    def can_retry(self) -> bool:
        """是否可以重试"""
        return self.is_failed and self.retry_count < self.max_retries
    
    @property
    def elapsed_seconds(self) -> int:
        """已耗时（秒）"""
        if not self.started_at:
            return 0
        
        end_time = self.completed_at or datetime.now(timezone.utc)
        return int((end_time - self.started_at).total_seconds())


class AnalysisNotification(Base):
    """
    分析完成通知
    
    用于前端轮询或WebSocket推送
    """
    __tablename__ = "analysis_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联信息
    pending_analysis_id = Column(Integer, ForeignKey("pending_analysis.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False, index=True)
    
    # 通知类型
    notification_type = Column(
        String(32),
        nullable=False,
        comment="started, progress, completed, failed"
    )
    
    # 通知内容
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    data = Column(JSON, nullable=True, comment="附加数据")
    
    # 状态
    is_read = Column(Integer, default=0, nullable=False, comment="是否已读（0未读，1已读）")
    
    # 时间
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # 关系
    pending_analysis = relationship("PendingAnalysis")
    user = relationship("User")
    chapter = relationship("Chapter")
    
    def __repr__(self):
        return f"<AnalysisNotification(id={self.id}, type={self.notification_type}, is_read={self.is_read})>"
    
    def mark_as_read(self):
        """标记为已读"""
        self.is_read = 1
        self.read_at = datetime.now(timezone.utc)

