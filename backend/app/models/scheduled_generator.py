"""
定时自动生成器模型

支持功能：
- 定时触发自动生成器（使用太平洋时间）
- 书籍队列管理
- 并发生成控制
- 自动切换机制
- 番茄小说自动上传集成
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Integer, String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from ..db.base import Base


class ScheduledGeneratorStatus(str, enum.Enum):
    """定时生成器状态"""
    IDLE = "idle"          # 空闲（未启动）
    RUNNING = "running"    # 运行中
    PAUSED = "paused"      # 已暂停


class GenerationMode(str, enum.Enum):
    """生成模式"""
    BASIC = "basic"              # 基础模式
    ENHANCED = "enhanced"        # 增强模式


class QueueItemStatus(str, enum.Enum):
    """队列项状态"""
    PENDING = "pending"        # 待处理
    RUNNING = "running"        # 处理中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败
    SKIPPED = "skipped"        # 已跳过


class ScheduledGeneratorConfig(Base):
    """定时生成器配置表"""
    __tablename__ = "scheduled_generator_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # 基础配置
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="默认定时任务")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 定时配置（太平洋时间 PT）
    trigger_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=2)  # 0-23
    trigger_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0-59

    # 生成配置
    generation_mode: Mapped[str] = mapped_column(
        SQLEnum(GenerationMode),
        nullable=False,
        default=GenerationMode.BASIC.value
    )

    # 番茄上传配置
    auto_upload_fanqie: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    upload_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=20)

    # 并发和时长控制
    concurrent_books: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 同时生成几本书
    max_duration_per_book: Mapped[int] = mapped_column(Integer, nullable=False, default=120)  # 单本最大时长（分钟）

    # 运行状态
    status: Mapped[str] = mapped_column(
        SQLEnum(ScheduledGeneratorStatus),
        nullable=False,
        default=ScheduledGeneratorStatus.IDLE.value
    )

    # 统计信息
    total_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_books_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_books_success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_books_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关系
    queue_items: Mapped[list["ScheduledGeneratorQueue"]] = relationship(
        "ScheduledGeneratorQueue",
        back_populates="config",
        cascade="all, delete-orphan"
    )
    logs: Mapped[list["ScheduledGeneratorLog"]] = relationship(
        "ScheduledGeneratorLog",
        back_populates="config",
        cascade="all, delete-orphan"
    )


class ScheduledGeneratorQueue(Base):
    """定时生成器队列表"""
    __tablename__ = "scheduled_generator_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[int] = mapped_column(Integer, ForeignKey("scheduled_generator_configs.id"), nullable=False)
    novel_id: Mapped[str] = mapped_column(String(36), nullable=False)  # 小说项目ID

    # 队列配置
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 优先级（数字越大越优先）
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 队列位置

    # 状态
    status: Mapped[str] = mapped_column(
        SQLEnum(QueueItemStatus),
        nullable=False,
        default=QueueItemStatus.PENDING.value
    )

    # 关联任务
    auto_generator_task_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 关联的AutoGeneratorTask ID

    # 执行信息
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 耗时（秒）

    # 生成统计
    chapters_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chapters_target: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 上传信息
    uploaded_to_fanqie: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    upload_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON格式的上传结果

    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # 关系
    config: Mapped["ScheduledGeneratorConfig"] = relationship("ScheduledGeneratorConfig", back_populates="queue_items")


class ScheduledGeneratorLog(Base):
    """定时生成器执行日志表"""
    __tablename__ = "scheduled_generator_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[int] = mapped_column(Integer, ForeignKey("scheduled_generator_configs.id"), nullable=False)

    # 触发信息
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)  # scheduled/manual/resume
    trigger_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # 执行结果
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # success/failed/partial

    # 统计信息
    books_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    books_success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    books_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    books_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    total_chapters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 详细信息
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON格式的详细日志
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # 关系
    config: Mapped["ScheduledGeneratorConfig"] = relationship("ScheduledGeneratorConfig", back_populates="logs")
