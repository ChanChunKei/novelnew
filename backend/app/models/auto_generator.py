"""自动生成器模型"""
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class AutoGeneratorTask(Base):
    """自动生成任务表"""
    
    __tablename__ = "auto_generator_tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    # 任务状态: pending, running, paused, stopped, completed, error
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    
    # 生成配置
    target_chapters: Mapped[Optional[int]] = mapped_column(Integer)  # 目标章节数，None表示无限
    chapters_per_batch: Mapped[int] = mapped_column(Integer, default=1)  # 每批生成章节数
    interval_seconds: Mapped[int] = mapped_column(Integer, default=60)  # 生成间隔（秒）
    auto_select_version: Mapped[bool] = mapped_column(default=True)  # 是否自动选择最佳版本
    auto_upload: Mapped[bool] = mapped_column(default=False)  # 是否自动上传到番茄小说
    fanqie_account: Mapped[Optional[str]] = mapped_column(String(64))  # 番茄小说账号名称

    # 生成参数
    generation_config: Mapped[Optional[dict]] = mapped_column(JSON)  # 生成参数配置
    
    # 统计信息
    chapters_generated: Mapped[int] = mapped_column(Integer, default=0)  # 已生成章节数
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0)  # 总token使用量
    error_count: Mapped[int] = mapped_column(Integer, default=0)  # 错误次数
    last_error: Mapped[Optional[str]] = mapped_column(Text)  # 最后一次错误信息
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_generation_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # ✅ 新增：定时启动功能
    scheduled_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)  # 定时启动时间
    delay_seconds: Mapped[int] = mapped_column(Integer, default=0)  # 启动延迟（秒）
    batch_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)  # 批次ID（用于标识批量创建的任务）

    # 关系
    project: Mapped["NovelProject"] = relationship("NovelProject")
    user: Mapped["User"] = relationship("User")


class AutoGeneratorLog(Base):
    """自动生成日志表"""
    
    __tablename__ = "auto_generator_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("auto_generator_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    chapter_number: Mapped[Optional[int]] = mapped_column(Integer)
    log_type: Mapped[str] = mapped_column(String(32))  # info, warning, error, success
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    task: Mapped[AutoGeneratorTask] = relationship("AutoGeneratorTask")
