from typing import Optional, Union

from pydantic import BaseModel, HttpUrl, Field, field_validator


class LLMConfigBase(BaseModel):
    llm_provider_url: Optional[Union[HttpUrl, str]] = Field(default=None, description="自定义 LLM 服务地址")
    llm_provider_api_key: Optional[str] = Field(default=None, description="多个 LLM API Key，逗号分隔或JSON格式的路由配置")
    llm_provider_model: Optional[str] = Field(default=None, description="自定义模型名称")

    @field_validator('llm_provider_url', mode='before')
    @classmethod
    def validate_url(cls, v):
        """允许空字符串，将其转换为 None"""
        if v == '' or v is None:
            return None
        return v

    @field_validator('llm_provider_model', mode='before')
    @classmethod
    def validate_model(cls, v):
        """允许空字符串，将其转换为 None"""
        if v == '' or v is None:
            return None
        return v


class LLMConfigCreate(LLMConfigBase):
    """
    支持两种格式：
    1. 旧格式：llm_provider_url, llm_provider_api_key, llm_provider_model
    2. 新格式：llm_provider_api_key 为 JSON 字符串，包含 routes 和 functions
    """
    pass


class LLMConfigRead(LLMConfigBase):
    user_id: int

    class Config:
        from_attributes = True
