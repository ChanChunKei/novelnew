import json
import logging
from typing import Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.novel import (
    Blueprint,
    BlueprintGenerationResponse,
    BlueprintPatch,
    BlueprintRegenerateRequest,
    Chapter as ChapterSchema,
    ConverseRequest,
    ConverseResponse,
    NovelProject as NovelProjectSchema,
    NovelProjectSummary,
    NovelSectionResponse,
    NovelSectionType,
)
from ...schemas.user import UserInDB
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...utils.json_utils import remove_think_tags, sanitize_json_like_text, unwrap_markdown_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/novels", tags=["Novels"])

JSON_RESPONSE_INSTRUCTION = """
IMPORTANT: 你的回复必须是合法的 JSON 对象，并严格包含以下字段：
{
  "ai_message": "string",
  "ui_control": {
    "type": "single_choice | text_input | info_display",
    "options": [
      {"id": "option_1", "label": "string"}
    ],
    "placeholder": "string"
  },
  "conversation_state": {},
  "is_complete": false
}
不要输出额外的文本或解释。
"""


def _ensure_prompt(prompt: str | None, name: str) -> str:
    if not prompt:
        raise HTTPException(status_code=500, detail=f"未配置名为 {name} 的提示词，请联系管理员")
    return prompt


@router.post("", response_model=NovelProjectSchema, status_code=status.HTTP_201_CREATED)
async def create_novel(
    title: str = Body(...),
    initial_prompt: str = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """为当前用户创建一个新的小说项目。"""
    novel_service = NovelService(session)
    project = await novel_service.create_project(current_user.id, title, initial_prompt)
    logger.info("用户 %s 创建项目 %s", current_user.id, project.id)
    return await novel_service.get_project_schema(project.id, current_user.id)


@router.get("", response_model=List[NovelProjectSummary])
async def list_novels(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[NovelProjectSummary]:
    """列出用户的全部小说项目摘要信息。"""
    novel_service = NovelService(session)
    projects = await novel_service.list_projects_for_user(current_user.id)
    logger.info("用户 %s 获取项目列表，共 %s 个", current_user.id, len(projects))
    return projects


@router.get("/{project_id}", response_model=NovelProjectSchema)
async def get_novel(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    logger.info("用户 %s 查询项目 %s", current_user.id, project_id)
    return await novel_service.get_project_schema(project_id, current_user.id)


@router.put("/{project_id}/title")
async def update_project_title(
    project_id: str,
    new_title: str = Body(..., embed=True, description="新的项目标题"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict:
    """修改项目标题

    当番茄小说书名已存在时，可以通过此接口修改本地项目书名，
    然后重新尝试上传。

    Args:
        project_id: 项目ID
        new_title: 新的项目标题

    Returns:
        修改结果
    """
    novel_service = NovelService(session)
    logger.info("用户 %s 修改项目 %s 标题为: %s", current_user.id, project_id, new_title)

    await novel_service.update_project_title(project_id, current_user.id, new_title)

    return {
        "success": True,
        "message": f"项目标题已成功修改为: {new_title}",
        "new_title": new_title
    }


@router.put("/{project_id}/fanqie-book-id")
async def update_fanqie_book_id(
    project_id: str,
    fanqie_book_id: str = Body(..., embed=True, description="番茄小说书籍ID"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict:
    """设置番茄小说book_id

    手动指定项目对应的番茄小说书籍ID，避免自动查找失败。

    获取book_id的方法：
    1. 登录番茄小说作家后台
    2. 进入书籍的"章节管理"页面
    3. URL中的数字就是book_id，例如：
       https://fanqienovel.com/main/writer/chapter-manage/123456789
       这里的 123456789 就是book_id

    Args:
        project_id: 项目ID
        fanqie_book_id: 番茄小说书籍ID

    Returns:
        设置结果
    """
    novel_service = NovelService(session)
    logger.info("用户 %s 设置项目 %s 的番茄book_id为: %s", current_user.id, project_id, fanqie_book_id)

    await novel_service.update_fanqie_book_id(project_id, current_user.id, fanqie_book_id)

    return {
        "success": True,
        "message": f"番茄book_id已成功设置为: {fanqie_book_id}",
        "fanqie_book_id": fanqie_book_id
    }


@router.get("/{project_id}/sections/{section}", response_model=NovelSectionResponse)
async def get_novel_section(
    project_id: str,
    section: NovelSectionType,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelSectionResponse:
    novel_service = NovelService(session)
    logger.info("用户 %s 获取项目 %s 的 %s 区段", current_user.id, project_id, section)
    return await novel_service.get_section_data(project_id, current_user.id, section)


@router.get("/{project_id}/chapters/{chapter_number}", response_model=ChapterSchema)
async def get_chapter(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterSchema:
    novel_service = NovelService(session)
    logger.info("用户 %s 获取项目 %s 第 %s 章", current_user.id, project_id, chapter_number)
    return await novel_service.get_chapter_schema(project_id, current_user.id, chapter_number)


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_novels(
    project_ids: List[str] = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, str]:
    novel_service = NovelService(session)
    await novel_service.delete_projects(project_ids, current_user.id)
    logger.info("用户 %s 删除项目 %s", current_user.id, project_ids)
    return {"status": "success", "message": f"成功删除 {len(project_ids)} 个项目"}


@router.post("/{project_id}/concept/converse", response_model=ConverseResponse)
async def converse_with_concept(
    project_id: str,
    request: ConverseRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ConverseResponse:
    """与概念设计师（LLM）进行对话，引导蓝图筹备。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    history_records = await novel_service.list_conversations(project_id)
    logger.info(
        "项目 %s 概念对话请求，用户 %s，历史记录 %s 条",
        project_id,
        current_user.id,
        len(history_records),
    )
    # 构建对话历史（不包含当前用户输入）
    conversation_history = [
        {"role": record.role, "content": record.content}
        for record in history_records
    ]
    user_content = json.dumps(request.user_input, ensure_ascii=False)

    system_prompt = _ensure_prompt(await prompt_service.get_prompt("concept"), "concept")
    system_prompt = f"{system_prompt}\n{JSON_RESPONSE_INSTRUCTION}"

    # 使用AI Orchestrator进行概念对话，传入完整历史上下文
    from app.services.ai_orchestrator_helper import concept_dialogue

    llm_response = await concept_dialogue(
        db_session=session,
        system_prompt=system_prompt,
        user_message=user_content,
        conversation_history=conversation_history,  # ✅ 传递历史上下文
        user_id=current_user.id,
        temperature=0.8,
        timeout=240.0,
    )

    llm_response = remove_think_tags(llm_response)

    try:
        normalized = unwrap_markdown_json(llm_response)
        sanitized = sanitize_json_like_text(normalized)
        parsed = json.loads(sanitized)
    except json.JSONDecodeError as exc:
        logger.exception(
            "Failed to parse concept converse response: project_id=%s user_id=%s error=%s\nOriginal response: %s\nNormalized: %s\nSanitized: %s",
            project_id,
            current_user.id,
            exc,
            llm_response[:1000],
            normalized[:1000] if 'normalized' in locals() else "N/A",
            sanitized[:1000] if 'sanitized' in locals() else "N/A",
        )
        raise HTTPException(
            status_code=500,
            detail=f"概念对话失败，AI 返回的内容格式不正确。请重试或联系管理员。错误详情: {str(exc)}"
        ) from exc

    await novel_service.append_conversation(project_id, "user", user_content)
    await novel_service.append_conversation(project_id, "assistant", normalized)

    logger.info("项目 %s 概念对话完成，is_complete=%s", project_id, parsed.get("is_complete"))

    if parsed.get("is_complete"):
        parsed["ready_for_blueprint"] = True

    parsed.setdefault("conversation_state", parsed.get("conversation_state", {}))
    return ConverseResponse(**parsed)


@router.post("/{project_id}/blueprint/generate", response_model=BlueprintGenerationResponse)
async def generate_blueprint(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BlueprintGenerationResponse:
    """根据完整对话生成可执行的小说蓝图。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("项目 %s 开始生成蓝图", project_id)

    history_records = await novel_service.list_conversations(project_id)
    if not history_records:
        logger.warning("项目 %s 缺少对话历史，无法生成蓝图", project_id)
        raise HTTPException(status_code=400, detail="缺少对话历史，请先完成概念对话后再生成蓝图")

    formatted_history: List[Dict[str, str]] = []
    for record in history_records:
        role = record.role
        content = record.content
        if not role or not content:
            continue
        try:
            normalized = unwrap_markdown_json(content)
            data = json.loads(normalized)
            if role == "user":
                user_value = data.get("value", data)
                if isinstance(user_value, str):
                    formatted_history.append({"role": "user", "content": user_value})
            elif role == "assistant":
                ai_message = data.get("ai_message") if isinstance(data, dict) else None
                if ai_message:
                    formatted_history.append({"role": "assistant", "content": ai_message})
        except (json.JSONDecodeError, AttributeError):
            continue

    if not formatted_history:
        logger.warning("项目 %s 对话历史格式异常，无法提取有效内容", project_id)
        raise HTTPException(
            status_code=400,
            detail="无法从历史对话中提取有效内容，请检查对话历史格式或重新进行概念对话"
        )

    system_prompt = _ensure_prompt(await prompt_service.get_prompt("screenwriting"), "screenwriting")

    # 使用AI Orchestrator生成蓝图，传入完整对话历史
    from app.services.ai_orchestrator_helper import generate_blueprint as generate_blueprint_helper

    blueprint_raw = await generate_blueprint_helper(
        db_session=session,
        system_prompt=system_prompt,
        conversation_history=formatted_history,  # ✅ 传递完整对话历史
        user_id=current_user.id,
        temperature=0.3,
        timeout=480.0,
    )

    # ✅ 检查 AI 响应是否为空
    if not blueprint_raw:
        logger.error("项目 %s 蓝图生成失败: AI 返回空响应", project_id)
        raise HTTPException(
            status_code=500,
            detail="蓝图生成失败，AI 未返回任何内容。请检查 AI 配置或重试。"
        )

    blueprint_raw = remove_think_tags(blueprint_raw)

    blueprint_normalized = unwrap_markdown_json(blueprint_raw)
    blueprint_sanitized = sanitize_json_like_text(blueprint_normalized)

    # ✅ 检查处理后的结果是否为空
    if not blueprint_sanitized:
        logger.error(
            "项目 %s 蓝图生成失败: 处理后为空\n原始响应: %s\n标准化后: %s",
            project_id,
            blueprint_raw[:500] if blueprint_raw else "None",
            blueprint_normalized[:500] if blueprint_normalized else "None",
        )
        raise HTTPException(
            status_code=500,
            detail="蓝图生成失败，AI 返回的内容无法解析。请重试或联系管理员。"
        )

    try:
        blueprint_data = json.loads(blueprint_sanitized)
    except json.JSONDecodeError as exc:
        logger.error(
            "项目 %s 蓝图生成 JSON 解析失败: %s\n原始响应: %s\n标准化后: %s\n清洗后: %s",
            project_id,
            exc,
            blueprint_raw[:500] if blueprint_raw else "None",
            blueprint_normalized[:500] if blueprint_normalized else "None",
            blueprint_sanitized[:500] if blueprint_sanitized else "None",
        )
        raise HTTPException(
            status_code=500,
            detail=f"蓝图生成失败，AI 返回的内容格式不正确。请重试或联系管理员。错误详情: {str(exc)}"
        ) from exc

    # 不再限制章节大纲数量，让 AI 自主决定
    chapter_outline = blueprint_data.get("chapter_outline", [])
    logger.info(
        f"项目 {project_id} AI 生成了 {len(chapter_outline)} 章大纲"
    )

    blueprint = Blueprint(**blueprint_data)
    await novel_service.replace_blueprint(project_id, blueprint)
    if blueprint.title:
        project.title = blueprint.title
        project.status = "blueprint_ready"
        await session.commit()
        logger.info("项目 %s 更新标题为 %s，并标记为 blueprint_ready", project_id, blueprint.title)

    ai_message = (
        "太棒了！我已经根据我们的对话整理出完整的小说蓝图。请确认是否进入写作阶段，或提出修改意见。"
    )
    return BlueprintGenerationResponse(blueprint=blueprint, ai_message=ai_message)


@router.post("/{project_id}/blueprint/regenerate", response_model=BlueprintGenerationResponse)
async def regenerate_blueprint(
    project_id: str,
    request: BlueprintRegenerateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BlueprintGenerationResponse:
    """根据用户补充的信息重新生成蓝图。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("项目 %s 开始重新生成蓝图，补充信息: %s", project_id, request.additional_feedback[:100])

    # 获取原有的对话历史
    history_records = await novel_service.list_conversations(project_id)
    if not history_records:
        logger.warning("项目 %s 缺少对话历史，无法重新生成蓝图", project_id)
        raise HTTPException(status_code=400, detail="缺少对话历史，请先完成概念对话后再生成蓝图")

    # 格式化对话历史
    formatted_history: List[Dict[str, str]] = []
    for record in history_records:
        role = record.role
        content = record.content
        if not role or not content:
            continue
        try:
            normalized = unwrap_markdown_json(content)
            data = json.loads(normalized)
            if role == "user":
                user_value = data.get("value", data)
                if isinstance(user_value, str):
                    formatted_history.append({"role": "user", "content": user_value})
            elif role == "assistant":
                ai_message = data.get("ai_message") if isinstance(data, dict) else None
                if ai_message:
                    formatted_history.append({"role": "assistant", "content": ai_message})
        except (json.JSONDecodeError, AttributeError):
            continue

    if not formatted_history:
        logger.warning("项目 %s 对话历史格式异常，无法提取有效内容", project_id)
        raise HTTPException(
            status_code=400,
            detail="无法从历史对话中提取有效内容，请检查对话历史格式或重新进行概念对话"
        )

    # ✅ 添加用户的补充信息作为新的用户消息
    formatted_history.append({
        "role": "user",
        "content": f"根据之前的对话和已生成的蓝图，我想补充以下信息，请重新生成蓝图：\n\n{request.additional_feedback}"
    })

    system_prompt = _ensure_prompt(await prompt_service.get_prompt("screenwriting"), "screenwriting")

    # 使用AI Orchestrator重新生成蓝图
    from app.services.ai_orchestrator_helper import generate_blueprint as generate_blueprint_helper

    blueprint_raw = await generate_blueprint_helper(
        db_session=session,
        system_prompt=system_prompt,
        conversation_history=formatted_history,  # ✅ 传递包含补充信息的完整对话历史
        user_id=current_user.id,
        temperature=0.3,
        timeout=480.0,
    )

    # ✅ 检查 AI 响应是否为空
    if not blueprint_raw:
        logger.error("项目 %s 蓝图重新生成失败: AI 返回空响应", project_id)
        raise HTTPException(
            status_code=500,
            detail="蓝图重新生成失败，AI 未返回任何内容。请检查 AI 配置或重试。"
        )

    blueprint_raw = remove_think_tags(blueprint_raw)
    blueprint_normalized = unwrap_markdown_json(blueprint_raw)
    blueprint_sanitized = sanitize_json_like_text(blueprint_normalized)

    # ✅ 检查处理后的结果是否为空
    if not blueprint_sanitized:
        logger.error(
            "项目 %s 蓝图重新生成失败: 处理后为空\n原始响应: %s\n标准化后: %s",
            project_id,
            blueprint_raw[:500] if blueprint_raw else "None",
            blueprint_normalized[:500] if blueprint_normalized else "None",
        )
        raise HTTPException(
            status_code=500,
            detail="蓝图重新生成失败，AI 返回的内容无法解析。请重试或联系管理员。"
        )

    try:
        blueprint_data = json.loads(blueprint_sanitized)
    except json.JSONDecodeError as exc:
        logger.error(
            "项目 %s 蓝图重新生成 JSON 解析失败: %s\n原始响应: %s\n标准化后: %s\n清洗后: %s",
            project_id,
            exc,
            blueprint_raw[:500] if blueprint_raw else "None",
            blueprint_normalized[:500] if blueprint_normalized else "None",
            blueprint_sanitized[:500] if blueprint_sanitized else "None",
        )
        raise HTTPException(
            status_code=500,
            detail=f"蓝图重新生成失败，AI 返回的内容格式不正确。请重试或联系管理员。错误详情: {str(exc)}"
        ) from exc

    chapter_outline = blueprint_data.get("chapter_outline", [])
    logger.info(
        f"项目 {project_id} AI 重新生成了 {len(chapter_outline)} 章大纲"
    )

    # 保存新蓝图
    blueprint = Blueprint(**blueprint_data)
    await novel_service.replace_blueprint(project_id, blueprint)
    if blueprint.title:
        project.title = blueprint.title
        project.status = "blueprint_ready"
        await session.commit()
        logger.info("项目 %s 更新标题为 %s，并标记为 blueprint_ready", project_id, blueprint.title)

    # ✅ 将用户的补充信息保存到对话历史中（可选，方便后续查看）
    await novel_service.add_conversation_record(
        project_id=project_id,
        role="user",
        content=json.dumps({"value": request.additional_feedback}, ensure_ascii=False)
    )

    ai_message = (
        "好的！我已经根据你补充的信息重新生成了蓝图。请查看新的蓝图内容，如果还有需要调整的地方，可以继续补充信息重新生成。"
    )
    return BlueprintGenerationResponse(blueprint=blueprint, ai_message=ai_message)


@router.post("/{project_id}/blueprint/save", response_model=NovelProjectSchema)
async def save_blueprint(
    project_id: str,
    blueprint_data: Blueprint | None = Body(None),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """保存蓝图信息，可用于手动覆盖自动生成结果。"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    if blueprint_data:
        await novel_service.replace_blueprint(project_id, blueprint_data)
        if blueprint_data.title:
            project.title = blueprint_data.title
            await session.commit()
        logger.info("项目 %s 手动保存蓝图", project_id)
    else:
        logger.warning("项目 %s 保存蓝图时未提供蓝图数据", project_id)
        raise HTTPException(status_code=400, detail="缺少蓝图数据，请提供有效的蓝图内容")

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.patch("/{project_id}/blueprint", response_model=NovelProjectSchema)
async def patch_blueprint(
    project_id: str,
    payload: BlueprintPatch,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """局部更新蓝图字段，对世界观或角色做微调。"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    update_data = payload.model_dump(exclude_unset=True)
    await novel_service.patch_blueprint(project_id, update_data)
    logger.info("项目 %s 局部更新蓝图字段：%s", project_id, list(update_data.keys()))
    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/{project_id}/upload-to-fanqie")
async def upload_to_fanqie(
    project_id: str,
    account: str = Body("default", description="番茄小说账号标识"),
    headless: bool = Body(True, description="是否使用无头模式（生产环境建议True）"),
    upload_interval: int = Body(20, description="上传间隔（秒），建议20-60秒"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict:
    """一键上传小说到番茄小说平台

    前提条件：
    1. 已在番茄小说平台手动创建同名书籍
    2. 已通过 /api/novels/fanqie/login 保存过Cookie

    Args:
        project_id: 小说项目ID
        account: 番茄小说账号标识（用于区分不同账号的cookie）
        headless: 是否使用无头模式（默认True，生产环境建议使用）
        upload_interval: 上传间隔（秒），默认20秒，建议20-60秒

    Returns:
        上传结果，包含成功/失败状态和详细信息
    """
    try:
        from ...services.fanqie_publisher_service import FanqiePublisherService

        novel_service = NovelService(session)
        await novel_service.ensure_project_owner(project_id, current_user.id)

        logger.info(f"用户 {current_user.id} 开始上传项目 {project_id} 到番茄小说 (headless={headless}, upload_interval={upload_interval})")

        # 使用异步上下文管理器
        try:
            async with FanqiePublisherService(headless=headless) as publisher:
                result = await publisher.upload_novel_to_fanqie(
                    db=session,
                    project_id=project_id,
                    account=account,
                    upload_interval=upload_interval
                )
        except Exception as e:
            logger.error(f"FanqiePublisherService 执行失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"上传服务初始化或执行失败: {str(e)}",
                "hint": "请检查Playwright是否正确安装，或查看后端日志获取详细信息"
            }

        if result.get("success"):
            logger.info(f"项目 {project_id} 上传成功: {result.get('chapter_count')}章")
        else:
            logger.error(f"项目 {project_id} 上传失败: {result.get('error')}")

        return result

    except HTTPException:
        # 重新抛出HTTP异常（如权限错误）
        raise
    except Exception as e:
        logger.error(f"上传到番茄小说时发生未预期的错误: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"上传失败: {str(e)}",
            "hint": "请查看后端日志获取详细错误信息"
        }


@router.post("/fanqie/login")
async def fanqie_open_login(
    account: str = Body("default", description="账号标识"),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict:
    """打开番茄小说登录页面

    此接口会打开浏览器窗口，用户需要手动完成登录。
    登录成功后，需要调用 /api/novels/fanqie/save-cookies 接口保存Cookie。

    Args:
        account: 账号标识（用于区分不同账号的cookie）

    Returns:
        操作结果
    """
    from ...services.fanqie_browser_manager import browser_manager

    logger.info(f"用户 {current_user.id} 打开番茄小说登录页面，账号标识: {account}")

    try:
        # 使用浏览器管理器获取或创建会话
        browser, context, page, playwright = await browser_manager.get_or_create_session(
            account=account,
            headless=False  # 登录时必须使用有头模式
        )

        # 清除旧的Cookie
        await context.clear_cookies()
        logger.info("已清除旧Cookie,准备进行全新登录")

        # 访问作家工作台（会自动跳转到登录页面）
        await page.goto("https://fanqienovel.com/main/writer/?enter_from=author_zone")

        logger.info("=" * 60)
        logger.info("浏览器窗口已打开，请在浏览器中完成登录操作")
        logger.info("=" * 60)

        return {
            "success": True,
            "account": account,
            "message": "浏览器窗口已打开，请完成登录后点击'保存Cookie'按钮"
        }
    except Exception as e:
        logger.error(f"打开登录页面失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/fanqie/save-cookies")
async def fanqie_save_cookies(
    account: str = Body("default", description="账号标识"),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict:
    """保存番茄小说Cookie

    从当前浏览器会话中提取并保存Cookie。
    应该在用户完成登录后调用。

    Args:
        account: 账号标识（用于区分不同账号的cookie）

    Returns:
        保存结果
    """
    from ...services.fanqie_publisher_service import FanqiePublisherService
    from ...services.fanqie_browser_manager import browser_manager
    import json
    from pathlib import Path

    logger.info(f"用户 {current_user.id} 保存番茄小说Cookie，账号标识: {account}")

    try:
        # 使用浏览器管理器获取现有会话
        browser, context, page, playwright = await browser_manager.get_or_create_session(account=account)

        # 获取当前Cookie
        cookies = await context.cookies()
        cookie_names = [c['name'] for c in cookies]
        logger.info(f"当前Cookie列表: {cookie_names}")

        # 检查是否有登录相关的Cookie
        has_login_cookie = any(name in cookie_names for name in [
            'sessionid', 'uid', 'passport_csrf_token', 'sid_guard',
            'sid_tt', 'ssid', 'odin_tt', 'passport_auth_status'
        ])

        if not has_login_cookie:
            logger.warning("未检测到登录Cookie，请确保已在浏览器中完成登录")
            return {
                "success": False,
                "error": "未检测到登录Cookie，请确保已在浏览器中完成登录"
            }

        # ✅ 修复：使用与FanqiePublisherService相同的路径计算方法
        # 获取当前文件所在目录（backend/app/api/routers/）
        current_file = Path(__file__).resolve()
        # 向上4级到backend目录
        backend_dir = current_file.parent.parent.parent.parent
        cookies_dir = backend_dir / "storage" / "fanqie_cookies"
        cookies_dir.mkdir(parents=True, exist_ok=True)
        cookies_file = cookies_dir / f"{account}_cookies.json"

        with open(cookies_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

        logger.info(f"Cookie已保存到: {cookies_file.absolute()}")

        # 保存成功后关闭浏览器会话
        await browser_manager.close_session(account)

        return {
            "success": True,
            "account": account,
            "message": f"Cookie保存成功！文件路径: {cookies_file.absolute()}"
        }
    except Exception as e:
        logger.error(f"保存Cookie失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/fanqie/manual-save-cookies")
async def fanqie_manual_save_cookies(
    account: str = Body("default", description="账号标识"),
    cookie_string: str = Body(..., description="Cookie字符串"),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict:
    """手动保存番茄小说Cookie

    用户从浏览器开发者工具中复制Cookie字符串并手动保存。

    Args:
        account: 账号标识（用于区分不同账号的cookie）
        cookie_string: Cookie字符串（格式：name1=value1; name2=value2; ...）

    Returns:
        保存结果
    """
    import json
    from pathlib import Path

    logger.info(f"用户 {current_user.id} 手动保存番茄小说Cookie，账号标识: {account}")

    try:
        # 解析Cookie字符串
        cookies = []
        for cookie_pair in cookie_string.split(';'):
            cookie_pair = cookie_pair.strip()
            if '=' in cookie_pair:
                name, value = cookie_pair.split('=', 1)
                cookies.append({
                    'name': name.strip(),
                    'value': value.strip(),
                    'domain': '.fanqienovel.com',
                    'path': '/'
                })

        if not cookies:
            return {
                "success": False,
                "error": "Cookie字符串格式不正确"
            }

        # 检查是否有登录相关的Cookie
        cookie_names = [c['name'] for c in cookies]
        has_login_cookie = any(name in cookie_names for name in [
            'sessionid', 'uid', 'passport_csrf_token', 'sid_guard',
            'sid_tt', 'ssid', 'odin_tt', 'passport_auth_status'
        ])

        if not has_login_cookie:
            logger.warning(f"未检测到登录Cookie，当前Cookie: {cookie_names}")
            return {
                "success": False,
                "error": "未检测到登录相关的Cookie，请确保复制了完整的Cookie字符串"
            }

        # 保存Cookie到文件 - 使用与FanqiePublisherService相同的路径
        # 获取当前文件所在目录（backend/app/api/routers/）
        current_file = Path(__file__).resolve()
        # 向上4级到backend目录
        backend_dir = current_file.parent.parent.parent.parent
        cookie_dir = backend_dir / "storage" / "fanqie_cookies"
        cookie_dir.mkdir(parents=True, exist_ok=True)
        cookie_file = cookie_dir / f"{account}_cookies.json"

        with open(cookie_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        logger.info(f"Cookie已手动保存到 {cookie_file.absolute()}，包含 {len(cookies)} 个Cookie")
        return {
            "success": True,
            "account": account,
            "message": f"Cookie保存成功！共保存 {len(cookies)} 个Cookie"
        }

    except Exception as e:
        logger.error(f"手动保存Cookie失败: {e}")
        return {
            "success": False,
            "error": f"保存失败: {str(e)}"
        }
