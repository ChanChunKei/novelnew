"""
AI Orchestrator 辅助函数

提供便捷的方法来使用Orchestrator，简化现有代码的集成
"""
import asyncio
import logging
import json
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..config.ai_function_config import AIFunctionType
from ..services.ai_orchestrator import AIOrchestrator
from ..services.llm_service import LLMService
import re

logger = logging.getLogger(__name__)


# ==================== 三Agent对话模式常量配置 ====================
MAX_REWRITE_ITERATIONS = 5  # 最多重写次数
MAX_PLANNER_TOOL_ROUNDS = 3  # 思考Agent最多工具调用轮数
MAX_WRITER_TOOL_ROUNDS = 2  # 写作Agent最多工具调用轮数
MIN_APPROVAL_SCORE = 80  # 审批通过最低分数
PLANNER_TEMPERATURE = 0.7  # 思考Agent温度
WRITER_TEMPERATURE = 0.9  # 写作Agent温度
REVIEWER_TEMPERATURE = 0.3  # 审批Agent温度
SUMMARIZER_TEMPERATURE = 0.5  # 总结Agent温度
AGENT_DIALOGUE_TOTAL_TIMEOUT = 600.0  # 三Agent对话总超时时间（10分钟）

# ==================== 三Agent大纲生成模式常量配置 ====================
MAX_OUTLINE_ITERATIONS = 3  # 大纲最多重写次数
MIN_OUTLINE_SCORE = 75  # 大纲审批通过最低分数（略低于章节的80分，因为大纲是规划阶段）
OUTLINE_PLANNER_TEMPERATURE = 0.6  # 大纲规划Agent温度（更理性，专注于结构规划）
OUTLINE_WRITER_TEMPERATURE = 0.9  # 大纲撰写Agent温度（更有创造性，同章节Writer）
OUTLINE_REVIEWER_TEMPERATURE = 0.3  # 大纲审核Agent温度（严格客观）
OUTLINE_DIALOGUE_TOTAL_TIMEOUT = 600.0  # 大纲生成总超时时间（10分钟）


# ==================== Prompt读取辅助函数 ====================
async def get_agent_prompt_from_db(
    db_session: AsyncSession,
    agent_type: str,
    is_outline: bool = False
) -> str:
    """
    从数据库读取Agent Prompt，如果不存在则使用代码中的默认值

    Args:
        db_session: 数据库会话
        agent_type: Agent类型 ("planner", "writer", "reviewer", "summarizer")
        is_outline: 是否是大纲Agent（True）还是章节Agent（False）

    Returns:
        Prompt内容
    """
    from ..services.prompt_service import PromptService

    # 构建prompt名称
    if is_outline:
        prompt_name = f"outline_agent_{agent_type}"
    else:
        prompt_name = f"agent_{agent_type}"

    # 尝试从数据库读取
    try:
        prompt_service = PromptService(db_session)
        db_prompt = await prompt_service.get_prompt(prompt_name)
        if db_prompt:
            logger.debug(f"从数据库加载Prompt: {prompt_name}")
            return db_prompt
    except Exception as e:
        logger.warning(f"从数据库读取Prompt失败: {prompt_name}, 错误: {e}")

    # 回退到代码中的默认值
    logger.debug(f"使用代码默认Prompt: {prompt_name}")
    if is_outline:
        from ..config.outline_agent_prompts import get_outline_agent_prompt
        return get_outline_agent_prompt(agent_type)
    else:
        from ..config.agent_prompts import get_agent_prompt
        return get_agent_prompt(agent_type)


