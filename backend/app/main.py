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

    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置，生产环境建议改为具体域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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
