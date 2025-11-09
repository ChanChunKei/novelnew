# -*- coding: utf-8 -*-
"""OpenAI 兼容型 LLM 工具封装，保持与旧项目一致的接口体验。"""

import os
from dataclasses import asdict, dataclass
from typing import AsyncGenerator, Dict, List, Optional

from openai import AsyncOpenAI


@dataclass
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


class LLMClient:
    """异步流式调用封装，兼容 OpenAI SDK。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("缺少 OPENAI_API_KEY 配置，请在数据库或环境变量中补全。")

        self._client = AsyncOpenAI(api_key=key, base_url=base_url or os.environ.get("OPENAI_API_BASE"))

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        response_format: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: int = 120,
        **kwargs,
    ) -> AsyncGenerator[Dict[str, str], None]:
        payload = {
            "model": model or os.environ.get("MODEL", "gpt-3.5-turbo"),
            "messages": [msg.to_dict() for msg in messages],
            "stream": True,
            "timeout": timeout,
            **kwargs,
        }
        if response_format:
            payload["response_format"] = {"type": response_format}
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        async def _yield_final(resp_obj):
            # 非流式响应的统一输出
            if getattr(resp_obj, "choices", None):
                choice = resp_obj.choices[0]
                content = getattr(getattr(choice, "message", None), "content", None)
                finish = getattr(choice, "finish_reason", None)
                yield {"content": content, "finish_reason": finish}

        try:
            stream = await self._client.chat.completions.create(**payload)
            # 流式正常路径
            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                yield {
                    "content": choice.delta.content,
                    "finish_reason": choice.finish_reason,
                }
            return
        except Exception as exc:
            text = str(exc).lower()
            # 兼容部分提供商在 json 模式下不支持 stream 或报 "prefix ... json mode"/code 20033
            if response_format and ("json mode" in text or "20033" in text or "prefix" in text):
                # 1) 关闭流式，再试一次（多数兼容端点要求 json 模式非流式）
                payload_no_stream = {**payload, "stream": False}
                try:
                    resp = await self._client.chat.completions.create(**payload_no_stream)
                    async for item in _yield_final(resp):
                        yield item
                    return
                except Exception:
                    # 2) 去掉 json 响应约束，退回普通流式
                    pass

            # 最后兜底：去掉 response_format 再流式请求
            payload_fallback = {k: v for k, v in payload.items() if k != "response_format"}
            stream = await self._client.chat.completions.create(**payload_fallback)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                yield {
                    "content": choice.delta.content,
                    "finish_reason": choice.finish_reason,
                }
