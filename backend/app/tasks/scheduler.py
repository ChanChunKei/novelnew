"""
定时任务调度器

使用APScheduler管理定时任务
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .cleanup_ai_logs import cleanup_old_ai_logs, cleanup_ai_logs_by_status

logger = logging.getLogger(__name__)

# 创建调度器
scheduler = AsyncIOScheduler()


def setup_scheduled_tasks():
    """设置定时任务"""
    
    # 每天凌晨2点清理30天前的日志
    scheduler.add_job(
        cleanup_old_ai_logs,
        CronTrigger(hour=2, minute=0),
        args=[30],
        id="cleanup_old_logs",
        name="清理30天前的AI调用日志",
        replace_existing=True,
    )
    
    # 每天凌晨3点清理7天前的失败日志
    scheduler.add_job(
        cleanup_ai_logs_by_status,
        CronTrigger(hour=3, minute=0),
        args=["failed", 7],
        id="cleanup_failed_logs",
        name="清理7天前的失败日志",
        replace_existing=True,
    )
    
    logger.info("✅ 定时任务已设置")


def start_scheduler():
    """启动调度器"""
    setup_scheduled_tasks()
    scheduler.start()
    logger.info("✅ 定时任务调度器已启动")


def shutdown_scheduler():
    """关闭调度器"""
    scheduler.shutdown()
    logger.info("✅ 定时任务调度器已关闭")

