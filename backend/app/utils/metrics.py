"""
Prometheus监控指标定义

用于追踪增强模式性能、成本和错误
"""
from prometheus_client import Counter, Histogram, Gauge, Summary
import time
from contextlib import contextmanager
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# ==================== AI路由系统指标 ====================

# AI调用总次数（按功能、provider、状态分类）
ai_calls_total = Counter(
    'ai_calls_total',
    'Total AI function calls',
    ['function', 'provider', 'status']
)

# AI调用耗时分布
ai_duration_seconds = Histogram(
    'ai_duration_seconds',
    'AI function call duration in seconds',
    ['function', 'provider'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600]
)

# AI调用成本统计
ai_cost_usd_total = Counter(
    'ai_cost_usd_total',
    'Total AI cost in USD',
    ['function', 'provider']
)

# Fallback次数统计
ai_fallback_total = Counter(
    'ai_fallback_total',
    'Total AI fallback occurrences',
    ['function', 'from_provider', 'to_provider']
)

# 错误类型统计
ai_error_total = Counter(
    'ai_error_total',
    'Total AI errors by type',
    ['function', 'provider', 'error_type']
)

# Token使用统计
ai_tokens_total = Counter(
    'ai_tokens_total',
    'Total tokens used',
    ['function', 'provider', 'token_type']  # token_type: input/output
)

# 当前运行中的AI调用
ai_calls_in_progress = Gauge(
    'ai_calls_in_progress',
    'Number of AI calls currently in progress',
    ['function']
)

# ==================== 增强模式指标 ====================

# 增强分析总次数（按状态和错误类型分类）
enhanced_analysis_total = Counter(
    'enhanced_analysis_total',
    'Total enhanced analysis attempts',
    ['status', 'error_type', 'mode']
)

