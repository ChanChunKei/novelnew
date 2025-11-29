"""FastAPI 应用入口，负责装配路由、依赖与生命周期管理。"""

import logging
from logging.config import dictConfig
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .db.init_db import init_db
from .services.prompt_service import PromptService
from .db.session import AsyncSessionLocal
from .api.routers import api_router


dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            }
        },
        "loggers": {
            "backend": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "app": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "backend.app": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "backend.api": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "backend.services": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
        },
        "root": {
            "level": "WARNING",
            "handlers": ["console"],
        },
    }
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时初始化数据库，并预热提示词缓存
    await init_db()

    # ✅ 修复：为 SQLite 启用 WAL 模式以提升并发性能
    from .db.session import init_sqlite_wal
    await init_sqlite_wal()

    async with AsyncSessionLocal() as session:
        prompt_service = PromptService(session)
        await prompt_service.preload()

    # ✅ 新增：恢复运行中的后台任务（服务器重启后自动恢复）
    async with AsyncSessionLocal() as session:
        from .services.auto_generator_service import AutoGeneratorService
        recovered_count = await AutoGeneratorService.recover_running_tasks(session)
        if recovered_count > 0:
            logging.getLogger(__name__).info(f"✅ 自动恢复了 {recovered_count} 个运行中的任务")

    # ✅ 修复：启动验证码缓存清理任务
    from .services.auth_service import start_cleanup_task
    start_cleanup_task()

    # ✅ 新增：初始化定时生成器调度器
    from .services.scheduled_generator_service import ScheduledGeneratorService
    scheduler = ScheduledGeneratorService.get_scheduler()
    logging.getLogger(__name__).info("✅ 定时生成器调度器已启动")

    # TODO: 恢复已启用的定时任务（从数据库中加载）
    async with AsyncSessionLocal() as session:
        from .models.scheduled_generator import ScheduledGeneratorConfig
        from sqlalchemy import select
        result = await session.execute(
            select(ScheduledGeneratorConfig).where(ScheduledGeneratorConfig.enabled == True)
        )
        enabled_configs = list(result.scalars().all())
        for config in enabled_configs:
            await ScheduledGeneratorService._register_scheduled_job(session, config)
            logging.getLogger(__name__).info(f"✅ 恢复定时任务: {config.name} (ID: {config.id})")

    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置 - 安全设置，仅允许指定域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",    # 开发环境前端
        "http://localhost:5173",    # Vite开发服务器 
        "http://127.0.0.1:3000",    # 本地开发
        "http://127.0.0.1:5173",    # 本地开发
        # 生产环境需要添加实际域名
        # "https://your-domain.com", 
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router)


# 健康检查接口（用于 Docker 健康检查和监控）
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    """健康检查接口，返回应用状态。"""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
    }
