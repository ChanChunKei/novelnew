from collections.abc import AsyncGenerator
import asyncio
import logging
from functools import wraps
from typing import TypeVar, Callable, Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import OperationalError, IntegrityError

from ..core.config import settings

logger = logging.getLogger(__name__)

# 根据不同数据库驱动调整连接池参数，确保在多数据库环境下表现稳定
engine_kwargs = {"echo": settings.debug}
if settings.is_sqlite_backend:
    # SQLite 场景下启用 WAL 模式并放宽线程检查，提升并发性能
    engine_kwargs.update(
        pool_pre_ping=False,
        connect_args={
            "check_same_thread": False,
            "timeout": 60.0,  # 增加超时时间到60秒（极端并发场景）
        },
        poolclass=NullPool,
    )
else:
    # MySQL 场景保持健康检查与连接复用，适用于生产环境的长连接需求
    engine_kwargs.update(pool_pre_ping=True, pool_recycle=3600)

engine = create_async_engine(settings.sqlalchemy_database_uri, **engine_kwargs)

# 统一的 Session 工厂，禁用 expire_on_commit 方便返回模型对象
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def init_sqlite_wal():
    """为 SQLite 启用 WAL 模式以提升并发性能"""
    if settings.is_sqlite_backend:
        try:
            from sqlalchemy import text
            async with engine.begin() as conn:
                await conn.execute(text("PRAGMA journal_mode=WAL"))
                await conn.execute(text("PRAGMA busy_timeout=60000"))  # 60秒超时（极端并发）
                await conn.execute(text("PRAGMA wal_autocheckpoint=1000"))  # WAL优化
                logger.info("SQLite WAL mode enabled for better concurrency")
        except Exception as e:
            logger.warning(f"Failed to enable WAL mode: {e}")


T = TypeVar('T')


def retry_on_db_lock(max_retries: int = 10, initial_delay: float = 0.2):
    """
    数据库操作重试装饰器，处理 SQLite 锁冲突

    极端并发场景优化：支持几十个任务同时运行

    Args:
        max_retries: 最大重试次数（默认10次）
        initial_delay: 初始延迟（秒），每次重试会指数增长
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            last_error = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except OperationalError as e:
                    error_msg = str(e).lower()
                    # 只重试数据库锁相关的错误
                    if "locked" in error_msg or "busy" in error_msg:
                        last_error = e
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Database locked, retry {attempt + 1}/{max_retries} "
                                f"after {delay:.2f}s: {func.__name__}"
                            )
                            await asyncio.sleep(delay)
                            delay *= 2  # 指数退避
                            continue
                    # 其他 OperationalError 不重试
                    raise
                except IntegrityError:
                    # 唯一约束冲突不重试（说明数据已存在）
                    raise

            # 所有重试都失败
            logger.error(f"Database operation failed after {max_retries} retries: {func.__name__}")
            raise last_error

        return wrapper
    return decorator


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖项：提供一个作用域内共享的数据库会话。"""
    async with AsyncSessionLocal() as session:
        yield session