def _strip_markdown_formatting(text: str) -> str:
    """
    移除文本中的Markdown格式标记，保留纯文本内容

    处理的标记：
    - 标题：## 、### 等
    - 粗体：**文本** 或 __文本__
    - 斜体：*文本* 或 _文本_
    - 代码：`文本`
    - 链接：[文本](url)
    - 行尾反斜杠+换行符（Markdown硬换行）
    - 其他常见标记
    """
    if not text:
        return text

    # 移除标题标记（##、###等），保留文本
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # 移除粗体标记 **text** 或 __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)

    # 移除斜体标记 *text* 或 _text_（要在粗体之后处理）
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)

    # 移除行内代码标记 `code`
    text = re.sub(r'`(.+?)`', r'\1', text)

    # 移除链接，保留文本 [text](url) -> text
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)

    # 移除图片 ![alt](url) -> alt
    text = re.sub(r'!\[(.+?)\]\(.+?\)', r'\1', text)

    # 移除引用标记 >
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

    # 移除列表标记 - 或 * 或 数字.
    text = re.sub(r'^[\*\-\+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)

    # 移除Markdown硬换行：行尾的反斜杠+换行符 (\ + \n)
    text = re.sub(r'\\\s*\n', '\n', text)

    return text


def _clean_full_content(content: str, chapter_number: int = 0, version_idx: int = 0) -> str:
    """
    清理full_content，应用与auto_generator相同的清理流程

    处理步骤：
    1. 检测并处理嵌套JSON
    2. 双重转义修复（\\n → \n）
    3. Markdown标记清理

    Args:
        content: 原始内容
        chapter_number: 章节号（用于日志）
        version_idx: 版本号（用于日志）

    Returns:
        清理后的内容
    """
    if not content or not isinstance(content, str):
        return content

    original_content = content

    # 步骤1: 检测嵌套JSON
    if content.strip().startswith("{"):
        try:
            nested = json.loads(content)
            if isinstance(nested, dict) and "full_content" in nested:
                logger.warning(f"第 {chapter_number} 章版本 {version_idx}: 检测到嵌套JSON，自动提取")
                content = nested["full_content"]
        except json.JSONDecodeError:
            pass

    # 步骤2: 双重转义修复
    # ⚠️ 只处理真正的双重转义（\\n、\\t等字符串字面量），而不是所有包含\的字符串
    if isinstance(content, str):
        # 检测是否有双重转义：查找 \\n \\t \\r \\" 等模式
        has_double_escape = any([
            '\\n' in content,   # 字符串字面量 \n
            '\\t' in content,   # 字符串字面量 \t
            '\\r' in content,   # 字符串字面量 \r
            '\\"' in content,   # 字符串字面量 \"
            "\\'" in content,   # 字符串字面量 \'
        ])

        if has_double_escape:
            try:
                original_escaped = content
                # 使用 encode().decode('unicode_escape') 进行反转义
                content = content.encode('utf-8').decode('unicode_escape')

                if content != original_escaped:
                    logger.warning(
                        f"第 {chapter_number} 章版本 {version_idx}: 检测到双重转义，已自动修复\n"
                        f"  原始: {original_escaped[:80]}...\n"
                        f"  修复后: {content[:80]}..."
                    )
            except Exception as e:
                logger.error(f"第 {chapter_number} 章版本 {version_idx}: 反转义失败: {e}，保持原样")

    # 步骤3: Markdown标记清理
    if isinstance(content, str):
        cleaned = _strip_markdown_formatting(content)

        if cleaned != original_content:
            logger.warning(
                f"第 {chapter_number} 章版本 {version_idx}: 检测到并清理了格式标记\n"
                f"  原始预览: {original_content[:100]}...\n"
                f"  清理后预览: {cleaned[:100]}..."
            )

        return cleaned

    return content


async def call_ai_function(
    db_session: AsyncSession,
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
    便捷方法：调用AI功能

    使用示例:
        response = await call_ai_function(
            db_session=db,
            function=AIFunctionType.CHAPTER_CONTENT_WRITING,
            system_prompt="你是专业的小说作家...",
            user_prompt="请生成第1章...",
            user_id=user_id,
        )
    """
    llm_service = LLMService(db_session)
    orchestrator = AIOrchestrator(llm_service, db_session)

    return await orchestrator.execute(
        function=function,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        conversation_history=conversation_history,
        temperature=temperature,
        timeout=timeout,
        user_id=user_id,
        response_format=response_format,
        max_tokens=max_tokens,
    )


async def generate_chapter_content(
    db_session: AsyncSession,
    system_prompt: str,
    user_prompt: str,
    user_id: int,
    temperature: float = 0.9,
    timeout: float = 600.0,
    generation_mode: str = "basic",
    project_id: Optional[str] = None,
    chapter_number: Optional[int] = None,
) -> str:
    """
    生成章节正文

    Args:
        db_session: 数据库会话
        system_prompt: 系统提示词
        user_prompt: 用户提示词（通常是大纲+上下文）
        user_id: 用户ID
        temperature: 温度参数
        timeout: 超时时间
        generation_mode: 生成模式 ("basic" / "enhanced" / "agent")
        project_id: 项目ID（Agent模式需要）
        chapter_number: 章节号（Agent模式需要）

    Returns:
        生成的章节内容（JSON字符串）
    """
    # ✅ Agent模式：使用Function Calling智能查询
    if generation_mode == "agent":
        return await _generate_with_agent(
            db_session=db_session,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            user_id=user_id,
            temperature=temperature,
            timeout=timeout,
            project_id=project_id,
            chapter_number=chapter_number,
        )

    # ✅ 三Agent对话模式：思考→写作→审批→总结
    if generation_mode == "agent_dialogue" or generation_mode == "multi_agent":
        return await _generate_with_agent_dialogue(
            db_session=db_session,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            user_id=user_id,
            temperature=temperature,
            timeout=timeout,
            project_id=project_id,
            chapter_number=chapter_number,
        )

    # 传统模式：直接调用AI
    return await call_ai_function(
        db_session=db_session,
        function=AIFunctionType.CHAPTER_CONTENT_WRITING,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        timeout=timeout,
        user_id=user_id,
        response_format="json_object",
    )


async def generate_outline(
    db_session: AsyncSession,
    system_prompt: str,
    user_prompt: str,
    user_id: int,
    temperature: float = 0.7,
    timeout: float = 360.0,
) -> str:
    """生成大纲"""
    return await call_ai_function(
        db_session=db_session,
        function=AIFunctionType.OUTLINE_GENERATION,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        timeout=timeout,
        user_id=user_id,
        response_format="json_object",
    )


async def generate_summary(
    db_session: AsyncSession,
    chapter_content: str,
    user_id: int,
    system_prompt: Optional[str] = None,
    temperature: float = 0.15,
    timeout: float = 180.0,
    blueprint_dict: Optional[dict] = None,
    volumes_snapshot: Optional[list] = None,
) -> str:
    """
    生成章节摘要

    替代原来的:
        summary = await llm_service.get_summary(
            chapter_content=content,
            temperature=0.2,
            user_id=user_id,
            timeout=180.0
        )

    改为:
        summary = await generate_summary(
            db_session=db,
            chapter_content=content,
            user_id=user_id,
            blueprint_dict=blueprint_dict,
            volumes_snapshot=volumes_snapshot,
        )
    """
    import json

    if not system_prompt:
        from ..services.prompt_service import PromptService
        prompt_service = PromptService(db_session)
        system_prompt = await prompt_service.get_prompt("extraction")
        if not system_prompt:
            raise ValueError("未配置摘要提示词")

    # 🔥 构建与章节评估一致的上下文
    context_payload = {
        "chapter_content": chapter_content
    }

    if blueprint_dict:
        context_payload["novel_blueprint"] = blueprint_dict

    if volumes_snapshot:
        context_payload["volumes_snapshot"] = volumes_snapshot

    user_content = json.dumps(context_payload, ensure_ascii=False)

    return await call_ai_function(
        db_session=db_session,
        function=AIFunctionType.SUMMARY_EXTRACTION,
        system_prompt=system_prompt,
        user_prompt=user_content,
        temperature=temperature,
        timeout=timeout,
        user_id=user_id,
        response_format=None,  # 摘要不需要JSON格式
    )


async def evaluate_chapter(
    db_session: AsyncSession,
    system_prompt: str,
    evaluation_payload: Dict,
    user_id: int,
    temperature: float = 0.3,
    timeout: float = 360.0,
) -> str:
    """评估章节版本"""
    import json
    
    return await call_ai_function(
        db_session=db_session,
        function=AIFunctionType.BASIC_ANALYSIS,  # 使用基础分析功能
        system_prompt=system_prompt,
        user_prompt=json.dumps(evaluation_payload, ensure_ascii=False),
        temperature=temperature,
        timeout=timeout,
        user_id=user_id,
        response_format="json_object",
    )


async def concept_dialogue(
    db_session: AsyncSession,
    system_prompt: str,
    user_message: str,
    user_id: int,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    temperature: float = 0.8,
    timeout: float = 240.0,
) -> str:
    """
    概念对话

    Args:
        db_session: 数据库会话
        system_prompt: 系统提示词
        user_message: 用户消息
        user_id: 用户ID
        conversation_history: 对话历史（不包含当前用户消息）
        temperature: 温度参数
        timeout: 超时时间

    Returns:
        AI响应文本
    """
    return await call_ai_function(
        db_session=db_session,
        function=AIFunctionType.CONCEPT_DIALOGUE,
        system_prompt=system_prompt,
        user_prompt=user_message,
        conversation_history=conversation_history,
        temperature=temperature,
        timeout=timeout,
        user_id=user_id,
        response_format="json_object",
    )


async def generate_blueprint(
    db_session: AsyncSession,
    system_prompt: str,
    conversation_history: List[Dict[str, str]],
    user_id: int,
    temperature: float = 0.3,
    timeout: float = 480.0,
) -> str:
    """
    生成蓝图

    Args:
        db_session: 数据库会话
        system_prompt: 系统提示词
        conversation_history: 完整的对话历史（从文思对话中提取）
        user_id: 用户ID
        temperature: 温度参数
        timeout: 超时时间

    Returns:
        AI响应文本（蓝图JSON）
    """
    # 提取最后一条用户消息作为 user_prompt
    user_prompt = ""
    for msg in reversed(conversation_history):
        if msg["role"] == "user":
            user_prompt = msg["content"]
            break

    # 如果没有找到用户消息，使用默认提示
    if not user_prompt:
        user_prompt = "请根据我们的对话生成小说蓝图"

    # 传递除最后一条消息外的历史
    history_without_last = [msg for msg in conversation_history if not (msg["role"] == "user" and msg["content"] == user_prompt)]

    return await call_ai_function(
        db_session=db_session,
        function=AIFunctionType.BLUEPRINT_GENERATION,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        conversation_history=history_without_last,
        temperature=temperature,
        timeout=timeout,
        user_id=user_id,
        response_format="json_object",
        # 不限制 max_tokens，让 AI 自由生成完整蓝图（20-50章大纲）
    )


# 向后兼容：提供一个包装器，让现有代码可以逐步迁移
class OrchestratorWrapper:
    """
    包装器类，提供与LLMService相同的接口
    
    使用方法:
        # 原来的代码
        llm_service = LLMService(db)
        
        # 改为
        llm_service = OrchestratorWrapper(db)
        
        # 其他代码不变
        response = await llm_service.get_llm_response(...)
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.llm_service = LLMService(db_session)
        self.orchestrator = AIOrchestrator(self.llm_service, db_session)
    
    async def get_llm_response(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        response_format: Optional[str] = "json_object",
    ) -> str:
        """
        兼容原有的get_llm_response接口
        自动根据上下文选择合适的AI功能
        """
        # 简单的启发式：根据temperature和timeout推断功能类型
        if timeout >= 600:
            function = AIFunctionType.CHAPTER_CONTENT_WRITING
        elif timeout >= 360:
            function = AIFunctionType.OUTLINE_GENERATION
        elif timeout >= 180:
            function = AIFunctionType.BASIC_ANALYSIS
        else:
            function = AIFunctionType.SUMMARY_EXTRACTION
        
        # 提取用户消息
        user_prompt = ""
        for msg in conversation_history:
            if msg["role"] == "user":
                user_prompt = msg["content"]
                break
        
        return await self.orchestrator.execute(
            function=function,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            timeout=timeout,
            user_id=user_id,
            response_format=response_format,
        )
    
    async def get_summary(
        self,
        chapter_content: str,
        *,
        temperature: float = 0.2,
        user_id: Optional[int] = None,
        timeout: float = 180.0,
        system_prompt: Optional[str] = None,
        blueprint_dict: Optional[dict] = None,
        volumes_snapshot: Optional[list] = None,
    ) -> str:
        """兼容原有的get_summary接口"""
        return await generate_summary(
            db_session=self.db_session,
            chapter_content=chapter_content,
            user_id=user_id,
            system_prompt=system_prompt,
            temperature=temperature,
            timeout=timeout,
            blueprint_dict=blueprint_dict,
            volumes_snapshot=volumes_snapshot,
        )
    
    # 其他方法直接委托给原始LLMService
    async def get_embedding(self, *args, **kwargs):
        return await self.llm_service.get_embedding(*args, **kwargs)

    async def get_embedding_dimension(self, *args, **kwargs):
        return await self.llm_service.get_embedding_dimension(*args, **kwargs)


# ==================== Agent模式实现 ====================

async def _generate_with_agent(
    db_session: AsyncSession,
    system_prompt: str,
    user_prompt: str,
    user_id: int,
    temperature: float,
    timeout: float,
    project_id: Optional[str],
    chapter_number: Optional[int],
) -> str:
    """
    Agent模式生成章节

    使用Function Calling让AI主动查询需要的历史信息

    流程：
    1. AI分析大纲，决定需要查询什么信息
    2. 执行工具调用（查询数据库、向量检索等）
    3. AI基于查询结果生成最终章节内容

    最多5轮对话，避免无限循环
    """
    import json
    from ..config.agent_tools import NOVEL_AGENT_TOOLS
    from ..config.ai_function_config import get_function_config

    llm_service = LLMService(db_session)

    # 获取配置
    config = get_function_config(AIFunctionType.CHAPTER_CONTENT_WRITING)
    provider = config.primary.provider
    model = config.primary.model

    # 初始化消息
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # Agent循环（最多5轮）
    max_rounds = 5
    for round_num in range(max_rounds):
        logger.info(f"Agent第{round_num + 1}轮开始")

        # 最后一轮需要强制生成JSON格式的章节内容
        is_final_round = (round_num == max_rounds - 1)

        # 调用LLM（带tools参数）
        response_str = await llm_service.invoke(
            provider=provider,
            model=model,
            messages=messages,
            temperature=temperature if not is_final_round else 0.9,  # 最后一轮用高温度生成
            timeout=timeout,
            user_id=user_id,
            tools=None if is_final_round else NOVEL_AGENT_TOOLS,  # 最后一轮不提供工具，强制生成内容
            response_format="json_object" if is_final_round else None,  # ✅ 最后一轮强制JSON格式
        )

        # 解析响应
        try:
            response = json.loads(response_str)
        except json.JSONDecodeError:
            # 不是JSON，直接返回（可能是最后一轮的内容）
            logger.info(f"Agent在第{round_num + 1}轮生成了内容（非JSON）")
            return response_str

        # 检查是否有工具调用
        if "tool_calls" in response and response["tool_calls"]:
            tool_calls = response["tool_calls"]
            logger.info(f"Agent在第{round_num + 1}轮调用了{len(tool_calls)}个工具")

            # 添加assistant消息
            messages.append({
                "role": "assistant",
                "content": response.get("content") or "",
                "tool_calls": tool_calls
            })

            # 执行工具调用
            tool_results = await _execute_tools(
                db_session=db_session,
                project_id=project_id,
                chapter_number=chapter_number,
                tool_calls=tool_calls
            )

            # 添加工具结果到消息
            for tool_call, result in zip(tool_calls, tool_results):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result
                })
        else:
            # 没有工具调用，AI已经生成了最终内容
            logger.info(f"Agent在第{round_num + 1}轮完成生成")
            return response.get("content") or response_str

    # 达到最大轮次，返回最后的响应
    logger.warning(f"Agent达到最大轮次{max_rounds}，强制返回")
    return response_str


