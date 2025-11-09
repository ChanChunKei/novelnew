"""自动生成器 Schemas"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class CreateAutoGeneratorTaskRequest(BaseModel):
    """创建自动生成任务请求"""
    project_id: str
    target_chapters: Optional[int] = None
    chapters_per_batch: int = 1
    interval_seconds: int = 60
    auto_select_version: bool = True
    auto_upload: bool = False
    fanqie_account: Optional[str] = None
    generation_config: Optional[dict] = None


class CreateBatchTasksRequest(BaseModel):
    """批量创建任务请求"""
    project_ids: Optional[List[str]] = Field(None, description="项目ID列表，None表示所有项目")
    generation_interval: Optional[int] = Field(None, description="生成间隔（秒），None表示自动计算")
    auto_start: bool = Field(True, description="是否自动启动")
    auto_upload: bool = Field(False, description="是否自动上传到番茄")
    fanqie_account: Optional[str] = Field(None, description="番茄账号")


class UpdateTaskScheduleRequest(BaseModel):
    """更新任务调度请求"""
    scheduled_start_time: Optional[datetime] = Field(None, description="定时启动时间")
    delay_seconds: Optional[int] = Field(None, description="启动延迟（秒）")
    interval_seconds: Optional[int] = Field(None, description="生成间隔（秒）")


class TaskScheduleInfo(BaseModel):
    """任务调度信息"""
    project_id: str
    project_title: str
    task_id: int
    scheduled_start_time: str
    delay_seconds: int
    interval_seconds: int


class BatchTasksResponse(BaseModel):
    """批量创建任务响应"""
    batch_id: str
    tasks_created: int
    start_interval: int
    generation_interval: int
    max_concurrent: int
    estimated_cycle_time: int
    schedule: List[TaskScheduleInfo]


class ScheduleOptionsResponse(BaseModel):
    """调度选项响应"""
    generation_intervals: List[dict]
    start_delays: List[dict]


class AutoGeneratorTaskResponse(BaseModel):
    """自动生成任务响应"""
    id: int
    project_id: str
    user_id: int
    status: str
    target_chapters: Optional[int]
    chapters_per_batch: int
    interval_seconds: int
    auto_select_version: bool
    auto_upload: bool
    fanqie_account: Optional[str]
    generation_config: Optional[dict] = None
    chapters_generated: int
    total_tokens_used: int
    error_count: int
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    last_generation_at: Optional[datetime]
    # 定时启动功能字段
    scheduled_start_time: Optional[datetime] = None
    delay_seconds: int = 0
    batch_id: Optional[str] = None

    class Config:
        from_attributes = True


class AutoGeneratorLogResponse(BaseModel):
    """自动生成日志响应"""
    id: int
    task_id: int
    chapter_number: Optional[int]
    log_type: str
    message: str
    details: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True
