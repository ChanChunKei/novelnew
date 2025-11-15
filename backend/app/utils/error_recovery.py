"""
错误恢复和异常处理工具
"""
import logging
from typing import Dict, Any, Optional, List
import json
import re

logger = logging.getLogger(__name__)


class ContentFormatError(Exception):
    """内容格式错误异常"""
    pass


class AgentResponseError(Exception):
    """Agent响应错误异常"""
    pass


class PlannerFormatDetector:
    """Planner格式检测器"""
    
    @staticmethod
    def detect_planner_format(content: str, check_length: int = 1000) -> tuple[bool, int, List[str]]:
        """检测是否为Planner格式"""
        planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
        matched = []
        
        check_text = content[:check_length].lower()
        
        for kw in planner_keywords:
            patterns = [
                f'{kw}:',
                f'"{kw}":',
                f"'{kw}':",
                f'**{kw}**',
                f'__{kw}__',
                f'## {kw}',
                f'### {kw}',
                f'# {kw}',
            ]
            
            for pattern in patterns:
                if pattern.lower() in check_text:
                    matched.append(f"{kw} ({pattern})")
                    break
        
        suspicious_count = len(matched)
        is_planner = suspicious_count >= 2
        
        return is_planner, suspicious_count, matched


class ContentNormalizer:
    """内容格式标准化工具"""
    
    @staticmethod
    def normalize_writer_content(content: str) -> str:
        """标准化Writer输出的内容"""
        if not content:
            return content
            
        cleaned = content
        
        # 处理转义字符
        cleaned = cleaned.replace('\\n', '\n')
        cleaned = cleaned.replace('\\"', '"')
        cleaned = cleaned.replace('\\t', '\t')
        cleaned = cleaned.replace('\\\\', '\\')
        
        # 修复3Agent模式的格式问题
        # 修复行尾孤立的反斜杠（如 "## 标题\" → "## 标题"）
        cleaned = re.sub(r'\\\s*$', '', cleaned, flags=re.MULTILINE)
        # 修复纯反斜杠行（如 "\" → ""）
        cleaned = re.sub(r'^\s*\\\s*$', '', cleaned, flags=re.MULTILINE)
        # 修复反斜杠+换行的组合
        cleaned = cleaned.replace('\\n', '\n')
        
        # 清理多余的空行（连续3个以上空行合并为2个）
        cleaned = re.sub(r'\n{4,}', '\n\n\n', cleaned)
        
        return cleaned.strip()
    
    @staticmethod 
    def validate_writer_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """验证并修复Writer响应格式"""
        if not isinstance(response, dict):
            raise AgentResponseError(f"Writer返回的不是JSON对象: {type(response)}")
            
        # 检查是否是Planner格式的误返
        if "analysis" in response and "plan" in response:
            is_planner, count, matched = PlannerFormatDetector.detect_planner_format(str(response))
            if is_planner:
                logger.warning(f"⚠️ Writer返回了Planner格式，检测到{count}个关键词: {matched}")
                raise ContentFormatError("Writer返回了Planner格式而非章节内容")
        
        # 确保包含full_content字段
        if "full_content" not in response:
            raise AgentResponseError("Writer响应缺少full_content字段")
            
        # 标准化内容
        if response["full_content"]:
            response["full_content"] = ContentNormalizer.normalize_writer_content(response["full_content"])
            
        return response


class ErrorRecoveryManager:
    """错误恢复管理器"""
    
    @staticmethod
    async def handle_writer_error(
        error: Exception, 
        round_num: int, 
        max_rounds: int,
        context: str
    ) -> Dict[str, Any]:
        """处理Writer错误，提供恢复策略"""
        
        if isinstance(error, ContentFormatError):
            if round_num < max_rounds - 1:
                logger.warning(f"第{round_num + 1}轮Writer返回错误格式，将重试第{round_num + 2}轮")
                return {"should_retry": True, "error_type": "format_error"}
            else:
                logger.error(f"Writer在{max_rounds}轮后仍返回错误格式")
                return {
                    "should_retry": False, 
                    "fallback_response": {
                        "full_content": "生成失败：Writer多次返回错误格式",
                        "writing_notes": "系统错误，需要人工介入"
                    }
                }
                
        elif isinstance(error, AgentResponseError):
            if round_num < max_rounds - 1:
                logger.warning(f"第{round_num + 1}轮Writer响应错误: {error}，将重试")
                return {"should_retry": True, "error_type": "response_error"}
            else:
                return {
                    "should_retry": False,
                    "fallback_response": {
                        "full_content": f"生成失败：{str(error)}",
                        "writing_notes": "响应格式错误，需要检查prompt或模型设置"
                    }
                }
                
        else:
            logger.error(f"Writer未知错误: {error}", exc_info=True)
            return {
                "should_retry": False,
                "fallback_response": {
                    "full_content": "生成失败：系统异常",
                    "writing_notes": f"系统错误: {str(error)}"
                }
            }
    
    @staticmethod
    def create_error_summary(errors: List[Dict[str, Any]]) -> str:
        """创建错误汇总报告"""
        if not errors:
            return "无错误"
            
        error_types = {}
        for error in errors:
            error_type = error.get("type", "unknown")
            if error_type not in error_types:
                error_types[error_type] = 0
            error_types[error_type] += 1
            
        summary_parts = []
        for error_type, count in error_types.items():
            summary_parts.append(f"{error_type}: {count}次")
            
        return f"错误统计 - " + ", ".join(summary_parts)


# 便捷函数
def normalize_content(content: str) -> str:
    """便捷的内容标准化函数"""
    return ContentNormalizer.normalize_writer_content(content)


def detect_format_issues(content: str) -> Dict[str, Any]:
    """检测内容格式问题"""
    issues = []
    
    # 检查是否有过多的转义字符
    if content.count('\\n') > len(content.split('\n')) * 0.1:
        issues.append("包含过多\\n转义字符")
    
    # 检查是否有行尾反斜杠问题
    if re.search(r'\\\s*$', content, re.MULTILINE):
        issues.append("检测到行尾孤立反斜杠")
        
    # 检查是否是Planner格式
    is_planner, count, matched = PlannerFormatDetector.detect_planner_format(content)
    if is_planner:
        issues.append(f"疑似Planner格式（{count}个关键词匹配）")
    
    return {
        "has_issues": len(issues) > 0,
        "issues": issues,
        "normalized_content": normalize_content(content) if issues else content
    }