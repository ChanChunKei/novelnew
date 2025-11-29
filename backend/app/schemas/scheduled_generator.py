"""
定时生成器 Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class ScheduledGeneratorConfigCreate(BaseModel):
    """创建定时配置请求"""
    name: str = Field(..., description="配置名称")
    trigger_hour: int = Field(..., ge=0, le=23, description="触发小时（太平洋时间，0-23）")
    trigger_minute: int = Field(..., ge=0, le=59, description="触发分钟（0-59）")
    generation_mode: str = Field(default="basic", description="生成模式：basic/enhanced")
    auto_upload_fanqie: bool = Field(default=False, description="是否自动上传番茄小说")
    upload_interval_seconds: int = Field(default=20, ge=5, le=60, description="上传间隔（秒）")
    concurrent_books: int = Field(default=1, ge=1, le=5, description="并发生成书籍数（1-5）")
    max_duration_per_book: int = Field(default=120, ge=10, le=600, description="单本最大时长（分钟）")

    @field_validator("generation_mode")
    @classmethod
    def validate_generation_mode(cls, v: str) -> str:
        if v not in ["basic", "enhanced"]:
            raise ValueError("generation_mode must be 'basic' or 'enhanced'")
        return v


class ScheduledGeneratorConfigUpdate(BaseModel):
    """更新定时配置请求"""
    name: Optional[str] = None
    trigger_hour: Optional[int] = Field(None, ge=0, le=23)
    trigger_minute: Optional[int] = Field(None, ge=0, le=59)
    generation_mode: Optional[str] = None
    auto_upload_fanqie: Optional[bool] = None
    upload_interval_seconds: Optional[int] = Field(None, ge=5, le=60)
    concurrent_books: Optional[int] = Field(None, ge=1, le=5)
    max_duration_per_book: Optional[int] = Field(None, ge=10, le=600)

    @field_validator("generation_mode")
    @classmethod
    def validate_generation_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ["basic", "enhanced"]:
            raise ValueError("generation_mode must be 'basic' or 'enhanced'")
        return v


class ScheduledGeneratorConfigResponse(BaseModel):
    """定时配置响应"""
    id: int
    user_id: int
    name: str
    enabled: bool
    trigger_hour: int
    trigger_minute: int
    generation_mode: str
    auto_upload_fanqie: bool
    upload_interval_seconds: int
    concurrent_books: int
    max_duration_per_book: int
    status: str
    total_runs: int
    total_books_processed: int
    total_books_success: int
    total_books_failed: int
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AddToQueueRequest(BaseModel):
    """添加到队列请求"""
    novel_ids: List[str] = Field(..., description="小说项目ID列表")
    priority: int = Field(default=0, description="优先级")


class QueueItemResponse(BaseModel):
    """队列项响应"""
    id: int
    config_id: int
    novel_id: str
    priority: int
    position: int
    status: str
    auto_generator_task_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    chapters_generated: int
    chapters_target: int
    uploaded_to_fanqie: bool
    upload_result: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SchedulerStatusResponse(BaseModel):
    """调度器状态响应"""
    config_id: int
    status: str
    enabled: bool
    next_run_at: Optional[str] = None
    last_run_at: Optional[str] = None
    queue_stats: Dict[str, int]
    currently_running: List[Dict[str, Any]]
    total_stats: Dict[str, int]


class LogResponse(BaseModel):
    """日志响应"""
    id: int
    config_id: int
    trigger_type: str
    trigger_time: datetime
    status: str
    books_processed: int
    books_success: int
    books_failed: int
    books_skipped: int
    total_chapters: int
    total_duration_seconds: int
    details: Optional[str] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
