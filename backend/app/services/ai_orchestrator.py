"""
AI Orchestrator - AI功能路由和调度层

根据功能类型自动选择对应的API提供商和模型
支持fallback和重试机制
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..config.ai_function_config import (
    AIFunctionType,
    FunctionRouteConfig,
    ProviderConfig,
    get_function_config,
)
from ..models.ai_routing import AIFunctionCallLog
from ..repositories.ai_routing_repository import (
    AIProviderRepository,
    AIFunctionRouteRepository,
    AIFunctionCallLogRepository,
)
from ..services.llm_service import LLMService
from ..utils.metrics import (
    ai_calls_total,
    ai_duration_seconds,
    ai_cost_usd_total,
    ai_fallback_total,
    ai_error_total,
    ai_calls_in_progress,
)

logger = logging.getLogger(__name__)


class AIOrchestrator:
    """AI功能调度器，负责根据功能类型路由到对应的模型"""

    def __init__(
        self,
        llm_service: LLMService,
        db_session: Optional[AsyncSession] = None
    ):
        self.llm_service = llm_service
        self.db_session = db_session

        # 初始化repositories（如果有数据库连接）
        if db_session:
            self.provider_repo = AIProviderRepository(db_session)
            self.route_repo = AIFunctionRouteRepository(db_session)
            self.log_repo = AIFunctionCallLogRepository(db_session)
        else:
            self.provider_repo = None
            self.route_repo = None
            self.log_repo = None

    async def execute(
        self,
        function: AIFunctionType,
        system_prompt: str,
        user_prompt: str,
        *,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None,
        user_id: Optional[int] = None,
        response_format: Optional[str] = "json_object",
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        执行AI功能调用

        Args:
            function: AI功能类型
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            conversation_history: 对话历史（可选，用于需要上下文的场景如概念对话）
            temperature: 温度参数（可选，默认使用配置中的值）
            timeout: 超时时间（可选，默认使用配置中的值）
            user_id: 用户ID
            response_format: 响应格式
            max_tokens: 最大生成token数（可选）

        Returns:
            LLM响应文本

        Raises:
            ValueError: 如果功能类型未配置
            HTTPException: 如果所有尝试都失败
        """
        # ✅ 优先检查用户自定义路由配置
        user_route_config = await self.llm_service.get_user_route_config(user_id)

        if user_route_config:
            # 用户配置了自定义路由，使用用户的配置
            return await self._execute_with_user_routes(
                function=function,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                conversation_history=conversation_history,
                temperature=temperature,
                timeout=timeout,
                user_id=user_id,
                response_format=response_format,
                user_route_config=user_route_config,
                max_tokens=max_tokens,
            )

        # 获取默认功能配置
        config = get_function_config(function)
        if not config:
            raise ValueError(f"未找到功能 {function} 的配置")

        # 使用配置中的参数，如果调用时未指定
        final_temperature = temperature if temperature is not None else config.temperature
        final_timeout = timeout if timeout is not None else config.timeout

        # 构建消息
        messages = [{"role": "system", "content": system_prompt}]

        # 如果有对话历史，添加历史消息
        if conversation_history:
            messages.extend(conversation_history)

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_prompt})

        logger.info(
            f"执行AI功能: {function.value}, 主模型: {config.primary.provider}/{config.primary.model}"
        )

        # ✅ 使用 try-finally 确保指标一定会被清理
        ai_calls_in_progress.labels(function=function.value).inc()
        try:
            # 构建尝试列表：主模型 + 备用模型
            attempts = [config.primary] + config.fallbacks

            last_error = None
            fallback_count = 0
            start_time = time.time()

            # 依次尝试每个模型（带重试）
            for idx, provider_config in enumerate(attempts):
                is_fallback = idx > 0
                if is_fallback:
                    fallback_count += 1

                attempt_label = f"备用模型{idx}" if is_fallback else "主模型"

                # 重试逻辑
                max_retries = config.max_retries if not is_fallback else 1
                for retry in range(max_retries):
                    retry_label = f"重试{retry+1}/{max_retries}" if retry > 0 else ""

                    logger.info(
                        f"尝试 {attempt_label} {retry_label}: "
                        f"{provider_config.provider}/{provider_config.model}"
                    )

                    call_start = time.time()
                    error_type = None
                    error_message = None
                    finish_reason = None

                    try:
                        # 调用LLMService.invoke
                        response = await self.llm_service.invoke(
                            provider=provider_config.provider,
                            model=provider_config.model,
                            messages=messages,
                            temperature=final_temperature,
                            timeout=final_timeout,
                            response_format=response_format,
                            user_id=user_id,
                        )

                        duration_ms = int((time.time() - call_start) * 1000)
                        duration_seconds = duration_ms / 1000.0

                        logger.info(
                            f"✅ {attempt_label} 调用成功: "
                            f"{provider_config.provider}/{provider_config.model}, "
                            f"耗时: {duration_ms}ms"
                        )

                        # 记录Prometheus指标
                        ai_calls_total.labels(
                            function=function.value,
                            provider=provider_config.provider,
                            status="success"
                        ).inc()

                        ai_duration_seconds.labels(
                            function=function.value,
                            provider=provider_config.provider
                        ).observe(duration_seconds)

                        if is_fallback:
                            ai_fallback_total.labels(
                                function=function.value,
                                from_provider=config.primary.provider,
                                to_provider=provider_config.provider
                            ).inc()

                        # 记录成功日志到数据库
                        await self._log_call(
                            function=function,
                            provider=provider_config.provider,
                            model=provider_config.model,
                            status="success",
                            is_fallback=is_fallback,
                            fallback_count=fallback_count,
                            duration_ms=duration_ms,
                            user_id=user_id,
                            temperature=final_temperature,
                            timeout=final_timeout,
                            finish_reason="stop",
                        )

                        # ✅ 不在这里dec，在finally中统一处理
                        return response

                    except asyncio.TimeoutError as e:
                        error_type = "timeout"
                        error_message = str(e)
                        last_error = e
                        logger.warning(f"⏱️ {attempt_label} 超时")

                    except Exception as e:
                        error_type = self._classify_error(e)
                        error_message = str(e)
                        last_error = e
                        logger.warning(
                            f"❌ {attempt_label} 调用失败: "
                            f"{provider_config.provider}/{provider_config.model}, "
                            f"错误类型: {error_type}, 错误: {str(e)}"
                        )

                    # 记录失败指标
                    duration_ms = int((time.time() - call_start) * 1000)

                    ai_calls_total.labels(
                        function=function.value,
                        provider=provider_config.provider,
                        status="failed"
                    ).inc()

                    ai_error_total.labels(
                        function=function.value,
                        provider=provider_config.provider,
                        error_type=error_type or "unknown"
                    ).inc()

                    # 记录失败日志到数据库
                    await self._log_call(
                        function=function,
                        provider=provider_config.provider,
                        model=provider_config.model,
                        status="failed",
                        is_fallback=is_fallback,
                        fallback_count=fallback_count,
                        duration_ms=duration_ms,
                        user_id=user_id,
                        temperature=final_temperature,
                        timeout=final_timeout,
                        error_type=error_type,
                        error_message=error_message,
                    )

                    # 如果还有重试机会，等待后重试
                    if retry < max_retries - 1:
                        wait_time = self._calculate_backoff(retry)
                        logger.info(f"等待 {wait_time}s 后重试...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # 重试次数用完，尝试下一个模型
                        break

                # 如果还有备用模型，继续尝试
                if idx < len(attempts) - 1:
                    logger.info(f"切换到下一个模型...")
                    continue
                else:
                    # 所有模型都失败了
                    if config.required:
                        # 必须成功的功能，抛出错误
                        logger.error(
                            f"所有模型都失败了，功能 {function.value} 无法完成"
                        )
                        raise last_error
                    else:
                        # 可选功能，返回默认值
                        logger.warning(
                            f"所有模型都失败了，功能 {function.value} 返回默认值"
                        )
                        return self._get_default_response(function)

                # 理论上不会到这里
                raise last_error

        finally:
            # ✅ 确保一定会执行，无论成功还是失败
            ai_calls_in_progress.labels(function=function.value).dec()

    def _get_default_response(self, function: AIFunctionType) -> str:
        """
        为可选功能返回默认响应
        """
        defaults = {
            AIFunctionType.VOLUME_NAMING: '{"title": "未命名卷"}',
            AIFunctionType.ENHANCED_ANALYSIS: "{}",
            AIFunctionType.CHARACTER_TRACKING: "{}",
            AIFunctionType.WORLDVIEW_EXPANSION: "{}",
        }
        return defaults.get(function, "{}")

    def _classify_error(self, error: Exception) -> str:
        """
        分类错误类型
        """
        error_str = str(error).lower()

        if "timeout" in error_str:
            return "timeout"
        elif "rate" in error_str or "limit" in error_str:
            return "rate_limit"
        elif "quota" in error_str:
            return "quota_exceeded"
        elif "json" in error_str or "parse" in error_str:
            return "invalid_response"
        elif "connection" in error_str or "network" in error_str:
            return "network_error"
        elif "auth" in error_str or "key" in error_str:
            return "auth_error"
        else:
            return "unknown_error"

    def _calculate_backoff(self, retry_count: int) -> float:
        """
        计算指数退避时间
        """
        # 指数退避: 2^retry_count 秒，最多30秒
        return min(2 ** retry_count, 30)

    async def _log_call(
        self,
        function: AIFunctionType,
        provider: str,
        model: str,
        status: str,
        is_fallback: bool,
        fallback_count: int,
        duration_ms: int,
        user_id: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        finish_reason: Optional[str] = None,
    ):
        """
        记录调用日志到数据库
        """
        if not self.log_repo:
            return

        try:
            log = AIFunctionCallLog(
                function_type=function.value,
                model=model,
                user_id=user_id,
                temperature=temperature,
                timeout_seconds=int(timeout) if timeout else None,
                status=status,
                is_fallback=is_fallback,
                fallback_count=fallback_count,
                duration_ms=duration_ms,
                error_type=error_type,
                error_message=error_message[:500] if error_message else None,
                finish_reason=finish_reason,
            )

            await self.log_repo.create(log)
            # ✅ 移除commit，让调用者控制事务边界
            # await self.db_session.commit()

        except Exception as e:
            logger.error(f"记录调用日志失败: {e}")
            # 不影响主流程

    async def execute_batch(
        self,
        function: AIFunctionType,
        prompts: List[Dict[str, str]],
        *,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None,
        user_id: Optional[int] = None,
        response_format: Optional[str] = "json_object",
    ) -> List[str]:
        """
        批量执行AI功能调用

        Args:
            function: AI功能类型
            prompts: 提示词列表，每个元素包含 system_prompt 和 user_prompt
            其他参数同 execute()

        Returns:
            响应列表
        """
        results = []
        for prompt in prompts:
            try:
                result = await self.execute(
                    function=function,
                    system_prompt=prompt["system_prompt"],
                    user_prompt=prompt["user_prompt"],
                    conversation_history=prompt.get("conversation_history"),
                    temperature=temperature,
                    timeout=timeout,
                    user_id=user_id,
                    response_format=response_format,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"批量调用失败: {str(e)}")
                # 根据配置决定是否继续
                config = get_function_config(function)
                if config and not config.required:
                    results.append(self._get_default_response(function))
                else:
                    raise

        return results


    async def _execute_with_user_routes(
        self,
        function: AIFunctionType,
        system_prompt: str,
        user_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]],
        temperature: Optional[float],
        timeout: Optional[float],
        user_id: Optional[int],
        response_format: Optional[str],
        user_route_config: Dict,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        使用用户自定义路由执行AI调用

        Args:
            function: AI功能类型
            user_route_config: 用户路由配置
            max_tokens: 最大生成token数（可选）
            其他参数同 execute()

        Returns:
            LLM响应文本
        """
        # 查找该功能对应的路由索引
        functions = user_route_config.get("functions", [])
        routes = user_route_config.get("routes", [])

        # 找到该功能的配置
        function_key = function.value  # 将枚举转为字符串
        route_index = None

        for func_config in functions:
            if func_config.get("key") == function_key:
                route_index = func_config.get("routeIndex")
                break

        if route_index is None:
            logger.warning(f"用户未配置功能 {function_key} 的路由，将使用默认配置")
            # 返回 None，让调用方使用默认配置
            return None

        # 获取对应的路由配置
        if route_index >= len(routes):
            raise ValueError(f"路由索引 {route_index} 超出范围（共 {len(routes)} 个路由）")

        route = routes[route_index]

        if not route.get("enabled"):
            raise ValueError(f"路由{route_index + 1} 未启用")

        # 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]

        # 添加对话历史（如果有）
        if conversation_history:
            messages.extend(conversation_history)

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_prompt})

        # 使用路由配置调用 LLM
        provider = self._extract_provider_from_url(route.get("url", ""))
        model = route.get("model", "")

        # 使用默认温度和超时（如果未指定）
        final_temperature = temperature if temperature is not None else 0.7
        final_timeout = timeout if timeout is not None else 300.0

        logger.info(
            f"使用用户路由{route_index + 1}调用 {function_key}: "
            f"provider={provider}, model={model}"
        )

        # 临时构建一个 ProviderConfig 来调用
        from ..config.ai_function_config import ProviderConfig

        provider_config = ProviderConfig(
            provider=provider,
            model=model,
            base_url=route.get("url"),
            api_key=route.get("apiKey"),
        )

        # 记录调用开始
        start_time = time.time()
        call_log = None

        if self.log_repo:
            call_log = AIFunctionCallLog(
                function_type=function.value,
                model=model,
                user_id=user_id,
                status="pending",
            )
            self.db_session.add(call_log)
            await self.db_session.flush()

        try:
            # 调用 LLM Service
            response = await self.llm_service.invoke(
                provider=provider,
                model=model,
                messages=messages,
                temperature=final_temperature,
                timeout=final_timeout,
                response_format=response_format,
                user_id=user_id,
                max_tokens=max_tokens,
            )

            # 记录成功
            duration_ms = int((time.time() - start_time) * 1000)
            duration_seconds = duration_ms / 1000.0

            if call_log:
                call_log.status = "success"
                call_log.duration_ms = duration_ms
                await self.db_session.commit()

            # 更新指标（注意：ai_calls_total 只有 function, provider, status 三个标签）
            ai_calls_total.labels(
                function=function.value,
                provider=provider,
                status="success"
            ).inc()

            ai_duration_seconds.labels(
                function=function.value,
                provider=provider
            ).observe(duration_seconds)

            logger.info(f"✅ 用户路由调用成功: {function_key}, 耗时 {duration_ms}ms")

            return response

        except Exception as e:
            # 记录失败
            duration_ms = int((time.time() - start_time) * 1000)
            error_type = self._classify_error(e)

            if call_log:
                call_log.status = "failed"
                call_log.duration_ms = duration_ms
                call_log.error_type = error_type
                call_log.error_message = str(e)
                await self.db_session.commit()

            # 更新指标
            ai_calls_total.labels(
                function=function.value,
                provider=provider,
                status="failed"
            ).inc()

            ai_error_total.labels(
                function=function.value,
                provider=provider,
                error_type=error_type or "unknown"
            ).inc()

            logger.error(f"❌ 用户路由调用失败: {function_key}, 错误类型: {error_type}, 错误: {e}")
            raise

    def _extract_provider_from_url(self, url: str) -> str:
        """从 URL 中提取 provider 名称"""
        if "siliconflow" in url:
            return "siliconflow"
        elif "openai" in url:
            return "openai"
        elif "gemini" in url or "generativelanguage" in url:
            return "gemini"
        elif "deepseek" in url:
            return "deepseek"
        else:
            return "custom"

