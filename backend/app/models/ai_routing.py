"""
AI路由系统数据模型
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, DECIMAL, ForeignKey
from sqlalchemy.orm import relationship

from ..db.base import Base


class AIProvider(Base):
    """AI提供商模型"""
    __tablename__ = "ai_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(200), nullable=False)
    base_url = Column(String(500), nullable=False)
    api_key_env = Column(String(100))
    status = Column(String(20), default="active")
    priority = Column(Integer, default=100)
    max_concurrent = Column(Integer, default=10)
    rate_limit_per_minute = Column(Integer, default=60)
    timeout_seconds = Column(Integer, default=300)
    cost_per_1k_tokens = Column(DECIMAL(10, 6))
    provider_metadata = Column(Text)  # 重命名避免与SQLAlchemy保留字冲突
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    function_routes = relationship("AIFunctionRoute", back_populates="primary_provider")
    call_logs = relationship("AIFunctionCallLog", back_populates="provider")


class AIFunctionRoute(Base):
    """AI功能路由配置模型"""
    __tablename__ = "ai_function_routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    function_type = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text)
    
    # 主模型配置
    primary_provider_id = Column(Integer, ForeignKey("ai_providers.id"), nullable=False)
    primary_model = Column(String(200), nullable=False)
    
    # 备用模型配置（JSON）
    fallback_configs = Column(Text)
    
    # 调用参数
    temperature = Column(DECIMAL(3, 2), default=0.7)
    timeout_seconds = Column(Integer, default=300)
    max_retries = Column(Integer, default=2)
    
    # 功能属性
    async_mode = Column(Boolean, default=False)
    required = Column(Boolean, default=True)
    
    # 配额和限制
    daily_quota = Column(Integer)
    cost_limit_daily = Column(DECIMAL(10, 2))
    
    # 元数据
    version = Column(Integer, default=1)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    primary_provider = relationship("AIProvider", back_populates="function_routes")


class AIFunctionCallLog(Base):
    """AI调用日志模型"""
    __tablename__ = "ai_function_call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 调用信息
    function_type = Column(String(100), nullable=False)
    provider_id = Column(Integer, ForeignKey("ai_providers.id"))
    model = Column(String(200))
    
    # 用户和项目
    user_id = Column(Integer)
    project_id = Column(String(100))
    
    # 调用参数
    temperature = Column(DECIMAL(3, 2))
    timeout_seconds = Column(Integer)
    
    # 调用结果
    status = Column(String(20), nullable=False)
    is_fallback = Column(Boolean, default=False)
    fallback_count = Column(Integer, default=0)
    
    # 性能指标
    duration_ms = Column(Integer)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    total_tokens = Column(Integer)
    
    # 成本
    cost_usd = Column(DECIMAL(10, 6))
    
    # 错误信息
    error_type = Column(String(100))
    error_message = Column(Text)

    # 元数据
    finish_reason = Column(String(50))
    call_metadata = Column(Text)  # 重命名避免与SQLAlchemy保留字冲突

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    provider = relationship("AIProvider", back_populates="call_logs")


class AIConfigHistory(Base):
    """配置变更历史模型"""
    __tablename__ = "ai_config_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String(100), nullable=False)
    record_id = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    changed_by = Column(Integer)
    change_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

