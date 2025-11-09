"""
AI调用日志清理任务

定期清理旧的AI调用日志，防止数据库膨胀
"""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import AsyncSessionLocal
from ..models.ai_routing import AIFunctionCallLog

logger = logging.getLogger(__name__)


async def cleanup_old_ai_logs(days: int = 30):
    """
    清理指定天数之前的AI调用日志
    
    Args:
        days: 保留最近多少天的日志，默认30天
    """
    logger.info(f"开始清理 {days} 天前的AI调用日志...")
    
    async with AsyncSessionLocal() as session:
        try:
            # 计算截止日期
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # 删除旧日志
            result = await session.execute(
                delete(AIFunctionCallLog)
                .where(AIFunctionCallLog.created_at < cutoff_date)
            )
            
            deleted_count = result.rowcount
            await session.commit()
            
            logger.info(f"✅ 成功清理 {deleted_count} 条旧日志（{days}天前）")
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ 清理日志失败: {e}")
            await session.rollback()
            raise


async def cleanup_ai_logs_by_status(status: str = "failed", days: int = 7):
    """
    清理指定状态的旧日志
    
    Args:
        status: 日志状态（success/failed）
        days: 保留最近多少天的日志
    """
    logger.info(f"开始清理 {days} 天前状态为 {status} 的日志...")
    
    async with AsyncSessionLocal() as session:
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            result = await session.execute(
                delete(AIFunctionCallLog)
                .where(
                    AIFunctionCallLog.created_at < cutoff_date,
                    AIFunctionCallLog.status == status
                )
            )
            
            deleted_count = result.rowcount
            await session.commit()
            
            logger.info(f"✅ 成功清理 {deleted_count} 条 {status} 状态的旧日志")
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ 清理日志失败: {e}")
            await session.rollback()
            raise


async def get_log_statistics():
    """获取日志统计信息"""
    from sqlalchemy import func, select
    
    async with AsyncSessionLocal() as session:
        # 总日志数
        total_result = await session.execute(
            select(func.count(AIFunctionCallLog.id))
        )
        total_count = total_result.scalar()
        
        # 按状态统计
        status_result = await session.execute(
            select(
                AIFunctionCallLog.status,
                func.count(AIFunctionCallLog.id)
            )
            .group_by(AIFunctionCallLog.status)
        )
        status_stats = dict(status_result.all())
        
        # 最早和最新的日志
        date_result = await session.execute(
            select(
                func.min(AIFunctionCallLog.created_at),
                func.max(AIFunctionCallLog.created_at)
            )
        )
        min_date, max_date = date_result.one()
        
        return {
            "total_count": total_count,
            "status_stats": status_stats,
            "oldest_log": min_date,
            "newest_log": max_date,
        }


if __name__ == "__main__":
    # 测试清理任务
    async def main():
        print("=" * 60)
        print("AI日志清理任务")
        print("=" * 60)
        print()
        
        # 显示统计信息
        stats = await get_log_statistics()
        print(f"总日志数: {stats['total_count']}")
        print(f"状态统计: {stats['status_stats']}")
        print(f"最早日志: {stats['oldest_log']}")
        print(f"最新日志: {stats['newest_log']}")
        print()
        
        # 清理30天前的日志
        deleted = await cleanup_old_ai_logs(days=30)
        print(f"清理了 {deleted} 条旧日志")
        print()
        
        # 显示清理后的统计
        stats = await get_log_statistics()
        print(f"清理后总日志数: {stats['total_count']}")
    
    asyncio.run(main())

