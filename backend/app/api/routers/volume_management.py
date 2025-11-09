"""
分卷管理API

✅ 修复：补齐前端需要的分卷管理接口
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user, get_session
from ...schemas.user import UserInDB
from ...services.story_metrics_service import StoryMetricsService
from ...services.volume_split_service import VolumeSplitService
from ...services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/novels", tags=["分卷管理"])


# ==================== Schemas ====================

class StoryMetricsResponse(BaseModel):
    """剧情指标响应"""
    chapter_number: int
    word_count: int
    key_event_count: int
    major_event_flag: bool
    foreshadow_count: int
    foreshadow_max_conf: float
    character_breakthrough_flag: bool
    world_shock_flag: bool
    climax_score: int
    stage_score: int
    
    class Config:
        from_attributes = True


class AutoSplitRequest(BaseModel):
    """自动分卷请求"""
    threshold: Optional[int] = None


class SplitConfigResponse(BaseModel):
    """分卷配置响应"""
    enabled: bool
    min_chapters: int
    max_chapters: int
    window_size: int
    score_threshold: int
    cooldown_chapters: int
    naming_model: str
    naming_timeout: int
    fallback_naming: bool


class SplitConfigUpdate(BaseModel):
    """分卷配置更新"""
    enabled: Optional[bool] = None
    min_chapters: Optional[int] = None
    max_chapters: Optional[int] = None
    window_size: Optional[int] = None
    score_threshold: Optional[int] = None
    cooldown_chapters: Optional[int] = None
    naming_model: Optional[str] = None
    naming_timeout: Optional[int] = None
    fallback_naming: Optional[bool] = None


# ==================== API Endpoints ====================

@router.get("/{project_id}/story-metrics", response_model=List[StoryMetricsResponse])
async def get_story_metrics(
    project_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """
    获取项目的剧情指标
    
    ✅ 修复：补齐缺失的剧情指标接口
    """
    from sqlalchemy import select, and_
    from ...models.story_metrics import ChapterStoryMetrics
    from ...models.novel import Project
    
    # 验证项目权限
    stmt = select(Project).where(
        and_(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到项目 {project_id}"
        )
    
    # 获取剧情指标
    stmt = (
        select(ChapterStoryMetrics)
        .where(ChapterStoryMetrics.project_id == project_id)
        .order_by(ChapterStoryMetrics.chapter_number)
    )
    result = await db.execute(stmt)
    metrics = result.scalars().all()
    
    return [StoryMetricsResponse.model_validate(m) for m in metrics]


@router.post("/{project_id}/auto-split")
async def trigger_auto_split(
    project_id: str,
    request_data: AutoSplitRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """
    触发自动分卷
    
    ✅ 修复：补齐缺失的自动分卷接口
    """
    from sqlalchemy import select, and_
    from ...models.novel import Project
    
    # 验证项目权限
    stmt = select(Project).where(
        and_(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到项目 {project_id}"
        )
    
    # 创建服务
    llm_service = LLMService(db)
    split_service = VolumeSplitService(db, llm_service)
    
    # 构建配置
    config = None
    if request_data.threshold is not None:
        config = {"score_threshold": request_data.threshold}
    
    # 执行分卷评估
    new_volume = await split_service.evaluate_project(
        project_id=project_id,
        config=config
    )
    
    if new_volume:
        logger.info(f"项目 {project_id} 创建了新卷: {new_volume.title}")
        return {
            "success": True,
            "volume_id": new_volume.id,
            "volume_number": new_volume.volume_number,
            "title": new_volume.title,
            "description": new_volume.description
        }
    else:
        return {
            "success": False,
            "message": "当前不满足分卷条件"
        }


@router.get("/{project_id}/split-config", response_model=SplitConfigResponse)
async def get_split_config(
    project_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """
    获取分卷配置
    
    ✅ 修复：补齐缺失的分卷配置接口
    """
    from sqlalchemy import select, and_
    from ...models.novel import Project
    
    # 验证项目权限
    stmt = select(Project).where(
        and_(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到项目 {project_id}"
        )
    
    # 从项目配置中获取分卷配置，如果没有则返回默认值
    generation_config = project.generation_config or {}
    split_config = generation_config.get("volume_split", VolumeSplitService.DEFAULT_CONFIG)
    
    return SplitConfigResponse(**split_config)


@router.put("/{project_id}/split-config", response_model=SplitConfigResponse)
async def update_split_config(
    project_id: str,
    config_update: SplitConfigUpdate,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """
    更新分卷配置
    
    ✅ 修复：补齐缺失的分卷配置更新接口
    """
    from sqlalchemy import select, and_
    from ...models.novel import Project
    
    # 验证项目权限
    stmt = select(Project).where(
        and_(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到项目 {project_id}"
        )
    
    # 获取当前配置
    generation_config = project.generation_config or {}
    split_config = generation_config.get("volume_split", VolumeSplitService.DEFAULT_CONFIG.copy())
    
    # 更新配置
    update_data = config_update.model_dump(exclude_unset=True)
    split_config.update(update_data)
    
    # 保存回项目
    generation_config["volume_split"] = split_config
    project.generation_config = generation_config
    
    await db.commit()
    
    logger.info(f"用户 {current_user.username} 更新了项目 {project_id} 的分卷配置")
    return SplitConfigResponse(**split_config)

