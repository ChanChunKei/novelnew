"""
AI路由系统Repository
"""
import json
import logging
from typing import List, Optional, Dict
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ai_routing import AIProvider, AIFunctionRoute, AIFunctionCallLog

logger = logging.getLogger(__name__)


class AIProviderRepository:
    """AI提供商Repository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, provider_id: int) -> Optional[AIProvider]:
        """根据ID获取provider"""
        result = await self.session.execute(
            select(AIProvider).where(AIProvider.id == provider_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[AIProvider]:
        """根据名称获取provider"""
        result = await self.session.execute(
            select(AIProvider).where(AIProvider.name == name)
        )
        return result.scalar_one_or_none()

    async def get_all_active(self) -> List[AIProvider]:
        """获取所有活跃的providers"""
        result = await self.session.execute(
            select(AIProvider)
            .where(AIProvider.status == "active")
            .order_by(AIProvider.priority)
        )
        return list(result.scalars().all())

    async def create(self, provider: AIProvider) -> AIProvider:
        """创建provider"""
        self.session.add(provider)
        await self.session.flush()
        return provider

    async def update(self, provider: AIProvider) -> AIProvider:
        """更新provider"""
        await self.session.flush()
        return provider


class AIFunctionRouteRepository:
    """AI功能路由Repository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_function_type(self, function_type: str) -> Optional[AIFunctionRoute]:
        """根据功能类型获取路由配置"""
        result = await self.session.execute(
            select(AIFunctionRoute)
            .options(selectinload(AIFunctionRoute.primary_provider))  # ✅ 预加载provider
            .where(
                and_(
                    AIFunctionRoute.function_type == function_type,
                    AIFunctionRoute.enabled == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_all_enabled(self) -> List[AIFunctionRoute]:
        """获取所有启用的路由配置"""
        result = await self.session.execute(
            select(AIFunctionRoute)
            .options(selectinload(AIFunctionRoute.primary_provider))  # ✅ 预加载provider
            .where(AIFunctionRoute.enabled == True)
            .order_by(AIFunctionRoute.function_type)
        )
        return list(result.scalars().all())

    async def create(self, route: AIFunctionRoute) -> AIFunctionRoute:
        """创建路由配置"""
        self.session.add(route)
        await self.session.flush()
        return route

    async def update(self, route: AIFunctionRoute) -> AIFunctionRoute:
        """更新路由配置"""
        await self.session.flush()
        return route

    async def parse_fallback_configs(self, route: AIFunctionRoute) -> List[Dict]:
        """解析fallback配置"""
        if not route.fallback_configs:
            return []
        try:
            return json.loads(route.fallback_configs)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse fallback_configs for {route.function_type}")
            return []


class AIFunctionCallLogRepository:
    """AI调用日志Repository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, log: AIFunctionCallLog) -> AIFunctionCallLog:
        """创建调用日志"""
        self.session.add(log)
        await self.session.flush()
        return log

    async def get_recent_logs(
        self,
        function_type: Optional[str] = None,
        limit: int = 100
    ) -> List[AIFunctionCallLog]:
        """获取最近的调用日志"""
        query = select(AIFunctionCallLog).order_by(AIFunctionCallLog.created_at.desc())
        
        if function_type:
            query = query.where(AIFunctionCallLog.function_type == function_type)
        
        query = query.limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_stats(
        self,
        function_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """
        获取统计信息

        ✅ 修复：实现真实的统计查询
        """
        from sqlalchemy import func, case
        from datetime import datetime

        # 构建基础查询
        query = select(AIFunctionCallLog)

        # 添加过滤条件
        if function_type:
            query = query.where(AIFunctionCallLog.function_type == function_type)
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            query = query.where(AIFunctionCallLog.created_at >= start_dt)
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            query = query.where(AIFunctionCallLog.created_at <= end_dt)

        # 执行查询
        result = await self.session.execute(query)
        logs = result.scalars().all()

        if not logs:
            return {
                "total_calls": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0,
                "total_cost_usd": 0.0,
                "by_function": {},
                "by_provider": {}
            }

        # 计算总体统计
        total_calls = len(logs)
        success_count = sum(1 for log in logs if log.status == "success")
        success_rate = (success_count / total_calls * 100) if total_calls > 0 else 0.0

        durations = [log.duration_ms for log in logs if log.duration_ms is not None]
        avg_duration_ms = int(sum(durations) / len(durations)) if durations else 0

        # 计算成本（简化版，实际应该从provider获取费率）
        total_cost_usd = 0.0

        # 按功能分组统计
        by_function = {}
        for log in logs:
            if log.function_type not in by_function:
                by_function[log.function_type] = {
                    "total": 0,
                    "success": 0,
                    "failed": 0
                }
            by_function[log.function_type]["total"] += 1
            if log.status == "success":
                by_function[log.function_type]["success"] += 1
            else:
                by_function[log.function_type]["failed"] += 1

        # 按供应商分组统计
        by_provider = {}
        for log in logs:
            if log.provider_id:
                if log.provider_id not in by_provider:
                    by_provider[log.provider_id] = {
                        "total": 0,
                        "success": 0,
                        "failed": 0
                    }
                by_provider[log.provider_id]["total"] += 1
                if log.status == "success":
                    by_provider[log.provider_id]["success"] += 1
                else:
                    by_provider[log.provider_id]["failed"] += 1

        return {
            "total_calls": total_calls,
            "success_rate": round(success_rate, 2),
            "avg_duration_ms": avg_duration_ms,
            "total_cost_usd": round(total_cost_usd, 4),
            "by_function": by_function,
            "by_provider": by_provider
        }