async def _execute_tools(
    db_session: AsyncSession,
    project_id: Optional[str],
    chapter_number: Optional[int],
    tool_calls: List[Dict],
) -> List[str]:
    """
    执行工具调用

    Args:
        db_session: 数据库会话
        project_id: 项目ID
        chapter_number: 当前章节号
        tool_calls: 工具调用列表

    Returns:
        工具执行结果列表
    """
    import asyncio
    import json

    async def execute_single_tool(tool_call: Dict) -> str:
        """执行单个工具调用"""
        function_name = tool_call["function"]["name"]
        arguments_str = tool_call["function"]["arguments"]

        try:
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError:
            return f"错误：无法解析参数 {arguments_str}"

        logger.info(f"执行工具: {function_name}，参数: {arguments}")

        try:
            if function_name == "search_chapters":
                return await _tool_search_chapters(db_session, project_id, arguments)
            elif function_name == "get_character_state":
                return await _tool_get_character_state(db_session, project_id, arguments)
            elif function_name == "get_world_setting":
                return await _tool_get_world_setting(db_session, project_id, arguments)
            elif function_name == "get_recent_chapters":
                return await _tool_get_recent_chapters(db_session, project_id, arguments)
            elif function_name == "check_plot_consistency":
                return await _tool_check_plot_consistency(db_session, project_id, arguments)
            elif function_name == "find_foreshadowing":
                return await _tool_find_foreshadowing(db_session, project_id, arguments)
            else:
                return f"错误：未知工具 {function_name}"
        except Exception as e:
            logger.error(f"工具执行失败: {function_name}, 错误: {str(e)}")
            return f"错误：工具执行失败 - {str(e)}"

    # 并行执行所有工具调用
    results = await asyncio.gather(*[execute_single_tool(tc) for tc in tool_calls])
    return results


# ==================== 工具实现函数 ====================

async def _tool_search_chapters(
    db_session: AsyncSession,
    project_id: Optional[str],
    arguments: Dict
) -> str:
    """搜索历史章节"""
    keyword = arguments.get("keyword")
    limit = arguments.get("limit", 3)

    if not project_id:
        return "错误：缺少project_id"

    # 方式1：使用向量检索（如果可用）
    try:
        from ..services.vector_store_service import VectorStoreService
        vector_service = VectorStoreService()

        results = await vector_service.search_chunks(
            project_id=project_id,
            query_text=keyword,
            top_k=limit
        )

        if results:
            formatted_results = []
            for chunk in results:
                formatted_results.append(
                    f"【第{chunk.chapter_number}章】{chunk.chapter_title or ''}\n"
                    f"相关度: {chunk.score:.2f}\n"
                    f"内容片段:\n{chunk.content[:500]}...\n"
                )
            return "\n\n".join(formatted_results)
    except Exception as e:
        logger.warning(f"向量检索失败，尝试数据库查询: {str(e)}")

    # 方式2：数据库全文搜索（fallback）
    try:
        from sqlalchemy import select, and_
        from sqlalchemy.orm import selectinload
        from ..models.novel import Chapter, ChapterVersion

        # ✅ 修复：Chapter没有content字段，需要查询ChapterVersion
        stmt = select(Chapter).where(
            and_(
                Chapter.project_id == project_id,
                Chapter.status == "successful"
            )
        ).options(
            selectinload(Chapter.selected_version)
        ).order_by(Chapter.chapter_number.desc()).limit(limit * 3)  # 多取一些，因为要在Python中过滤

        result = await db_session.execute(stmt)
        chapters = result.scalars().all()

        # 在ChapterVersion.content中搜索关键词
        formatted_results = []
        found_count = 0
        for ch in chapters:
            if found_count >= limit:
                break
            if ch.selected_version and keyword in ch.selected_version.content:
                # 找到包含关键词的位置，提取前后文
                content = ch.selected_version.content
                keyword_pos = content.find(keyword)
                start_pos = max(0, keyword_pos - 200)
                end_pos = min(len(content), keyword_pos + 300)
                snippet = content[start_pos:end_pos]

                formatted_results.append(
                    f"【第{ch.chapter_number}章】\n"
                    f"相关内容:\n...{snippet}...\n"
                )
                found_count += 1

        if formatted_results:
            return "\n\n".join(formatted_results)
        else:
            return f"未找到包含关键词'{keyword}'的章节"
    except Exception as e:
        logger.error(f"数据库查询失败: {str(e)}")
        return f"查询失败: {str(e)}"


async def _tool_get_character_state(
    db_session: AsyncSession,
    project_id: Optional[str],
    arguments: Dict
) -> str:
    """获取角色状态"""
    name = arguments.get("name")
    chapter_number = arguments.get("chapter_number")

    if not project_id:
        return "错误：缺少project_id"

    if not name:
        return "错误：缺少角色名称"

    try:
        from sqlalchemy import select, and_, or_, func
        from ..models.novel import BlueprintCharacter, Volume, Chapter

        # ✅ 实现：从蓝图角色表查询基础信息
        # 1. 先查询蓝图中的角色定义
        stmt = select(BlueprintCharacter).where(
            and_(
                BlueprintCharacter.project_id == project_id,
                BlueprintCharacter.name == name
            )
        )

        result = await db_session.execute(stmt)
        character = result.scalar_one_or_none()

        if not character:
            # 尝试模糊匹配
            stmt = select(BlueprintCharacter).where(
                and_(
                    BlueprintCharacter.project_id == project_id,
                    BlueprintCharacter.name.contains(name)
                )
            )
            result = await db_session.execute(stmt)
            character = result.scalar_one_or_none()

        if not character:
            return f"未找到角色【{name}】的信息。请检查角色名称是否正确。"

        # 2. 构建角色信息
        character_info = [
            f"=== 角色【{character.name}】信息 ===",
            "",
            f"身份：{character.identity or '未设定'}",
            f"性格：{character.personality or '未设定'}",
            f"目标：{character.goals or '未设定'}",
            f"能力：{character.abilities or '未设定'}",
            f"与主角关系：{character.relationship_to_protagonist or '未设定'}",
        ]

        # 3. 如果指定了章节号，尝试查找该章节时角色的最新状态
        if chapter_number:
            # 从最近几章中搜索该角色的相关描写
            from sqlalchemy.orm import selectinload

            stmt = select(Chapter).where(
                and_(
                    Chapter.project_id == project_id,
                    Chapter.chapter_number <= chapter_number,
                    Chapter.status == "successful"
                )
            ).options(
                selectinload(Chapter.selected_version)
            ).order_by(Chapter.chapter_number.desc()).limit(5)  # 最近5章

            result = await db_session.execute(stmt)
            recent_chapters = result.scalars().all()

            # 在内容中搜索角色名
            recent_mentions = []
            for ch in recent_chapters:
                if ch.selected_version and character.name in ch.selected_version.content:
                    content = ch.selected_version.content
                    # 找到角色名的位置，提取上下文
                    keyword_pos = content.find(character.name)
                    start_pos = max(0, keyword_pos - 100)
                    end_pos = min(len(content), keyword_pos + 200)
                    snippet = content[start_pos:end_pos]
                    recent_mentions.append(f"第{ch.chapter_number}章：...{snippet}...")

            if recent_mentions:
                character_info.append("")
                character_info.append(f"=== 截至第{chapter_number}章的最新状态 ===")
                character_info.extend(recent_mentions[:2])  # 只显示最近2次提及

        # 4. 添加额外信息
        if character.extra:
            character_info.append("")
            character_info.append("=== 其他信息 ===")
            import json
            for key, value in character.extra.items():
                character_info.append(f"{key}: {value}")

        return "\n".join(character_info)

    except Exception as e:
        logger.error(f"获取角色状态失败: {str(e)}")
        return f"查询角色失败: {str(e)}"


async def _tool_get_world_setting(
    db_session: AsyncSession,
    project_id: Optional[str],
    arguments: Dict
) -> str:
    """获取世界设定"""
    tag = arguments.get("tag")

    if not project_id:
        return "错误：缺少project_id"

    try:
        from sqlalchemy import select
        from ..models.novel import NovelBlueprint, Volume

        # ✅ 实现：从蓝图的world_setting字段查询
        # 1. 先查询蓝图中的世界观设定
        stmt = select(NovelBlueprint).where(
            NovelBlueprint.project_id == project_id
        )

        result = await db_session.execute(stmt)
        blueprint = result.scalar_one_or_none()

        if not blueprint:
            return f"未找到项目【{project_id}】的蓝图信息"

        world_setting = blueprint.world_setting or {}

        if not world_setting:
            return "该项目暂未设定世界观信息"

        # 2. 如果指定了标签，查找特定设定
        if tag:
            tag_lower = tag.lower()
            setting_info = []

            # 搜索匹配的设定
            for key, value in world_setting.items():
                if tag_lower in key.lower() or (isinstance(value, str) and tag_lower in value.lower()):
                    setting_info.append(f"【{key}】")
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            setting_info.append(f"  {sub_key}: {sub_value}")
                    elif isinstance(value, list):
                        for item in value:
                            setting_info.append(f"  - {item}")
                    else:
                        setting_info.append(f"  {value}")
                    setting_info.append("")

            if setting_info:
                return f"=== 世界设定：{tag} ===\n\n" + "\n".join(setting_info)
            else:
                # 没找到匹配的，返回所有设定供参考
                return f"未找到标签【{tag}】的具体设定。\n\n可用的设定标签：{', '.join(world_setting.keys())}"

        # 3. 如果没有指定标签，返回所有世界观设定
        setting_info = ["=== 世界观设定总览 ===", ""]

        for key, value in world_setting.items():
            setting_info.append(f"【{key}】")
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    setting_info.append(f"  {sub_key}: {sub_value}")
            elif isinstance(value, list):
                for item in value:
                    setting_info.append(f"  - {item}")
            else:
                setting_info.append(f"  {value}")
            setting_info.append("")

        return "\n".join(setting_info)

    except Exception as e:
        logger.error(f"获取世界设定失败: {str(e)}")
        return f"查询世界设定失败: {str(e)}"


