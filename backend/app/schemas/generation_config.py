"""
生成配置Schema - 细粒度控制

支持：
- 增强功能开关
- 动态阈值
- 成本控制
"""
from typing import Optional
from pydantic import BaseModel, Field


class EnhancedFeatures(BaseModel):
    """增强功能开关"""
    
    character_tracking: bool = Field(
        default=True,
        description="角色追踪：追踪角色状态变化"
    )
    
    world_expansion: bool = Field(
        default=True,
        description="世界观扩展：自动扩展世界设定"
    )
    
    foreshadowing: bool = Field(
        default=True,
        description="伏笔识别：识别并记录伏笔"
    )
    
    new_character_detection: bool = Field(
        default=True,
        description="新角色检测：自动添加新出现的角色"
    )


class DynamicThreshold(BaseModel):
    """动态阈值配置"""
    
    min_chapter_length: int = Field(
        default=1000,
        description="最小章节长度（字数），低于此值不执行增强分析"
    )
    
    max_chapter_length: int = Field(
        default=8000,
        description="最大章节长度（字数），超过此值会截断"
    )
    
    plot_intensity_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="剧情强度阈值（0-1），低于此值不执行增强分析（暂未实现）"
    )
    
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="置信度阈值，低于此值的结果会标记为低置信度"
    )


class CostTracking(BaseModel):
    """成本追踪配置"""
    
    enabled: bool = Field(
        default=True,
        description="是否启用成本追踪"
    )
    
    show_in_ui: bool = Field(
        default=True,
        description="是否在UI中显示成本信息"
    )
    
    alert_threshold_usd: Optional[float] = Field(
        default=None,
        description="成本告警阈值（美元），超过此值会发出告警"
    )


class GenerationConfig(BaseModel):
    """
    生成配置
    
    用于自动生成器任务的详细配置
    """
    
    # 基础配置
    generation_mode: str = Field(
        default="basic",
        description="生成模式：basic（基础）或 enhanced（增强）"
    )
    
    bug_fix_mode: str = Field(
        default="fixed",
        description="Bug修复模式：original（原始）或 fixed（修复）"
    )
    
    # 增强功能配置
    enhanced_features: EnhancedFeatures = Field(
        default_factory=EnhancedFeatures,
        description="增强功能开关"
    )
    
    # 动态阈值配置
    dynamic_threshold: DynamicThreshold = Field(
        default_factory=DynamicThreshold,
        description="动态阈值配置"
    )
    
    # 成本追踪配置
    cost_tracking: CostTracking = Field(
        default_factory=CostTracking,
        description="成本追踪配置"
    )
    
    # LLM配置
    model_name: Optional[str] = Field(
        default=None,
        description="指定使用的模型名称"
    )
    
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="生成温度"
    )
    
    # 版本配置
    num_versions: int = Field(
        default=2,
        ge=1,
        le=5,
        description="每章生成的版本数"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "generation_mode": "enhanced",
                "bug_fix_mode": "fixed",
                "enhanced_features": {
                    "character_tracking": True,
                    "world_expansion": True,
                    "foreshadowing": True,
                    "new_character_detection": True
                },
                "dynamic_threshold": {
                    "min_chapter_length": 2000,
                    "max_chapter_length": 8000,
                    "plot_intensity_threshold": 0.5,
                    "confidence_threshold": 0.7
                },
                "cost_tracking": {
                    "enabled": True,
                    "show_in_ui": True,
                    "alert_threshold_usd": 10.0
                },
                "model_name": "gpt-3.5-turbo",
                "temperature": 0.7,
                "num_versions": 2
            }
        }


def get_default_config(mode: str = "basic") -> dict:
    """获取默认配置"""
    config = GenerationConfig(generation_mode=mode)
    return config.model_dump()


def should_run_enhanced_analysis(
    config: dict,
    chapter_length: int
) -> bool:
    """
    判断是否应该运行增强分析
    
    Args:
        config: 生成配置字典
        chapter_length: 章节长度（字数）
    
    Returns:
        是否应该运行增强分析
    """
    # 基础模式直接返回False
    if config.get("generation_mode") != "enhanced":
        return False
    
    # 检查动态阈值
    threshold = config.get("dynamic_threshold", {})
    min_length = threshold.get("min_chapter_length", 1000)
    
    if chapter_length < min_length:
        return False
    
    # 未来可以添加更多条件判断
    # 例如：剧情强度、角色数量等
    
    return True


def get_enabled_features(config: dict) -> dict:
    """
    获取启用的增强功能
    
    Returns:
        {
            "character_tracking": True/False,
            "world_expansion": True/False,
            ...
        }
    """
    features = config.get("enhanced_features", {})
    return {
        "character_tracking": features.get("character_tracking", True),
        "world_expansion": features.get("world_expansion", True),
        "foreshadowing": features.get("foreshadowing", True),
        "new_character_detection": features.get("new_character_detection", True),
    }

