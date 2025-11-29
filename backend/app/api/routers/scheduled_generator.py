"""
定时自动生成器 API路由
"""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models.user import User as UserInDB
from ...services.scheduled_generator_service import ScheduledGeneratorService
from ...schemas.scheduled_generator import (
    ScheduledGeneratorConfigCreate,
    ScheduledGeneratorConfigUpdate,
    ScheduledGeneratorConfigResponse,
    AddToQueueRequest,
    QueueItemResponse,
    SchedulerStatusResponse,
    LogResponse,
)
from ..dependencies import get_current_user

router = APIRouter(prefix="/scheduled-generator", tags=["scheduled-generator"])
logger = logging.getLogger(__name__)


# ========== 配置管理 ==========

@router.post("/config", response_model=ScheduledGeneratorConfigResponse)
async def create_config(
    data: ScheduledGeneratorConfigCreate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ScheduledGeneratorConfigResponse:
    """创建定时配置"""
    try:
        config = await ScheduledGeneratorService.create_config(
            session=session,
            user_id=current_user.id,
            name=data.name,
            trigger_hour=data.trigger_hour,
            trigger_minute=data.trigger_minute,
            generation_mode=data.generation_mode,
            auto_upload_fanqie=data.auto_upload_fanqie,
            upload_interval_seconds=data.upload_interval_seconds,
            concurrent_books=data.concurrent_books,
            max_duration_per_book=data.max_duration_per_book,
        )
        return ScheduledGeneratorConfigResponse.model_validate(config)
    except Exception as e:
        logger.exception(f"Error creating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config", response_model=ScheduledGeneratorConfigResponse)
async def get_config(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ScheduledGeneratorConfigResponse:
    """获取当前用户的配置"""
    config = await ScheduledGeneratorService.get_user_config(session, current_user.id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return ScheduledGeneratorConfigResponse.model_validate(config)


@router.put("/config/{config_id}", response_model=ScheduledGeneratorConfigResponse)
async def update_config(
    config_id: int,
    data: ScheduledGeneratorConfigUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ScheduledGeneratorConfigResponse:
    """更新配置"""
    try:
        # 验证配置所有权
        config = await ScheduledGeneratorService.get_config(session, config_id)
        if not config or config.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="配置不存在")

        # 只更新非None的字段
        update_data = data.model_dump(exclude_unset=True)
        updated_config = await ScheduledGeneratorService.update_config(
            session, config_id, **update_data
        )
        return ScheduledGeneratorConfigResponse.model_validate(updated_config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/config/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    """删除配置"""
    config = await ScheduledGeneratorService.get_config(session, config_id)
    if not config or config.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="配置不存在")

    # 先停止调度器
    await ScheduledGeneratorService.stop_scheduler(session, config_id)

    # 删除配置（会级联删除队列和日志）
    await session.delete(config)
    await session.commit()


# ========== 队列管理 ==========

@router.post("/queue/add", response_model=List[QueueItemResponse])
async def add_to_queue(
    data: AddToQueueRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[QueueItemResponse]:
    """添加书籍到队列"""
    try:
        # 获取用户的配置
        config = await ScheduledGeneratorService.get_user_config(session, current_user.id)
        if not config:
            raise HTTPException(status_code=404, detail="请先创建定时配置")

        items = await ScheduledGeneratorService.add_to_queue(
            session, config.id, data.novel_ids, data.priority
        )
        return [QueueItemResponse.model_validate(item) for item in items]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error adding to queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue", response_model=List[QueueItemResponse])
async def get_queue(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[QueueItemResponse]:
    """获取队列列表"""
    config = await ScheduledGeneratorService.get_user_config(session, current_user.id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    items = await ScheduledGeneratorService.get_queue(session, config.id)
    return [QueueItemResponse.model_validate(item) for item in items]


@router.delete("/queue/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_queue(
    item_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    """从队列中移除书籍"""
    try:
        await ScheduledGeneratorService.remove_from_queue(session, item_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error removing from queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 任务控制 ==========

@router.post("/start", status_code=status.HTTP_200_OK)
async def start_scheduler(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """启动定时任务"""
    try:
        config = await ScheduledGeneratorService.get_user_config(session, current_user.id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")

        await ScheduledGeneratorService.start_scheduler(session, config.id)
        return {"status": "success", "message": "定时任务已启动"}
    except Exception as e:
        logger.exception(f"Error starting scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pause", status_code=status.HTTP_200_OK)
async def pause_scheduler(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """暂停定时任务"""
    try:
        config = await ScheduledGeneratorService.get_user_config(session, current_user.id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")

        await ScheduledGeneratorService.pause_scheduler(session, config.id)
        return {"status": "success", "message": "定时任务已暂停"}
    except Exception as e:
        logger.exception(f"Error pausing scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume", status_code=status.HTTP_200_OK)
async def resume_scheduler(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """恢复定时任务"""
    try:
        config = await ScheduledGeneratorService.get_user_config(session, current_user.id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")

        await ScheduledGeneratorService.resume_scheduler(session, config.id)
        return {"status": "success", "message": "定时任务已恢复"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error resuming scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop", status_code=status.HTTP_200_OK)
async def stop_scheduler(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """停止定时任务"""
    try:
        config = await ScheduledGeneratorService.get_user_config(session, current_user.id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")

        await ScheduledGeneratorService.stop_scheduler(session, config.id)
        return {"status": "success", "message": "定时任务已停止"}
    except Exception as e:
        logger.exception(f"Error stopping scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger-now", status_code=status.HTTP_200_OK)
async def trigger_now(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """立即触发一次生成"""
    try:
        config = await ScheduledGeneratorService.get_user_config(session, current_user.id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")

        await ScheduledGeneratorService.trigger_now(session, config.id)
        return {"status": "success", "message": "已触发生成任务"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error triggering now: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 状态查询 ==========

@router.get("/status", response_model=SchedulerStatusResponse)
async def get_status(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> SchedulerStatusResponse:
    """获取当前状态"""
    try:
        config = await ScheduledGeneratorService.get_user_config(session, current_user.id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")

        status_data = await ScheduledGeneratorService.get_status(session, config.id)
        return SchedulerStatusResponse(**status_data)
    except Exception as e:
        logger.exception(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs", response_model=List[LogResponse])
async def get_logs(
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[LogResponse]:
    """获取执行日志"""
    from sqlalchemy import select
    from ...models.scheduled_generator import ScheduledGeneratorLog

    config = await ScheduledGeneratorService.get_user_config(session, current_user.id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    result = await session.execute(
        select(ScheduledGeneratorLog)
        .where(ScheduledGeneratorLog.config_id == config.id)
        .order_by(ScheduledGeneratorLog.created_at.desc())
        .limit(limit)
    )
    logs = list(result.scalars().all())
    return [LogResponse.model_validate(log) for log in logs]
