"""
异步分析API端点

提供：
1. 查询分析状态
2. 获取未读通知
3. 标记通知已读
4. 手动触发重试
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload  # ✅ 添加selectinload
from pydantic import BaseModel
from datetime import datetime

# ✅ 修复：从正确的路径导入
from ...db.session import get_session
from ...models.async_task import PendingAnalysis, AnalysisNotification
from ...core.dependencies import get_current_user
from ...schemas.user import UserInDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/async-analysis", tags=["异步分析"])


# ==================== Schemas ====================

class PendingAnalysisResponse(BaseModel):
    """待处理分析响应"""
    id: int
    chapter_id: int
    chapter_number: int
    status: str
    priority: int
    retry_count: int
    max_retries: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    error_message: Optional[str]
    error_type: Optional[str]
    
    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    """通知响应"""
    id: int
    chapter_id: int
    chapter_number: int
    notification_type: str
    title: str
    message: Optional[str]
    data: Optional[dict]
    is_read: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class AnalysisStatusResponse(BaseModel):
    """分析状态响应"""
    total: int
    pending: int
    processing: int
    completed: int
    failed: int
    recent_tasks: List[PendingAnalysisResponse]


# ==================== API端点 ====================

@router.get("/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    project_id: str = Query(..., description="项目ID"),
    limit: int = Query(10, ge=1, le=100, description="最近任务数量"),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """
    获取分析状态概览
    
    返回：
    - 总任务数
    - 各状态任务数
    - 最近的任务列表
    """
    # 查询统计
    stmt = select(PendingAnalysis).where(
        and_(
            PendingAnalysis.project_id == project_id,
            PendingAnalysis.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    all_tasks = list(result.scalars().all())
    
    # 统计各状态
    total = len(all_tasks)
    pending = sum(1 for t in all_tasks if t.status == 'pending')
    processing = sum(1 for t in all_tasks if t.status == 'processing')
    completed = sum(1 for t in all_tasks if t.status == 'completed')
    failed = sum(1 for t in all_tasks if t.status == 'failed')
    
    # 获取最近任务
    # ✅ 添加selectinload预加载chapter关系，避免MissingGreenlet
    stmt = (
        select(PendingAnalysis)
        .where(
            and_(
                PendingAnalysis.project_id == project_id,
                PendingAnalysis.user_id == current_user.id
            )
        )
        .options(selectinload(PendingAnalysis.chapter))
        .order_by(desc(PendingAnalysis.created_at))
        .limit(limit)
    )

    result = await db.execute(stmt)
    recent_tasks = result.scalars().all()
    
    # 构建响应
    recent_tasks_data = []
    for task in recent_tasks:
        recent_tasks_data.append(PendingAnalysisResponse(
            id=task.id,
            chapter_id=task.chapter_id,
            chapter_number=task.chapter.chapter_number,
            status=task.status,
            priority=task.priority,
            retry_count=task.retry_count,
            max_retries=task.max_retries,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            duration_seconds=task.duration_seconds,
            error_message=task.error_message,
            error_type=task.error_type
        ))
    
    return AnalysisStatusResponse(
        total=total,
        pending=pending,
        processing=processing,
        completed=completed,
        failed=failed,
        recent_tasks=recent_tasks_data
    )


@router.get("/notifications", response_model=List[NotificationResponse])
async def get_notifications(
    unread_only: bool = Query(False, description="仅未读"),
    limit: int = Query(20, ge=1, le=100, description="数量限制"),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """
    获取通知列表

    参数：
    - unread_only: 仅返回未读通知
    - limit: 返回数量
    """
    # ✅ 添加selectinload预加载chapter关系，避免MissingGreenlet
    stmt = (
        select(AnalysisNotification)
        .where(AnalysisNotification.user_id == current_user.id)
        .options(selectinload(AnalysisNotification.chapter))
    )

    if unread_only:
        stmt = stmt.where(AnalysisNotification.is_read == 0)

    stmt = stmt.order_by(desc(AnalysisNotification.created_at)).limit(limit)

    result = await db.execute(stmt)
    notifications = result.scalars().all()
    
    # 构建响应
    return [
        NotificationResponse(
            id=n.id,
            chapter_id=n.chapter_id,
            chapter_number=n.chapter.chapter_number,
            notification_type=n.notification_type,
            title=n.title,
            message=n.message,
            data=n.data,
            is_read=n.is_read,
            created_at=n.created_at
        )
        for n in notifications
    ]


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """标记通知为已读"""
    stmt = select(AnalysisNotification).where(
        and_(
            AnalysisNotification.id == notification_id,
            AnalysisNotification.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")
    
    notification.mark_as_read()
    await db.commit()
    
    return {"message": "已标记为已读"}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """标记所有通知为已读"""
    stmt = select(AnalysisNotification).where(
        and_(
            AnalysisNotification.user_id == current_user.id,
            AnalysisNotification.is_read == 0
        )
    )
    result = await db.execute(stmt)
    notifications = result.scalars().all()
    
    for notification in notifications:
        notification.mark_as_read()
    
    await db.commit()
    
    return {"message": f"已标记 {len(notifications)} 条通知为已读"}


@router.post("/tasks/{task_id}/retry")
async def retry_failed_task(
    task_id: int,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """手动重试失败的任务"""
    stmt = select(PendingAnalysis).where(
        and_(
            PendingAnalysis.id == task_id,
            PendingAnalysis.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if not task.is_failed:
        raise HTTPException(status_code=400, detail="只能重试失败的任务")
    
    if not task.can_retry:
        raise HTTPException(
            status_code=400,
            detail=f"已达到最大重试次数 ({task.max_retries})"
        )
    
    # 重置状态
    task.status = 'pending'
    task.error_message = None
    task.error_type = None
    await db.commit()
    
    return {"message": "任务已重新加入队列"}


@router.get("/tasks/{chapter_id}/latest", response_model=Optional[PendingAnalysisResponse])
async def get_chapter_latest_task(
    chapter_id: int,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """获取章节的最新分析任务"""
    # ✅ 添加selectinload预加载chapter关系，避免MissingGreenlet
    stmt = (
        select(PendingAnalysis)
        .where(
            and_(
                PendingAnalysis.chapter_id == chapter_id,
                PendingAnalysis.user_id == current_user.id
            )
        )
        .options(selectinload(PendingAnalysis.chapter))
        .order_by(desc(PendingAnalysis.created_at))
        .limit(1)
    )

    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    
    if not task:
        return None
    
    return PendingAnalysisResponse(
        id=task.id,
        chapter_id=task.chapter_id,
        chapter_number=task.chapter.chapter_number,
        status=task.status,
        priority=task.priority,
        retry_count=task.retry_count,
        max_retries=task.max_retries,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        duration_seconds=task.duration_seconds,
        error_message=task.error_message,
        error_type=task.error_type
    )


# ✅ 修复：补齐前端需要的任务列表/详情/取消接口
@router.get("/tasks", response_model=List[PendingAnalysisResponse])
async def get_tasks(
    status: Optional[str] = Query(None, description="按状态过滤"),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """
    获取任务列表

    ✅ 修复：补齐缺失的任务列表接口
    """
    stmt = (
        select(PendingAnalysis)
        .where(PendingAnalysis.user_id == current_user.id)
        .options(selectinload(PendingAnalysis.chapter))
    )

    if status:
        stmt = stmt.where(PendingAnalysis.status == status)

    stmt = stmt.order_by(desc(PendingAnalysis.created_at))

    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return [
        PendingAnalysisResponse(
            id=task.id,
            chapter_id=task.chapter_id,
            chapter_number=task.chapter.chapter_number,
            status=task.status,
            priority=task.priority,
            retry_count=task.retry_count,
            max_retries=task.max_retries,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            duration_seconds=task.duration_seconds,
            error_message=task.error_message,
            error_type=task.error_type
        )
        for task in tasks
    ]


@router.get("/tasks/{task_id}", response_model=PendingAnalysisResponse)
async def get_task_detail(
    task_id: int,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """
    获取任务详情

    ✅ 修复：补齐缺失的任务详情接口
    """
    stmt = (
        select(PendingAnalysis)
        .where(
            and_(
                PendingAnalysis.id == task_id,
                PendingAnalysis.user_id == current_user.id
            )
        )
        .options(selectinload(PendingAnalysis.chapter))
    )

    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到任务 {task_id}"
        )

    return PendingAnalysisResponse(
        id=task.id,
        chapter_id=task.chapter_id,
        chapter_number=task.chapter.chapter_number,
        status=task.status,
        priority=task.priority,
        retry_count=task.retry_count,
        max_retries=task.max_retries,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        duration_seconds=task.duration_seconds,
        error_message=task.error_message,
        error_type=task.error_type
    )


@router.post("/tasks/{task_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_task(
    task_id: int,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """
    取消任务

    ✅ 修复：补齐缺失的取消任务接口
    """
    stmt = (
        select(PendingAnalysis)
        .where(
            and_(
                PendingAnalysis.id == task_id,
                PendingAnalysis.user_id == current_user.id
            )
        )
    )

    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到任务 {task_id}"
        )

    # 只能取消pending或processing状态的任务
    if task.status not in ['pending', 'processing']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态为 {task.status}，无法取消"
        )

    # 更新状态为cancelled
    task.status = 'cancelled'
    task.completed_at = datetime.now()

    await db.commit()

    logger.info(f"用户 {current_user.username} 取消了任务 {task_id}")
    return None

