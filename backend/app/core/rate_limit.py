"""
速率限制配置

使用slowapi实现API速率限制
"""
from slowapi import Limiter
from slowapi.util import get_remote_address


# 创建限流器
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],  # 默认每分钟100次
    storage_uri="memory://",  # 使用内存存储，生产环境建议使用Redis
)


def get_limiter():
    """获取限流器实例"""
    return limiter

