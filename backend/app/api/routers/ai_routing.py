"""
AI路由管理API

提供管理AI提供商和功能路由的接口
"""
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, validator
from sqlalchemy import update as sql_update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user, get_current_admin, get_session
from ...core.rate_limit import limiter
from ...models.user import User
from ...models.ai_routing import AIProvider, AIFunctionRoute, AIFunctionCallLog
from ...config.ai_function_config import AIFunctionType
from ...repositories.ai_routing_repository import (
    AIProviderRepository,
    AIFunctionRouteRepository,
    AIFunctionCallLogRepository,
)

logger = logging.getLogger(__name__)

# ✅ 修复：统一前后端路径，改为 /api/ai
router = APIRouter(prefix="/api/ai", tags=["AI路由管理"])


# ==================== Schemas ====================

class AIProviderPublicSchema(BaseModel):
    """公开的Provider信息（普通用户可见）"""
    id: int
    name: str
    display_name: str
    status: str

    class Config:
        from_attributes = True


class AIProviderAdminSchema(AIProviderPublicSchema):
    """完整的Provider信息（仅管理员可见）"""
    base_url: str
    priority: int
    cost_per_1k_tokens: Optional[float] = None
    api_key_env: Optional[str] = None


class AIProviderCreateSchema(BaseModel):
    """创建Provider的请求体"""
    name: str
    display_name: str
    base_url: str
    priority: int = 100
    cost_per_1k_tokens: Optional[float] = None
    api_key_env: Optional[str] = None
    status: str = "active"


class AIProviderUpdateSchema(BaseModel):
    """更新Provider的请求体"""
    display_name: Optional[str] = None
    base_url: Optional[str] = None
    priority: Optional[int] = None
    cost_per_1k_tokens: Optional[float] = None
    api_key_env: Optional[str] = None
    status: Optional[str] = None


class AIFunctionRouteSchema(BaseModel):
    id: int
    function_type: str
    display_name: str
    primary_provider_id: int
    primary_model: str
    temperature: float
    timeout_seconds: int
    max_retries: int
    enabled: bool

    class Config:
        from_attributes = True


class AICallLogSchema(BaseModel):
    id: int
    function_type: str
    provider_id: Optional[int]
    model: Optional[str]
    status: str
    is_fallback: bool
    duration_ms: Optional[int]
    error_type: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    total_calls: int
    success_rate: float
    avg_duration_ms: int
    total_cost_usd: float
    by_function: dict
    by_provider: dict


# ==================== API Endpoints ====================