async def _tool_get_recent_chapters(
    db_session: AsyncSession,
    project_id: Optional[str],
    arguments: Dict
) -> str:
    """获取最近N章内容"""
    current_chapter = arguments.get("current_chapter")
    count = arguments.get("count", 3)

    if not project_id or not current_chapter:
        return "错误：缺少project_id或current_chapter"

    try:
        from sqlalchemy import select, and_
        from ..models.novel import Chapter

        start_chapter = max(1, current_chapter - count)
        end_chapter = current_chapter - 1

        stmt = select(Chapter).where(
            and_(
                Chapter.project_id == project_id,
                Chapter.chapter_number >= start_chapter,
                Chapter.chapter_number <= end_chapter
            )
        ).order_by(Chapter.chapter_number)

        result = await db_session.execute(stmt)
        chapters = result.scalars().all()

        if not chapters:
            return f"未找到第{start_chapter}-{end_chapter}章的内容"

        formatted_results = []
        for ch in chapters:
            formatted_results.append(
                f"=== 第{ch.chapter_number}章：{ch.title or ''} ===\n"
                f"{ch.content or ''}\n"
            )
        return "\n\n".join(formatted_results)

    except Exception as e:
        logger.error(f"获取最近章节失败: {str(e)}")
        return f"查询失败: {str(e)}"


async def _tool_check_plot_consistency(
    db_session: AsyncSession,
    project_id: Optional[str],
    arguments: Dict
) -> str:
    """检查剧情一致性"""
    check_items = arguments.get("check_items", [])

    if not project_id:
        return "错误：缺少project_id"

    if not check_items:
        return "错误：未指定需要检查的项目"

    results = []

    for item in check_items:
        # 搜索相关章节
        search_result = await _tool_search_chapters(
            db_session=db_session,
            project_id=project_id,
            arguments={"keyword": item, "limit": 5}
        )

        results.append(f"## 检查项目：{item}\n{search_result}\n")

    if results:
        return (
            "=== 剧情一致性检查结果 ===\n\n"
            "以下是历史章节中关于这些项目的描述，请仔细检查是否存在矛盾：\n\n"
            + "\n".join(results)
        )
    else:
        return f"未找到关于 {', '.join(check_items)} 的相关内容"


async def _tool_find_foreshadowing(
    db_session: AsyncSession,
    project_id: Optional[str],
    arguments: Dict
) -> str:
    """查找伏笔"""
    chapter_range = arguments.get("chapter_range", "")

    if not project_id:
        return "错误：缺少project_id"

    # 解析章节范围（如"1-50"）
    start_chapter = 1
    end_chapter = 999
    if chapter_range and "-" in chapter_range:
        try:
            parts = chapter_range.split("-")
            start_chapter = int(parts[0])
            end_chapter = int(parts[1])
        except (ValueError, IndexError):
            return f"错误：无效的章节范围格式'{chapter_range}'，应该是'1-50'"

    try:
        from sqlalchemy import select, and_
        from sqlalchemy.orm import selectinload
        from ..models.novel import Chapter

        # 查询指定范围的章节
        stmt = select(Chapter).where(
            and_(
                Chapter.project_id == project_id,
                Chapter.chapter_number >= start_chapter,
                Chapter.chapter_number <= end_chapter,
                Chapter.status == "successful"
            )
        ).options(
            selectinload(Chapter.selected_version)
        ).order_by(Chapter.chapter_number)

        result = await db_session.execute(stmt)
        chapters = result.scalars().all()

        if not chapters:
            return f"章节范围{chapter_range}未找到已完成的章节"

        # 搜索可能包含伏笔的关键词
        foreshadowing_keywords = ["伏笔", "暗示", "预兆", "留下", "埋下", "隐藏", "秘密", "线索", "疑问"]

        results = []
        for ch in chapters:
            if not ch.selected_version:
                continue

            content = ch.selected_version.content
            found_keywords = []

            for keyword in foreshadowing_keywords:
                if keyword in content:
                    # 找到包含关键词的位置，提取前后文
                    keyword_pos = content.find(keyword)
                    start_pos = max(0, keyword_pos - 150)
                    end_pos = min(len(content), keyword_pos + 200)
                    snippet = content[start_pos:end_pos]
                    found_keywords.append((keyword, snippet))

            # 也检查章节摘要
            if ch.summary:
                for keyword in foreshadowing_keywords:
                    if keyword in ch.summary:
                        found_keywords.append((keyword, f"摘要：{ch.summary}"))

            if found_keywords:
                chapter_result = f"【第{ch.chapter_number}章】{ch.title or ''}\n"
                for kw, snippet in found_keywords[:3]:  # 最多显示3个
                    chapter_result += f"  含'{kw}'：...{snippet}...\n"
                results.append(chapter_result)

        if results:
            return (
                f"=== 章节{chapter_range}的伏笔线索 ===\n\n"
                f"找到 {len(results)} 章可能包含伏笔或未解决线索：\n\n"
                + "\n".join(results)
            )
        else:
            return f"章节范围{chapter_range}未找到明显的伏笔标记"

    except Exception as e:
        logger.error(f"查找伏笔失败: {str(e)}")
        return f"查找失败: {str(e)}"



# ==================== 三Agent对话模式实现 ====================

async def _generate_with_agent_dialogue(
    db_session: AsyncSession,
    system_prompt: str,
    user_prompt: str,
    user_id: int,
    temperature: float,
    timeout: float,
    project_id: Optional[str],
    chapter_number: Optional[int],
) -> str:
    """
    三Agent对话模式生成章节（带总体超时控制）

    工作流程：
    1. 思考Agent：分析大纲，决定查询什么历史信息
    2. 写作Agent：基于查询结果生成章节内容
    3. 审批Agent：审核内容，提供修改意见
    4. 如果不通过：写作Agent重写（可多轮，最多5次）
    5. 通过后：总结Agent生成摘要

    Args:
        db_session: 数据库会话
        system_prompt: 系统提示词（写作要求）
        user_prompt: 用户提示词（上下文：所有章节摘要 + 前两章完整内容 + 当前章大纲）
        user_id: 用户ID
        temperature: 温度参数
        timeout: 超时时间（单次AI调用超时）
        project_id: 项目ID（必需）
        chapter_number: 章节号（必需）

    Returns:
        生成的章节内容（JSON格式，包含content和summary）

    Raises:
        ValueError: 如果project_id或chapter_number为None
        asyncio.TimeoutError: 如果总体超时
    """
    # 添加总体超时控制
    try:
        result = await asyncio.wait_for(
            _generate_with_agent_dialogue_impl(
                db_session=db_session,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                user_id=user_id,
                temperature=temperature,
                timeout=timeout,
                project_id=project_id,
                chapter_number=chapter_number,
            ),
            timeout=AGENT_DIALOGUE_TOTAL_TIMEOUT
        )
        return result
    except asyncio.TimeoutError:
        logger.error(f"三Agent对话超时（{AGENT_DIALOGUE_TOTAL_TIMEOUT}秒）：第{chapter_number}章")
        raise ValueError(
            f"生成超时（{AGENT_DIALOGUE_TOTAL_TIMEOUT/60:.1f}分钟），"
            "请减少重写次数或稍后重试"
        )


