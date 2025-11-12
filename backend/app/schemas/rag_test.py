"""RAG 测试相关的 Schema"""

from typing import Optional
from pydantic import BaseModel


class GeminiRAGTestResult(BaseModel):
    """Gemini RAG 测试结果"""

    success: bool
    message: str
    api_key_configured: bool
    api_key_valid: bool
    provider: str
    corpus_accessible: Optional[bool] = None
    error_detail: Optional[str] = None


class GeminiRAGTestRequest(BaseModel):
    """Gemini RAG 测试请求"""

    test_project_id: Optional[str] = None  # 可选：测试指定项目的Corpus访问