# 增强分析耗时分布
enhanced_analysis_duration = Histogram(
    'enhanced_analysis_duration_seconds',
    'Enhanced analysis duration in seconds',
    ['mode', 'feature'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

# Token消耗统计
token_usage_total = Counter(
    'token_usage_total',
    'Total tokens consumed',
    ['mode', 'feature', 'model']
)

# 当前运行中的增强分析任务数
enhanced_analysis_in_progress = Gauge(
    'enhanced_analysis_in_progress',
    'Number of enhanced analysis tasks currently running'
)

# ==================== 章节生成指标 ====================

# 章节生成总次数
chapter_generation_total = Counter(
    'chapter_generation_total',
    'Total chapter generation attempts',
    ['status', 'mode']
)

# 章节生成耗时
chapter_generation_duration = Histogram(
    'chapter_generation_duration_seconds',
    'Chapter generation duration in seconds',
    ['mode'],
    buckets=[10, 30, 60, 120, 300, 600, 1200]
)

# ==================== 数据质量指标 ====================

# 角色匹配统计
character_match_total = Counter(
    'character_match_total',
    'Character matching attempts',
    ['match_type', 'success']
)

# JSON解析失败统计
json_parse_failures = Counter(
    'json_parse_failures_total',
    'JSON parsing failures',
    ['source', 'error_type']
)

# 世界观扩展统计
world_expansion_total = Counter(
    'world_expansion_total',
    'World setting expansions',
    ['category', 'confidence_level']
)

# ==================== 辅助函数 ====================

@contextmanager
def track_duration(metric: Histogram, **labels):
    """
    上下文管理器：自动追踪代码块执行时间
    
    用法:
        with track_duration(enhanced_analysis_duration, mode='enhanced', feature='character_tracking'):
            # 你的代码
            pass
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metric.labels(**labels).observe(duration)


@contextmanager
def track_in_progress(gauge: Gauge):
    """
    上下文管理器：追踪并发任务数
    
    用法:
        with track_in_progress(enhanced_analysis_in_progress):
            # 你的代码
            pass
    """
    gauge.inc()
    try:
        yield
    finally:
        gauge.dec()


def record_success(mode: str, feature: Optional[str] = None):
    """记录成功的增强分析"""
    enhanced_analysis_total.labels(
        status='success',
        error_type='none',
        mode=mode
    ).inc()
    logger.info(f"✅ {mode} 模式分析成功: {feature or 'all'}")


def record_failure(mode: str, error_type: str, error: Exception):
    """记录失败的增强分析"""
    enhanced_analysis_total.labels(
        status='failed',
        error_type=error_type,
        mode=mode
    ).inc()
    logger.error(f"❌ {mode} 模式分析失败 ({error_type}): {error}")


def record_token_usage(mode: str, feature: str, tokens: int, model: str = 'unknown'):
    """记录Token消耗"""
    token_usage_total.labels(
        mode=mode,
        feature=feature,
        model=model
    ).inc(tokens)
    logger.info(f"💰 Token消耗: {mode}/{feature} = {tokens} tokens ({model})")


def record_character_match(match_type: str, success: bool):
    """
    记录角色匹配结果
    
    match_type: 'exact', 'fuzzy', 'similarity', 'failed'
    """
    character_match_total.labels(
        match_type=match_type,
        success='true' if success else 'false'
    ).inc()


def record_json_parse_failure(source: str, error_type: str):
    """
    记录JSON解析失败
    
    source: 'super_analysis', 'outline_generation', etc.
    error_type: 'invalid_json', 'missing_field', 'type_error'
    """
    json_parse_failures.labels(
        source=source,
        error_type=error_type
    ).inc()
    logger.warning(f"⚠️ JSON解析失败: {source} - {error_type}")


def record_world_expansion(category: str, confidence: float):
    """
    记录世界观扩展
    
    category: 'location', 'faction', 'item', 'rule'
    confidence: 0.0 - 1.0
    """
    if confidence >= 0.9:
        level = 'high'
    elif confidence >= 0.7:
        level = 'medium'
    else:
        level = 'low'
    
    world_expansion_total.labels(
        category=category,
        confidence_level=level
    ).inc()


# ==================== 成本估算 ====================

class CostEstimator:
    """成本估算器"""
    
    # 价格配置（美元/1000 tokens）
    PRICING = {
        'gpt-4': {'input': 0.03, 'output': 0.06},
        'gpt-3.5-turbo': {'input': 0.001, 'output': 0.002},
        'claude-3-sonnet': {'input': 0.003, 'output': 0.015},
    }
    
    @classmethod
    def estimate_cost(cls, model: str, input_tokens: int, output_tokens: int) -> float:
        """估算成本（美元）"""
        if model not in cls.PRICING:
            logger.warning(f"未知模型 {model}，使用默认价格")
            model = 'gpt-3.5-turbo'
        
        pricing = cls.PRICING[model]
        cost = (input_tokens / 1000 * pricing['input'] + 
                output_tokens / 1000 * pricing['output'])
        return round(cost, 6)
    
    @classmethod
    def estimate_chapter_cost(cls, mode: str, model: str = 'gpt-3.5-turbo') -> dict:
        """估算单章成本"""
        if mode == 'basic':
            # 基础模式：2.5次调用
            # 大纲0.5次(1000 input, 500 output) + 内容2次(2000 input, 3000 output)
            input_tokens = 1000 * 0.5 + 2000 * 2
            output_tokens = 500 * 0.5 + 3000 * 2
        else:  # enhanced
            # 增强模式：3.6次调用
            # 基础2.5次 + 超级分析1.1次(5000 input, 2000 output)
            input_tokens = 1000 * 0.5 + 2000 * 2 + 5000 * 1.1
            output_tokens = 500 * 0.5 + 3000 * 2 + 2000 * 1.1
        
        cost = cls.estimate_cost(model, int(input_tokens), int(output_tokens))
        
        return {
            'mode': mode,
            'model': model,
            'input_tokens': int(input_tokens),
            'output_tokens': int(output_tokens),
            'total_tokens': int(input_tokens + output_tokens),
            'cost_usd': cost,
            'cost_cny': round(cost * 7.2, 4)  # 假设汇率7.2
        }