async def _generate_with_agent_dialogue_impl(
    db_session: AsyncSession,
    system_prompt: str,
    user_prompt: str,
    user_id: int,
    temperature: float,
    timeout: float,
    project_id: Optional[str],
    chapter_number: Optional[int],
) -> str:
    """
    三Agent对话模式生成章节（实际实现）

    内部实现函数，由_generate_with_agent_dialogue包装调用
    """
    from ..config.agent_tools import NOVEL_AGENT_TOOLS
    from ..config.agent_prompts import get_agent_prompt
    from ..config.ai_function_config import get_function_config

    # ✅ 参数验证
    if not project_id:
        raise ValueError("三Agent对话模式需要project_id参数")
    if chapter_number is None:
        raise ValueError("三Agent对话模式需要chapter_number参数")

    start_time = time.time()
    logger.info(f"=== 三Agent对话模式开始：第{chapter_number}章 ===")

    llm_service = LLMService(db_session)
    config = get_function_config(AIFunctionType.CHAPTER_CONTENT_WRITING)
    provider = config.primary.provider
    model = config.primary.model
    
    # 对话历史（记录所有Agent的交互）
    conversation_history = []
    
    # ==================== 阶段1：思考Agent ====================
    logger.info("阶段1：思考Agent分析大纲并查询历史信息")
    planner_start = time.time()

    planner_result = await _call_planner_agent(
        llm_service=llm_service,
        provider=provider,
        model=model,
        user_prompt=user_prompt,
        user_id=user_id,
        temperature=PLANNER_TEMPERATURE,
        timeout=timeout,
        project_id=project_id,
        chapter_number=chapter_number,
    )

    logger.info(f"思考Agent完成，耗时: {time.time() - planner_start:.2f}秒")

    # ✅ 输出Planner的详细结果
    logger.info("=" * 80)
    logger.info("📋 思考Agent输出：")
    logger.info(f"  分析 (analysis): {planner_result.get('analysis', 'N/A')[:300]}...")
    logger.info(f"  规划 (plan): {planner_result.get('plan', 'N/A')[:300]}...")
    logger.info(f"  查询总结 (queries_summary): {planner_result.get('queries_summary', 'N/A')[:200]}...")
    logger.info(f"  给Writer的建议 (notes_for_writer): {planner_result.get('notes_for_writer', 'N/A')[:200]}...")
    logger.info("=" * 80)

    conversation_history.append({
        "agent": "planner",
        "content": planner_result,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    # ==================== 阶段2-4：写作↔审批循环 ====================
    logger.info("阶段2-4：写作Agent生成内容，审批Agent审核")

    final_content = None

    for iteration in range(MAX_REWRITE_ITERATIONS):
        logger.info(f"--- 写作迭代 {iteration + 1}/{MAX_REWRITE_ITERATIONS} ---")

        # 阶段2：写作Agent生成内容
        writer_start = time.time()
        writer_context = _build_writer_context(
            user_prompt=user_prompt,
            planner_result=planner_result,
            conversation_history=conversation_history,
            is_rewrite=(iteration > 0)
        )

        writer_result = await _call_writer_agent(
            llm_service=llm_service,
            provider=provider,
            model=model,
            writer_context=writer_context,
            user_id=user_id,
            temperature=WRITER_TEMPERATURE,
            timeout=timeout,
            project_id=project_id,
            chapter_number=chapter_number,
        )

        logger.info(f"写作Agent完成，耗时: {time.time() - writer_start:.2f}秒")

        # ✅ 输出Writer的详细结果
        full_content = writer_result.get("full_content", "")
        logger.info("=" * 80)
        logger.info(f"✍️ 写作Agent输出（迭代 {iteration + 1}）：")
        logger.info(f"  字数: {len(full_content)}")
        logger.info(f"  前500字预览:\n{full_content[:500]}...")
        logger.info(f"  创作说明 (writing_notes): {writer_result.get('writing_notes', 'N/A')[:300]}")
        logger.info("=" * 80)

        # ✅ 优化：只存储摘要，避免conversation_history膨胀
        writer_summary = {
            "writing_notes": writer_result.get("writing_notes", "")[:500],  # 只保留前500字
            "word_count": len(full_content),
            "preview": full_content[:200] + "..."  # 只保留前200字预览
        }
        conversation_history.append({
            "agent": "writer",
            "iteration": iteration + 1,
            "content": writer_summary,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # 阶段3：审批Agent审核
        reviewer_start = time.time()
        reviewer_context = _build_reviewer_context(
            writer_result=writer_result,
            conversation_history=conversation_history,
            user_prompt=user_prompt
        )

        reviewer_result = await _call_reviewer_agent(
            llm_service=llm_service,
            provider=provider,
            model=model,
            reviewer_context=reviewer_context,
            user_id=user_id,
            temperature=REVIEWER_TEMPERATURE,
            timeout=timeout,
        )

        logger.info(f"审批Agent完成，耗时: {time.time() - reviewer_start:.2f}秒")

        # ✅ 输出Reviewer的详细结果
        logger.info("=" * 80)
        logger.info(f"📝 审批Agent输出（迭代 {iteration + 1}）：")
        logger.info(f"  评分: {reviewer_result.get('score', 'N/A')}/{MIN_APPROVAL_SCORE}")
        logger.info(f"  是否通过: {'✅ 通过' if reviewer_result.get('approved', False) else '❌ 未通过'}")
        suggestions = reviewer_result.get('suggestions', [])
        if suggestions:
            logger.info(f"  修改建议 ({len(suggestions)}条):")
            for idx, suggestion in enumerate(suggestions[:5], 1):  # 只显示前5条
                logger.info(f"    {idx}. {suggestion[:150]}...")
        logger.info(f"  总体评价: {reviewer_result.get('overall_comment', 'N/A')[:200]}...")
        logger.info("=" * 80)

        conversation_history.append({
            "agent": "reviewer",
            "iteration": iteration + 1,
            "content": reviewer_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # 检查是否通过
        score = reviewer_result.get("score", 0)
        if reviewer_result.get("approved", False) and score >= MIN_APPROVAL_SCORE:
            logger.info(f"✅ 审批通过！评分：{score}/{MIN_APPROVAL_SCORE}")
            final_content = writer_result.get("full_content", "")
            break
        else:
            logger.warning(f"❌ 审批未通过，评分：{score}/{MIN_APPROVAL_SCORE}")
            logger.info(f"修改建议：{reviewer_result.get('suggestions', [])}")

            # 如果是最后一次迭代，使用当前版本
            if iteration == MAX_REWRITE_ITERATIONS - 1:
                logger.warning("已达最大重写次数，使用当前版本")
                final_content = writer_result.get("full_content", "")
                break
    
    if not final_content:
        raise ValueError("写作失败：无法生成章节内容")
    
    # ==================== 阶段5：总结Agent生成摘要 ====================
    logger.info("阶段5：总结Agent生成章节摘要")
    summarizer_start = time.time()

    summarizer_context = _build_summarizer_context(
        final_content=final_content,
        conversation_history=conversation_history,
        user_prompt=user_prompt
    )

    summarizer_result = await _call_summarizer_agent(
        llm_service=llm_service,
        provider=provider,
        model=model,
        summarizer_context=summarizer_context,
        user_id=user_id,
        temperature=SUMMARIZER_TEMPERATURE,
        timeout=timeout,
    )

    logger.info(f"总结Agent完成，耗时: {time.time() - summarizer_start:.2f}秒")

    # ✅ 输出Summarizer的详细结果
    logger.info("=" * 80)
    logger.info("📄 总结Agent输出：")
    logger.info(f"  章节摘要: {summarizer_result.get('summary', 'N/A')[:400]}...")
    logger.info("=" * 80)

    conversation_history.append({
        "agent": "summarizer",
        "content": summarizer_result,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    # ==================== 返回最终结果 ====================
    total_time = time.time() - start_time
    iterations = len([h for h in conversation_history if h["agent"] == "writer"])

    result = {
        "full_content": final_content,
        "summary": summarizer_result.get("summary", ""),
        "metadata": {
            "conversation_history": conversation_history,
            "iterations": iterations,
            "final_score": conversation_history[-2].get("content", {}).get("score", 0) if len(conversation_history) >= 2 else 0,
            "total_time_seconds": round(total_time, 2)
        }
    }

    logger.info(
        f"=== 三Agent对话完成 ===\n"
        f"  章节号: {chapter_number}\n"
        f"  迭代次数: {iterations}\n"
        f"  最终评分: {result['metadata']['final_score']}\n"
        f"  总耗时: {total_time:.2f}秒 ({total_time/60:.1f}分钟)"
    )

    return json.dumps(result, ensure_ascii=False)


# ==================== Agent调用辅助函数 ====================

async def _call_planner_agent(
    llm_service: LLMService,
    provider: str,
    model: str,
    user_prompt: str,
    user_id: int,
    temperature: float,
    timeout: float,
    project_id: str,
    chapter_number: int,
) -> Dict[str, Any]:
    """
    调用思考Agent

    上下文：所有章节摘要 + 前两章完整内容 + 当前章大纲
    任务：分析大纲，决定查询什么，调用工具查询
    """
    from ..config.agent_tools import NOVEL_AGENT_TOOLS

    # 从数据库读取prompt
    planner_prompt = await get_agent_prompt_from_db(llm_service.db_session, "planner", is_outline=False)

    messages = [
        {"role": "system", "content": planner_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # Agent可以调用工具查询，最多3轮
    for round_num in range(MAX_PLANNER_TOOL_ROUNDS):
        response_str = await llm_service.invoke(
            provider=provider,
            model=model,
            messages=messages,
            temperature=temperature,
            timeout=timeout,
            user_id=user_id,
            tools=NOVEL_AGENT_TOOLS,  # 提供查询工具
        )
        
        try:
            response = json.loads(response_str)
        except json.JSONDecodeError as e:
            # 不是JSON，说明是最终结果（或者是纯文本响应）
            logger.warning(
                f"思考Agent返回非JSON格式（第{round_num + 1}轮），"
                f"响应前200字: {response_str[:200]}"
            )
            return {"analysis": response_str}
        except Exception as e:
            logger.error(f"思考Agent处理响应时出错: {e}", exc_info=True)
            raise
        
        # 检查是否有工具调用
        if "tool_calls" in response and response["tool_calls"]:
            # 执行工具
            tool_results = await _execute_tools(
                db_session=llm_service.db_session,
                tool_calls=response["tool_calls"],
                project_id=project_id,
                chapter_number=chapter_number,
            )

            # 添加到对话
            messages.append({
                "role": "assistant",
                "content": response.get("content", ""),
                "tool_calls": response["tool_calls"]
            })

            # ✅ 修复：为每个tool_call添加单独的tool消息
            for tool_call, result in zip(response["tool_calls"], tool_results):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result  # 已经是字符串，不需要dumps
                })
        else:
            # 没有工具调用，返回结果
            return response
    
    # 3轮后返回最后的响应
    return {"analysis": "思考完成"}


async def _call_writer_agent(
    llm_service: LLMService,
    provider: str,
    model: str,
    writer_context: str,
    user_id: int,
    temperature: float,
    timeout: float,
    project_id: str,
    chapter_number: int,
) -> Dict[str, Any]:
    """
    调用写作Agent

    上下文：思考结果 + 查询结果 + 所有章节摘要 + 前两章 + 审批意见（如果是重写）
    任务：撰写章节内容
    """
    from ..config.agent_tools import NOVEL_AGENT_TOOLS

    # 从数据库读取prompt
    writer_prompt = await get_agent_prompt_from_db(llm_service.db_session, "writer", is_outline=False)

    messages = [
        {"role": "system", "content": writer_prompt},
        {"role": "user", "content": writer_context}
    ]

    # 写作Agent也可以调用工具（如果需要更多信息），最多2轮
    for round_num in range(MAX_WRITER_TOOL_ROUNDS):
        is_final_round = (round_num == 1)
        
        response_str = await llm_service.invoke(
            provider=provider,
            model=model,
            messages=messages,
            temperature=temperature,
            timeout=timeout,
            user_id=user_id,
            tools=None if is_final_round else NOVEL_AGENT_TOOLS,
            response_format="json_object" if is_final_round else None,
        )
        
        try:
            response = json.loads(response_str)
        except json.JSONDecodeError as e:
            # JSON解析失败，将原始响应作为内容（需要清理）
            logger.warning(
                f"写作Agent返回非JSON格式（第{round_num + 1}轮），"
                f"响应前200字: {response_str[:200]}"
            )
            cleaned_content = _clean_full_content(response_str, chapter_number=chapter_number, version_idx=1)
            return {"full_content": cleaned_content}
        except Exception as e:
            logger.error(f"写作Agent处理响应时出错: {e}", exc_info=True)
            raise
        
        # 检查是否有工具调用
        if "tool_calls" in response and response["tool_calls"] and not is_final_round:
            # 执行工具
            tool_results = await _execute_tools(
                db_session=llm_service.db_session,
                tool_calls=response["tool_calls"],
                project_id=project_id,
                chapter_number=chapter_number,
            )
            
            # 添加到对话
            messages.append({
                "role": "assistant",
                "content": response.get("content", ""),
                "tool_calls": response["tool_calls"]
            })
            messages.append({
                "role": "tool",
                "content": json.dumps(tool_results, ensure_ascii=False)
            })
        else:
            # ✅ 验证返回格式：必须包含full_content字段
            if "full_content" not in response or not response["full_content"]:
                logger.error(
                    f"❌ 写作Agent返回格式错误（第{round_num + 1}轮）：缺少full_content字段\n"
                    f"  返回的字段: {list(response.keys())}\n"
                    f"  这可能是LLM误解了要求，返回了错误的JSON格式（如planner格式）"
                )
                # 如果是第一轮且没有full_content，继续到第二轮强制JSON格式
                if round_num == 0:
                    logger.warning("⚠️ 将进入第2轮，强制JSON格式重新生成...")
                    continue
                else:
                    # 第二轮还是错误，返回错误信息
                    return {"full_content": f"生成失败：返回格式错误，收到的字段为 {list(response.keys())}，期望包含 full_content 字段"}

            # 清理full_content后返回
            response["full_content"] = _clean_full_content(
                response["full_content"],
                chapter_number=chapter_number,
                version_idx=1
            )
            return response

    return {"full_content": "生成失败：未能在2轮内生成有效内容"}


async def _call_reviewer_agent(
    llm_service: LLMService,
    provider: str,
    model: str,
    reviewer_context: str,
    user_id: int,
    temperature: float,
    timeout: float,
) -> Dict[str, Any]:
    """
    调用审批Agent

    上下文：写作内容 + 写作Agent的所有上下文
    任务：审核质量，返回通过/不通过 + 修改建议
    """
    # 从数据库读取prompt
    reviewer_prompt = await get_agent_prompt_from_db(llm_service.db_session, "reviewer", is_outline=False)

    messages = [
        {"role": "system", "content": reviewer_prompt},
        {"role": "user", "content": reviewer_context}
    ]

    response_str = await llm_service.invoke(
        provider=provider,
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
        user_id=user_id,
        response_format="json_object",  # 强制JSON格式
    )

    try:
        response = json.loads(response_str)
        return response
    except json.JSONDecodeError as e:
        # ✅ 解析失败，默认不通过（保证质量）
        logger.error(f"审批Agent返回非JSON格式: {e}, 原始响应前200字: {response_str[:200]}")
        return {
            "approved": False,
            "score": 0,
            "feedback": "审批系统错误：响应格式错误",
            "suggestions": ["审批Agent返回了非JSON格式的响应，请检查提示词或重试"],
            "issues": ["审批系统异常"]
        }
    except Exception as e:
        logger.error(f"审批Agent处理响应时出错: {e}", exc_info=True)
        return {
            "approved": False,
            "score": 0,
            "feedback": f"审批系统错误: {str(e)}",
            "suggestions": ["系统异常，请重试"],
            "issues": ["审批系统异常"]
        }


async def _call_summarizer_agent(
    llm_service: LLMService,
    provider: str,
    model: str,
    summarizer_context: str,
    user_id: int,
    temperature: float,
    timeout: float,
) -> Dict[str, Any]:
    """
    调用总结Agent

    上下文：对话历史 + 所有AI上下文 + 本章内容
    任务：生成精炼的章节摘要
    """
    # 从数据库读取prompt
    summarizer_prompt = await get_agent_prompt_from_db(llm_service.db_session, "summarizer", is_outline=False)

    messages = [
        {"role": "system", "content": summarizer_prompt},
        {"role": "user", "content": summarizer_context}
    ]

    response_str = await llm_service.invoke(
        provider=provider,
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
        user_id=user_id,
        response_format="json_object",
    )

    try:
        response = json.loads(response_str)
        return response
    except json.JSONDecodeError as e:
        logger.error(f"总结Agent返回非JSON格式: {e}, 原始响应前200字: {response_str[:200]}")
        return {"summary": "摘要生成失败"}
    except Exception as e:
        logger.error(f"总结Agent处理响应时出错: {e}", exc_info=True)
        return {"summary": f"摘要生成失败: {str(e)}"}


# ==================== 上下文构建辅助函数 ====================

def _build_writer_context(
    user_prompt: str,
    planner_result: Dict[str, Any],
    conversation_history: List[Dict[str, Any]],
    is_rewrite: bool
) -> str:
    """构建写作Agent的上下文"""
    context_parts = [
        "# 章节上下文（所有章节摘要 + 前两章完整内容 + 当前章大纲）",
        user_prompt,
        "",
        "# 思考Agent的分析和规划",
        json.dumps(planner_result, ensure_ascii=False, indent=2),
        "",
    ]
    
    if is_rewrite:
        # 如果是重写，添加上一次的审批意见
        last_review = None
        for item in reversed(conversation_history):
            if item["agent"] == "reviewer":
                last_review = item["content"]
                break
        
        if last_review:
            context_parts.extend([
                "# ⚠️ 审批Agent的修改意见",
                "上一版本存在以下问题，请根据建议修改：",
                json.dumps(last_review, ensure_ascii=False, indent=2),
                "",
                "请重新撰写，确保解决上述问题。",
                ""
            ])
    
    context_parts.append("# 请撰写章节正文（JSON格式：{\"full_content\": \"...\", \"writing_notes\": \"...\"}）")
    
    return "\n".join(context_parts)


def _build_reviewer_context(
    writer_result: Dict[str, Any],
    conversation_history: List[Dict[str, Any]],
    user_prompt: str
) -> str:
    """构建审批Agent的上下文"""
    context_parts = [
        "# 章节要求和背景",
        user_prompt,
        "",
        "# 写作Agent生成的内容",
        f"```markdown\n{writer_result.get('full_content', '')}\n```",
        "",
    ]
    
    if writer_result.get("writing_notes"):
        context_parts.extend([
            "# 写作Agent的创作说明",
            writer_result["writing_notes"],
            "",
        ])
    
    # 添加对话历史（让审批Agent了解整个过程）
    context_parts.extend([
        "# 对话历史摘要",
        f"已进行{len([h for h in conversation_history if h['agent'] == 'writer'])}轮写作",
        "",
        "# 请审核上述内容",
        "输出JSON格式：{\"approved\": true/false, \"score\": 0-100, \"issues\": [...], \"suggestions\": [...], \"feedback\": \"...\"}",
    ])
    
    return "\n".join(context_parts)


def _build_summarizer_context(
    final_content: str,
    conversation_history: List[Dict[str, Any]],
    user_prompt: str
) -> str:
    """构建总结Agent的上下文"""
    context_parts = [
        "# 章节完整内容",
        f"```markdown\n{final_content}\n```",
        "",
        "# 创作过程摘要",
        f"经过{len([h for h in conversation_history if h['agent'] == 'writer'])}轮写作打磨",
        "",
        "# 请生成精炼的章节摘要（JSON格式：{\"summary\": \"...\"}）",
        "要求：100-200字，抓住主要情节和冲突，避免流水账"
    ]

    return "\n".join(context_parts)


# ==================== 三Agent大纲生成模式 ====================

async def generate_outline_with_agents(
    db_session: AsyncSession,
    project_id: str,
    start_chapter: int,
    user_id: int,
    blueprint_dict: Dict[str, Any],
    completed_summaries: List[Dict[str, Any]],
    volumes_data: List[Dict[str, Any]],
    timeout: float = 600.0,
    planner_temperature: Optional[float] = None,
    writer_temperature: Optional[float] = None,
    reviewer_temperature: Optional[float] = None,
    min_score: Optional[int] = None,
    max_iterations: Optional[int] = None,
    planner_provider: Optional[str] = None,
    planner_model: Optional[str] = None,
    writer_provider: Optional[str] = None,
    writer_model: Optional[str] = None,
    reviewer_provider: Optional[str] = None,
    reviewer_model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    使用3Agent对话模式生成大纲（带总体超时控制）

    工作流程：
    1. 规划Agent：分析项目，规划章节结构
    2. 写作Agent：根据规划撰写详细大纲
    3. 审批Agent：审核大纲质量，提供修改意见
    4. 如果不通过：写作Agent重写（可多轮，最多3次）

    Args:
        db_session: 数据库会话
        project_id: 项目ID
        start_chapter: 起始章节号
        user_id: 用户ID
        blueprint_dict: 项目蓝图（包含题材、基调、目标读者等）
        completed_summaries: 已完成章节的摘要列表
        volumes_data: 分卷数据
        timeout: 超时时间（默认600秒）
        planner_temperature: 规划Agent温度（默认使用OUTLINE_PLANNER_TEMPERATURE）
        writer_temperature: 写作Agent温度（默认使用OUTLINE_WRITER_TEMPERATURE）
        reviewer_temperature: 审批Agent温度（默认使用OUTLINE_REVIEWER_TEMPERATURE）
        min_score: 最低通过分数（默认使用MIN_OUTLINE_SCORE）
        max_iterations: 最大重写次数（默认使用MAX_OUTLINE_ITERATIONS）

    Returns:
        生成的大纲数据（Dict格式，包含chapters列表和metadata）

    Raises:
        ValueError: 参数验证失败
        asyncio.TimeoutError: 如果总体超时
    """
    # ✅ 参数验证
    if not project_id:
        raise ValueError("project_id不能为空")
    if not isinstance(start_chapter, int) or start_chapter < 1:
        raise ValueError(f"start_chapter必须是大于0的整数，当前值：{start_chapter}")
    if not blueprint_dict:
        raise ValueError("blueprint_dict不能为空，请先创建项目蓝图")
    if not isinstance(user_id, int) or user_id < 1:
        raise ValueError(f"user_id必须是大于0的整数，当前值：{user_id}")

    try:
        result = await asyncio.wait_for(
            _generate_outline_with_agents_impl(
                db_session=db_session,
                project_id=project_id,
                start_chapter=start_chapter,
                user_id=user_id,
                blueprint_dict=blueprint_dict,
                completed_summaries=completed_summaries,
                volumes_data=volumes_data,
                planner_temperature=planner_temperature,
                writer_temperature=writer_temperature,
                reviewer_temperature=reviewer_temperature,
                min_score=min_score,
                max_iterations=max_iterations,
                planner_provider=planner_provider,
                planner_model=planner_model,
                writer_provider=writer_provider,
                writer_model=writer_model,
                reviewer_provider=reviewer_provider,
                reviewer_model=reviewer_model,
            ),
            timeout=OUTLINE_DIALOGUE_TOTAL_TIMEOUT
        )
        return result
    except asyncio.TimeoutError:
        logger.error(f"3Agent大纲生成超时（{OUTLINE_DIALOGUE_TOTAL_TIMEOUT}秒）")
        raise ValueError(
            f"大纲生成超时（{OUTLINE_DIALOGUE_TOTAL_TIMEOUT/60:.1f}分钟），"
            "请稍后重试"
        )


async def _generate_outline_with_agents_impl(
    db_session: AsyncSession,
    project_id: str,
    start_chapter: int,
    user_id: int,
    blueprint_dict: Dict[str, Any],
    completed_summaries: List[Dict[str, Any]],
    volumes_data: List[Dict[str, Any]],
    planner_temperature: Optional[float] = None,
    writer_temperature: Optional[float] = None,
    reviewer_temperature: Optional[float] = None,
    min_score: Optional[int] = None,
    max_iterations: Optional[int] = None,
    planner_provider: Optional[str] = None,
    planner_model: Optional[str] = None,
    writer_provider: Optional[str] = None,
    writer_model: Optional[str] = None,
    reviewer_provider: Optional[str] = None,
    reviewer_model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    三Agent对话模式生成大纲（实际实现）

    内部实现函数，由generate_outline_with_agents包装调用
    """
    from ..config.outline_agent_prompts import get_outline_agent_prompt
    from ..config.ai_function_config import get_function_config

    start_time = time.time()
    logger.info(f"=== 3Agent大纲生成模式开始：从第{start_chapter}章开始 ===")

    llm_service = LLMService(db_session)
    config = get_function_config(AIFunctionType.OUTLINE_GENERATION)
    default_provider = config.primary.provider
    default_model = config.primary.model

    # ✅ 使用自定义配置或默认值
    planner_temp = planner_temperature if planner_temperature is not None else OUTLINE_PLANNER_TEMPERATURE
    writer_temp = writer_temperature if writer_temperature is not None else OUTLINE_WRITER_TEMPERATURE
    reviewer_temp = reviewer_temperature if reviewer_temperature is not None else OUTLINE_REVIEWER_TEMPERATURE
    min_score_threshold = min_score if min_score is not None else MIN_OUTLINE_SCORE
    max_rewrite_iterations = max_iterations if max_iterations is not None else MAX_OUTLINE_ITERATIONS

    # ✅ 设置每个Agent的LLM配置
    planner_llm_provider = planner_provider if planner_provider else default_provider
    planner_llm_model = planner_model if planner_model else default_model
    writer_llm_provider = writer_provider if writer_provider else default_provider
    writer_llm_model = writer_model if writer_model else default_model
    reviewer_llm_provider = reviewer_provider if reviewer_provider else default_provider
    reviewer_llm_model = reviewer_model if reviewer_model else default_model

    logger.info(f"配置参数: planner_temp={planner_temp}, writer_temp={writer_temp}, "
                f"reviewer_temp={reviewer_temp}, min_score={min_score_threshold}, max_iterations={max_rewrite_iterations}")
    logger.info(f"LLM配置: Planner={planner_llm_provider}/{planner_llm_model}, "
                f"Writer={writer_llm_provider}/{writer_llm_model}, "
                f"Reviewer={reviewer_llm_provider}/{reviewer_llm_model}")

    # 对话历史（记录所有Agent的交互）
    conversation_history = []

    # 构建初始上下文
    context = _build_outline_initial_context(
        blueprint_dict=blueprint_dict,
        completed_summaries=completed_summaries,
        volumes_data=volumes_data,
        start_chapter=start_chapter,
    )

    # ==================== 阶段1：规划Agent ====================
    logger.info("阶段1：规划Agent分析项目并规划章节结构")
    planner_start = time.time()

    planner_result = await _call_outline_planner_agent(
        llm_service=llm_service,
        provider=planner_llm_provider,
        model=planner_llm_model,
        context=context,
        user_id=user_id,
        timeout=120.0,
        temperature=planner_temp,
    )

    logger.info(f"规划Agent完成，耗时: {time.time() - planner_start:.2f}秒")

    conversation_history.append({
        "agent": "outline_planner",
        "content": planner_result,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    # ==================== 阶段2-3：写作↔审批循环 ====================
    logger.info("阶段2-3：写作Agent撰写大纲，审批Agent审核")

    final_outline = None
    final_score = 0

    for iteration in range(max_rewrite_iterations):
        logger.info(f"--- 大纲写作迭代 {iteration + 1}/{max_rewrite_iterations} ---")

        # 阶段2：写作Agent撰写大纲
        writer_start = time.time()
        writer_context = _build_outline_writer_context(
            initial_context=context,
            planner_result=planner_result,
            conversation_history=conversation_history,
            is_rewrite=(iteration > 0)
        )

        writer_result = await _call_outline_writer_agent(
            llm_service=llm_service,
            provider=writer_llm_provider,
            model=writer_llm_model,
            context=writer_context,
            user_id=user_id,
            timeout=180.0,
            temperature=writer_temp,
        )

        logger.info(f"写作Agent完成，耗时: {time.time() - writer_start:.2f}秒")

        conversation_history.append({
            "agent": "outline_writer",
            "iteration": iteration + 1,
            "content": {
                "chapters_count": len(writer_result.get("chapters", [])),
                "notes": writer_result.get("notes", "")
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # 阶段3：审批Agent审核
        reviewer_start = time.time()
        reviewer_context = _build_outline_reviewer_context(
            writer_result=writer_result,
            conversation_history=conversation_history,
            initial_context=context
        )

        reviewer_result = await _call_outline_reviewer_agent(
            llm_service=llm_service,
            provider=reviewer_llm_provider,
            model=reviewer_llm_model,
            context=reviewer_context,
            user_id=user_id,
            timeout=120.0,
            temperature=reviewer_temp,
        )

        logger.info(f"审批Agent完成，耗时: {time.time() - reviewer_start:.2f}秒")

        conversation_history.append({
            "agent": "outline_reviewer",
            "iteration": iteration + 1,
            "content": reviewer_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # 检查是否通过
        score = reviewer_result.get("score", 0)
        final_score = score

        if reviewer_result.get("approved", False) and score >= min_score_threshold:
            logger.info(f"✅ 大纲审批通过！评分：{score}/{min_score_threshold}")
            final_outline = writer_result
            break
        else:
            logger.warning(f"❌ 大纲审批未通过，评分：{score}/{min_score_threshold}")
            logger.info(f"修改建议：{reviewer_result.get('suggestions', [])}")

            # 如果是最后一次迭代，使用当前版本
            if iteration == max_rewrite_iterations - 1:
                logger.warning("已达最大重写次数，使用当前版本")
                final_outline = writer_result
                break

    if not final_outline or not final_outline.get("chapters"):
        raise ValueError("大纲生成失败：无法生成有效的章节大纲")

    # ==================== 返回最终结果 ====================
    total_time = time.time() - start_time
    iterations = len([h for h in conversation_history if h["agent"] == "outline_writer"])

    # ✅ 返回与传统模式兼容的完整数据结构
    result = {
        "volume_title": final_outline.get("volume_title", ""),
        "chapters": final_outline.get("chapters", []),
        "characters": final_outline.get("characters", []),
        "relationships": final_outline.get("relationships", []),
        "world_setting": final_outline.get("world_setting", {}),
        "metadata": {
            "conversation_history": conversation_history,
            "iterations": iterations,
            "final_score": final_score,
            "total_time": total_time,
            "planner_analysis": planner_result.get("analysis", ""),
            "generation_mode": "agent_dialogue",  # 标记生成模式
        }
    }

    logger.info(
        f"=== 3Agent大纲生成完成 ===\n"
        f"  起始章节: {start_chapter}\n"
        f"  生成章节数: {len(final_outline.get('chapters', []))}\n"
        f"  迭代次数: {iterations}\n"
        f"  最终评分: {final_score}\n"
        f"  总耗时: {total_time:.2f}秒 ({total_time/60:.1f}分钟)"
    )

    return result


# ==================== 大纲Agent调用辅助函数 ====================

async def _call_outline_planner_agent(
    llm_service: LLMService,
    provider: str,
    model: str,
    context: str,
    user_id: int,
    timeout: float,
    temperature: float,
) -> Dict[str, Any]:
    """
    调用大纲规划Agent

    上下文：项目蓝图 + 已完成章节摘要 + 分卷信息
    任务：分析项目，规划章节结构和节奏
    """
    # 从数据库读取prompt
    planner_prompt = await get_agent_prompt_from_db(llm_service.db_session, "planner", is_outline=True)

    messages = [
        {"role": "system", "content": planner_prompt},
        {"role": "user", "content": context}
    ]

    response_str = await llm_service.invoke(
        provider=provider,
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
        user_id=user_id,
        response_format="json_object",
    )

    try:
        response = json.loads(response_str)
        return response
    except json.JSONDecodeError as e:
        logger.error(
            f"规划Agent返回非JSON格式，响应前200字: {response_str[:200]}",
            exc_info=True
        )
        # 返回默认结构
        return {
            "analysis": response_str[:500],
            "chapter_plan": {"total_chapters": 50, "structure": "线性", "key_points": []},
            "rhythm": "均衡节奏",
            "notes": "解析失败，使用默认规划"
        }


async def _call_outline_writer_agent(
    llm_service: LLMService,
    provider: str,
    model: str,
    context: str,
    user_id: int,
    timeout: float,
    temperature: float,
) -> Dict[str, Any]:
    """
    调用大纲撰写Agent

    任务：根据规划方案撰写详细的章节大纲（标题+摘要）
    """
    # 从数据库读取prompt
    writer_prompt = await get_agent_prompt_from_db(llm_service.db_session, "writer", is_outline=True)

    messages = [
        {"role": "system", "content": writer_prompt},
        {"role": "user", "content": context}
    ]

    response_str = await llm_service.invoke(
        provider=provider,
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
        user_id=user_id,
        response_format="json_object",
    )

    try:
        response = json.loads(response_str)
        return response
    except json.JSONDecodeError as e:
        logger.error(
            f"写作Agent返回非JSON格式，响应前200字: {response_str[:200]}",
            exc_info=True
        )
        raise ValueError("大纲撰写失败：返回格式错误")


async def _call_outline_reviewer_agent(
    llm_service: LLMService,
    provider: str,
    model: str,
    context: str,
    user_id: int,
    timeout: float,
    temperature: float,
) -> Dict[str, Any]:
    """
    调用大纲审核Agent

    任务：审核大纲质量，提供评分和修改建议
    """
    # 从数据库读取prompt
    reviewer_prompt = await get_agent_prompt_from_db(llm_service.db_session, "reviewer", is_outline=True)

    messages = [
        {"role": "system", "content": reviewer_prompt},
        {"role": "user", "content": context}
    ]

    response_str = await llm_service.invoke(
        provider=provider,
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
        user_id=user_id,
        response_format="json_object",
    )

    try:
        response = json.loads(response_str)
        # ✅ 确保默认行为安全：解析失败时不通过
        if "approved" not in response:
            response["approved"] = False
        if "score" not in response:
            response["score"] = 0
        return response
    except json.JSONDecodeError as e:
        logger.error(
            f"审批Agent返回非JSON格式，响应前200字: {response_str[:200]}",
            exc_info=True
        )
        # 返回不通过的默认结果
        return {
            "approved": False,
            "score": 0,
            "issues": ["返回格式错误，无法解析"],
            "suggestions": ["请重新生成"],
            "feedback": "审批失败：返回格式错误"
        }


# ==================== 大纲生成上下文构建函数 ====================

def _build_outline_initial_context(
    blueprint_dict: Dict[str, Any],
    completed_summaries: List[Dict[str, Any]],
    volumes_data: List[Dict[str, Any]],
    start_chapter: int,
) -> str:
    """构建大纲生成的初始上下文"""
    context_parts = [
        "# 项目蓝图",
        f"题材：{blueprint_dict.get('genre', '未指定')}",
        f"基调：{blueprint_dict.get('tone', '未指定')}",
        f"目标读者：{blueprint_dict.get('target_audience', '未指定')}",
        "",
        "# 分卷信息",
    ]

    for vol in volumes_data:
        context_parts.append(
            f"- {vol.get('title', '未命名卷')}：{vol.get('description', '无描述')}"
        )

    context_parts.extend([
        "",
        f"# 当前进度",
        f"已完成章节：{len(completed_summaries)}章",
        f"下一批大纲起始章节：第{start_chapter}章",
        "",
    ])

    if completed_summaries:
        context_parts.extend([
            "# 已完成章节摘要（最近10章）",
        ])
        for summary in completed_summaries[-10:]:
            context_parts.append(
                f"第{summary.get('chapter_number', '?')}章 - {summary.get('title', '未命名')}：{summary.get('summary', '')}"
            )
    else:
        context_parts.append("（这是项目的第一批大纲）")

    return "\n".join(context_parts)


def _build_outline_writer_context(
    initial_context: str,
    planner_result: Dict[str, Any],
    conversation_history: List[Dict[str, Any]],
    is_rewrite: bool,
) -> str:
    """构建大纲写作Agent的上下文"""
    context_parts = [
        initial_context,
        "",
        "# 规划方案",
        f"## 项目分析",
        planner_result.get("analysis", ""),
        "",
        f"## 卷名建议",
        f"建议卷名：{planner_result.get('volume_title_suggestion', '未提供')}",
        f"核心主题：{planner_result.get('volume_theme', '未提供')}",
        "",
        f"## 章节规划",
        f"总章节数：{planner_result.get('chapter_plan', {}).get('total_chapters', 50)}",
        f"本批生成：{planner_result.get('chapter_plan', {}).get('chapters_to_generate', 30)}章",
        f"结构：{planner_result.get('chapter_plan', {}).get('structure', '线性')}",
        "",
        f"## 关键节点",
    ]

    for point in planner_result.get("chapter_plan", {}).get("key_points", []):
        context_parts.append(f"- {point}")

    # 添加世界观扩展
    world_expansion = planner_result.get("world_expansion", {})
    if world_expansion:
        context_parts.extend([
            "",
            f"## 世界观扩展",
        ])
        if world_expansion.get("new_locations"):
            context_parts.append(f"新地点：{', '.join(world_expansion.get('new_locations', []))}")
        if world_expansion.get("new_forces"):
            context_parts.append(f"新势力：{', '.join(world_expansion.get('new_forces', []))}")
        if world_expansion.get("new_concepts"):
            context_parts.append(f"新概念：{', '.join(world_expansion.get('new_concepts', []))}")

    # 添加角色发展
    character_dev = planner_result.get("character_development", {})
    if character_dev:
        context_parts.extend([
            "",
            f"## 角色发展",
        ])
        if character_dev.get("main_characters"):
            context_parts.append("主要角色：")
            for char in character_dev.get("main_characters", []):
                context_parts.append(f"- {char}")
        if character_dev.get("new_characters"):
            context_parts.append("新增角色：")
            for char in character_dev.get("new_characters", []):
                context_parts.append(f"- {char}")

    context_parts.extend([
        "",
        f"## 节奏安排",
        planner_result.get("rhythm", ""),
        "",
        f"## 规划说明",
        planner_result.get("notes", ""),
    ])

    if is_rewrite:
        # 添加上一轮的审批意见
        last_review = None
        for h in reversed(conversation_history):
            if h["agent"] == "outline_reviewer":
                last_review = h["content"]
                break

        if last_review:
            context_parts.extend([
                "",
                "# 修改要求（上一轮审批意见）",
                f"评分：{last_review.get('score', 0)}/100",
                "",
                "## 问题",
            ])
            for issue in last_review.get("issues", []):
                context_parts.append(f"- {issue}")

            context_parts.append("\n## 修改建议")
            for suggestion in last_review.get("suggestions", []):
                context_parts.append(f"- {suggestion}")

    context_parts.append("\n# 请撰写详细的章节大纲")

    return "\n".join(context_parts)


def _build_outline_reviewer_context(
    writer_result: Dict[str, Any],
    conversation_history: List[Dict[str, Any]],
    initial_context: str
) -> str:
    """构建大纲审核Agent的上下文"""
    context_parts = [
        "# 项目背景",
        initial_context,
        "",
        "# 待审核的大纲",
        f"章节数量：{len(writer_result.get('chapters', []))}",
        "",
    ]

    for chapter in writer_result.get("chapters", []):
        context_parts.append(
            f"## 第{chapter.get('chapter_number', '?')}章：{chapter.get('title', '未命名')}"
        )
        context_parts.append(f"{chapter.get('summary', '')}")
        context_parts.append("")

    context_parts.extend([
        "# 创作说明",
        writer_result.get("notes", ""),
        "",
        "# 对话历史摘要",
        f"已进行{len([h for h in conversation_history if h['agent'] == 'outline_writer'])}轮大纲撰写",
        "",
        "# 请审核上述大纲",
        "输出JSON格式：{\"approved\": true/false, \"score\": 0-100, \"strengths\": [...], \"issues\": [...], \"suggestions\": [...], \"feedback\": \"...\"}",
    ])

    return "\n".join(context_parts)
