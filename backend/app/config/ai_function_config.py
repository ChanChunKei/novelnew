"""
AI功能到模型的映射配置

支持不同的AI功能使用不同的API提供商和模型
优先使用：硅基流动(SiliconFlow) 和 Gemini
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class AIFunctionType(str, Enum):
    """AI功能类型枚举"""
    # F01: 概念对话
    CONCEPT_DIALOGUE = "concept_dialogue"
    
    # F02: 蓝图生成
    BLUEPRINT_GENERATION = "blueprint_generation"
    
    # F03: 批量大纲生成
    OUTLINE_GENERATION = "outline_generation"
    
    # F04: 章节正文生成
    CHAPTER_CONTENT_WRITING = "chapter_content_writing"
    
    # F05: 章节摘要提取
    SUMMARY_EXTRACTION = "summary_extraction"
    
    # F06: 基础分析
    BASIC_ANALYSIS = "basic_analysis"
    
    # F07: 增强分析
    ENHANCED_ANALYSIS = "enhanced_analysis"
    
    # F08: 角色追踪
    CHARACTER_TRACKING = "character_tracking"
    
    # F09: 世界观扩展
    WORLDVIEW_EXPANSION = "worldview_expansion"
    
    # F10: 卷名生成
    VOLUME_NAMING = "volume_naming"

    # F11: AI去味
    AI_DENOISING = "ai_denoising"


class ProviderConfig(BaseModel):
    """API提供商配置"""
    provider: str  # "siliconflow" / "gemini" / "openai" / "deepseek"
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None  # 如果为None，则从环境变量或系统配置读取


class FunctionRouteConfig(BaseModel):
    """功能路由配置"""
    function_type: AIFunctionType
    primary: ProviderConfig  # 主模型
    fallbacks: List[ProviderConfig] = Field(default_factory=list)  # ✅ 修复：使用default_factory避免共享可变状态
    temperature: float = 0.7
    timeout: float = 300.0
    max_retries: int = 2
    async_mode: bool = False  # 是否异步执行
    required: bool = True  # 是否必须成功（False则失败时返回默认值）


# ==================== AI功能配置 ====================

AI_FUNCTION_ROUTES: Dict[AIFunctionType, FunctionRouteConfig] = {
    # F01: 概念对话 - 使用DeepSeek
    AIFunctionType.CONCEPT_DIALOGUE: FunctionRouteConfig(
        function_type=AIFunctionType.CONCEPT_DIALOGUE,
        primary=ProviderConfig(
            provider="siliconflow",
            model="deepseek-ai/DeepSeek-R1",
        ),
        fallbacks=[],  # 暂时移除fallback
        temperature=0.8,
        timeout=240.0,
        max_retries=2,
        required=True,
    ),

    # F02: 蓝图生成 - 使用DeepSeek
    AIFunctionType.BLUEPRINT_GENERATION: FunctionRouteConfig(
        function_type=AIFunctionType.BLUEPRINT_GENERATION,
        primary=ProviderConfig(
            provider="siliconflow",
            model="deepseek-ai/DeepSeek-R1",
        ),
        fallbacks=[],  # 暂时移除fallback
        temperature=0.8,
        timeout=300.0,
        max_retries=2,
        required=True,
    ),

    # F03: 批量大纲生成 - 使用DeepSeek
    AIFunctionType.OUTLINE_GENERATION: FunctionRouteConfig(
        function_type=AIFunctionType.OUTLINE_GENERATION,
        primary=ProviderConfig(
            provider="siliconflow",
            model="deepseek-ai/DeepSeek-R1",
        ),
        fallbacks=[],  # 暂时移除fallback
        temperature=0.8,
        timeout=360.0,
        max_retries=2,
        required=True,
    ),

    # F04: 章节正文生成 - 使用DeepSeek
    AIFunctionType.CHAPTER_CONTENT_WRITING: FunctionRouteConfig(
        function_type=AIFunctionType.CHAPTER_CONTENT_WRITING,
        primary=ProviderConfig(
            provider="siliconflow",
            model="deepseek-ai/DeepSeek-R1",
        ),
        fallbacks=[],  # 暂时移除fallback
        temperature=0.9,
        timeout=600.0,
        max_retries=3,
        required=True,
    ),

    # F05: 章节摘要提取 - 使用DeepSeek
    AIFunctionType.SUMMARY_EXTRACTION: FunctionRouteConfig(
        function_type=AIFunctionType.SUMMARY_EXTRACTION,
        primary=ProviderConfig(
            provider="siliconflow",
            model="deepseek-ai/DeepSeek-R1",
        ),
        fallbacks=[],  # 暂时移除fallback
        temperature=0.15,
        timeout=180.0,
        max_retries=2,
        required=True,
    ),

    # F06: 基础分析 - 使用DeepSeek
    AIFunctionType.BASIC_ANALYSIS: FunctionRouteConfig(
        function_type=AIFunctionType.BASIC_ANALYSIS,
        primary=ProviderConfig(
            provider="siliconflow",
            model="deepseek-ai/DeepSeek-R1",
        ),
        fallbacks=[],  # 暂时移除fallback
        temperature=0.3,
        timeout=180.0,
        max_retries=2,
        required=True,
    ),

    # F07: 增强分析 - 使用DeepSeek
    AIFunctionType.ENHANCED_ANALYSIS: FunctionRouteConfig(
        function_type=AIFunctionType.ENHANCED_ANALYSIS,
        primary=ProviderConfig(
            provider="siliconflow",
            model="deepseek-ai/DeepSeek-R1",
        ),
        fallbacks=[],  # 暂时移除fallback
        temperature=0.5,
        timeout=600.0,
        max_retries=1,
        async_mode=True,
        required=False,  # 失败可跳过
    ),

    # F08: 角色追踪 - 使用DeepSeek
    AIFunctionType.CHARACTER_TRACKING: FunctionRouteConfig(
        function_type=AIFunctionType.CHARACTER_TRACKING,
        primary=ProviderConfig(
            provider="siliconflow",
            model="deepseek-ai/DeepSeek-R1",
        ),
        fallbacks=[],  # 暂时移除fallback
        temperature=0.3,
        timeout=300.0,
        max_retries=1,
        async_mode=True,
        required=False,
    ),

    # F09: 世界观扩展 - 使用DeepSeek
    AIFunctionType.WORLDVIEW_EXPANSION: FunctionRouteConfig(
        function_type=AIFunctionType.WORLDVIEW_EXPANSION,
        primary=ProviderConfig(
            provider="siliconflow",
            model="deepseek-ai/DeepSeek-R1",
        ),
        fallbacks=[],  # 暂时移除fallback
        temperature=0.7,
        timeout=300.0,
        max_retries=1,
        async_mode=True,
        required=False,
    ),

    # F10: 卷名生成 - 使用DeepSeek
    AIFunctionType.VOLUME_NAMING: FunctionRouteConfig(
        function_type=AIFunctionType.VOLUME_NAMING,
        primary=ProviderConfig(
            provider="siliconflow",
            model="deepseek-ai/DeepSeek-R1",
        ),
        fallbacks=[],  # 暂时移除fallback
        temperature=0.7,
        timeout=30.0,
        max_retries=1,
        required=False,  # 失败返回默认卷名
    ),

    # F11: AI去味 - 使用Gemini（擅长自然语言处理）
    AIFunctionType.AI_DENOISING: FunctionRouteConfig(
        function_type=AIFunctionType.AI_DENOISING,
        primary=ProviderConfig(
            provider="gemini",
            model="gemini-2.0-flash-exp",
        ),
        fallbacks=[
            ProviderConfig(
                provider="siliconflow",
                model="deepseek-ai/DeepSeek-R1",
            ),
        ],
        temperature=0.8,  # 稍高的温度，增加自然度
        timeout=60.0,
        max_retries=2,
        required=False,  # 失败返回原文
    ),
}


# ==================== Provider 配置 ====================

PROVIDER_CONFIGS = {
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "env_key": "SILICONFLOW_API_KEY",  # 从环境变量读取
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_key": "GEMINI_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
    },
}


def get_function_config(function_type: AIFunctionType) -> FunctionRouteConfig:
    """获取指定功能的配置"""
    return AI_FUNCTION_ROUTES.get(function_type)


def get_provider_base_url(provider: str) -> str:
    """获取provider的base_url"""
    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        raise ValueError(f"未知的provider: {provider}")
    return config["base_url"]


def get_provider_env_key(provider: str) -> str:
    """获取provider的环境变量key"""
    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        raise ValueError(f"未知的provider: {provider}")
    return config["env_key"]