@router.get("/providers")
async def list_providers(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    获取所有AI提供商列表

    普通用户只能看到基本信息，管理员可以看到完整信息
    """
    repo = AIProviderRepository(session)
    providers = await repo.get_all_active()

    # ✅ 根据用户权限返回不同的Schema
    if current_user.is_admin:
        return [AIProviderAdminSchema.model_validate(p) for p in providers]
    else:
        return [AIProviderPublicSchema.model_validate(p) for p in providers]


@router.post("/providers", response_model=AIProviderAdminSchema, status_code=status.HTTP_201_CREATED)
async def create_provider(
    provider_data: AIProviderCreateSchema,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_admin),  # ✅ 仅管理员可创建
):
    """
    创建新的AI提供商

    ✅ 修复：补齐缺失的 POST 接口
    """
    # 检查名称是否已存在
    repo = AIProviderRepository(session)
    existing = await repo.get_by_name(provider_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider名称 '{provider_data.name}' 已存在"
        )

    # 创建新Provider
    new_provider = AIProvider(**provider_data.model_dump())
    session.add(new_provider)
    await session.commit()
    await session.refresh(new_provider)

    logger.info(f"管理员 {current_user.username} 创建了新Provider: {new_provider.name}")
    return AIProviderAdminSchema.model_validate(new_provider)


@router.put("/providers/{provider_id}", response_model=AIProviderAdminSchema)
async def update_provider(
    provider_id: int,
    provider_data: AIProviderUpdateSchema,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_admin),  # ✅ 仅管理员可更新
):
    """
    更新AI提供商配置

    ✅ 修复：补齐缺失的 PUT 接口
    """
    repo = AIProviderRepository(session)
    provider = await repo.get_by_id(provider_id)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {provider_id} 的Provider"
        )

    # 更新字段
    update_data = provider_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(provider, key, value)

    await session.commit()
    await session.refresh(provider)

    logger.info(f"管理员 {current_user.username} 更新了Provider {provider_id}")
    return AIProviderAdminSchema.model_validate(provider)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_admin),  # ✅ 仅管理员可删除
):
    """
    删除AI提供商（软删除，设置status为inactive）

    ✅ 修复：补齐缺失的 DELETE 接口
    """
    repo = AIProviderRepository(session)
    provider = await repo.get_by_id(provider_id)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {provider_id} 的Provider"
        )

    # 软删除
    provider.status = "inactive"
    await session.commit()

    logger.info(f"管理员 {current_user.username} 删除了Provider {provider_id}")
    return None


@router.get("/routes", response_model=List[AIFunctionRouteSchema])
async def list_routes(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """获取所有功能路由配置"""
    repo = AIFunctionRouteRepository(session)
    routes = await repo.get_all_enabled()
    return routes


@router.get("/routes/{function_type}", response_model=AIFunctionRouteSchema)
async def get_route(
    function_type: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """获取指定功能的路由配置"""
    repo = AIFunctionRouteRepository(session)
    route = await repo.get_by_function_type(function_type)

    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到功能 {function_type} 的路由配置"
        )

    return route


# ✅ 修复：添加 function-configs 别名接口（与前端调用一致）
@router.get("/function-configs", response_model=List[AIFunctionRouteSchema])
async def list_function_configs(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """获取所有功能配置（routes的别名）"""
    repo = AIFunctionRouteRepository(session)
    routes = await repo.get_all_enabled()
    return routes


@router.put("/function-configs/{function_name}", response_model=AIFunctionRouteSchema)
async def update_function_config(
    function_name: str,
    config_data: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_admin),  # ✅ 仅管理员可更新
):
    """
    更新功能配置

    ✅ 修复：补齐缺失的 PUT 接口
    """
    repo = AIFunctionRouteRepository(session)
    route = await repo.get_by_function_type(function_name)

    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到功能 {function_name} 的配置"
        )

    # 更新允许的字段
    allowed_fields = {'primary_provider_id', 'primary_model', 'temperature',
                     'timeout_seconds', 'max_retries', 'enabled'}
    for key, value in config_data.items():
        if key in allowed_fields:
            setattr(route, key, value)

    await session.commit()
    await session.refresh(route)

    logger.info(f"管理员 {current_user.username} 更新了功能配置 {function_name}")
    return route


@router.get("/logs", response_model=List[AICallLogSchema])
@limiter.limit("30/minute")  # ✅ 每分钟最多30次
async def list_logs(
    request: Request,
    function_type: Optional[str] = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """获取AI调用日志（限流：30次/分钟）"""
    repo = AIFunctionCallLogRepository(session)
    logs = await repo.get_recent_logs(function_type=function_type, limit=limit)
    
    return [
        AICallLogSchema(
            id=log.id,
            function_type=log.function_type,
            provider_id=log.provider_id,
            model=log.model,
            status=log.status,
            is_fallback=log.is_fallback,
            duration_ms=log.duration_ms,
            error_type=log.error_type,
            created_at=log.created_at.isoformat() if log.created_at else "",
        )
        for log in logs
    ]


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    function_type: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """获取统计信息"""
    repo = AIFunctionCallLogRepository(session)
    stats = await repo.get_stats(function_type=function_type)
    
    return StatsResponse(
        total_calls=stats.get("total_calls", 0),
        success_rate=stats.get("success_rate", 0.0),
        avg_duration_ms=stats.get("avg_duration_ms", 0),
        total_cost_usd=stats.get("total_cost_usd", 0.0),
        by_function=stats.get("by_function", {}),
        by_provider=stats.get("by_provider", {}),
    )


# ==================== 配置更新API ====================

class UpdateRouteRequest(BaseModel):
    primary_provider_id: Optional[int] = Field(None, gt=0, description="主提供商ID")
    primary_model: Optional[str] = Field(None, min_length=1, max_length=200, description="主模型名称")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="温度参数(0.0-2.0)")
    timeout_seconds: Optional[int] = Field(None, ge=1, le=3600, description="超时时间(1-3600秒)")
    max_retries: Optional[int] = Field(None, ge=0, le=10, description="最大重试次数(0-10)")
    enabled: Optional[bool] = Field(None, description="是否启用")

    @validator('primary_model')
    def validate_model_name(cls, v):
        """验证模型名称不为空"""
        if v is not None and not v.strip():
            raise ValueError('模型名称不能为空')
        return v.strip() if v else v


@router.patch("/routes/{function_type}")
@limiter.limit("10/minute")  # ✅ 配置更新限流更严格
async def update_route(
    http_request: Request,
    function_type: str,
    request: UpdateRouteRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_admin),  # ✅ 改为require admin
):
    """
    更新功能路由配置

    需要管理员权限（限流：10次/分钟）
    """
    # ✅ 验证function_type
    valid_types = [t.value for t in AIFunctionType]
    if function_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的功能类型: {function_type}，有效值: {', '.join(valid_types)}"
        )

    repo = AIFunctionRouteRepository(session)
    route = await repo.get_by_function_type(function_type)

    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到功能 {function_type} 的路由配置"
        )

    # ✅ 使用乐观锁：记录当前版本号
    old_version = route.version

    # 构建更新字段
    update_values = {}
    if request.primary_provider_id is not None:
        update_values["primary_provider_id"] = request.primary_provider_id
    if request.primary_model is not None:
        update_values["primary_model"] = request.primary_model
    if request.temperature is not None:
        update_values["temperature"] = request.temperature
    if request.timeout_seconds is not None:
        update_values["timeout_seconds"] = request.timeout_seconds
    if request.max_retries is not None:
        update_values["max_retries"] = request.max_retries
    if request.enabled is not None:
        update_values["enabled"] = request.enabled

    # ✅ 使用乐观锁更新：只有当version未变时才更新
    update_values["version"] = old_version + 1

    result = await session.execute(
        sql_update(AIFunctionRoute)
        .where(
            and_(
                AIFunctionRoute.id == route.id,
                AIFunctionRoute.version == old_version  # ✅ 乐观锁条件
            )
        )
        .values(**update_values)
    )

    # ✅ 检查是否更新成功
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="配置已被其他用户修改，请刷新后重试"
        )

    await session.commit()
    
    logger.info(
        f"用户 {current_user.id} 更新了功能 {function_type} 的路由配置，"
        f"版本号: {route.version}"
    )
    
    return {"message": "配置更新成功", "version": route.version}


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "service": "ai-routing",
        "version": "1.0.0"
    }

