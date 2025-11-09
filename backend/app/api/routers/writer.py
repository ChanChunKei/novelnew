import json
import logging
import os
from datetime import datetime
from typing import Dict, List
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...models.novel import BlueprintCharacter, Chapter, ChapterOutline, NovelBlueprint, Volume
from ...schemas.novel import (
    DeleteChapterRequest,
    DenoiseChapterRequest,
    EditChapterRequest,
    EvaluateChapterRequest,
    GenerateChapterRequest,
    GenerateOutlineRequest,
    NovelProject as NovelProjectSchema,
    SelectVersionRequest,
    UpdateChapterOutlineRequest,
)
from ...schemas.user import UserInDB
from ...services.ai_denoising_service import AIDenoisingService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...utils.json_utils import remove_think_tags, unwrap_markdown_json
from ...repositories.system_config_repository import SystemConfigRepository

router = APIRouter(prefix="/api/writer", tags=["Writer"])
logger = logging.getLogger(__name__)


async def _load_project_schema(service: NovelService, project_id: str, user_id: int) -> NovelProjectSchema:
    return await service.get_project_schema(project_id, user_id)





async def _check_prerequisites(
    session: AsyncSession,
    project_id: str,
    chapter_number: int
) -> tuple[bool, str]:
    """
    ✅ 新增函数：检查章节前置条件

    确保在生成章节前，所有前置章节都已完成。

    Args:
        session: 数据库会话
        project_id: 项目ID
        chapter_number: 要生成的章节号

    Returns:
        (可否生成, 错误信息)
    """
    if chapter_number == 1:
        return True, ""

    # 查询所有前置章节
    stmt = (
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .where(Chapter.chapter_number < chapter_number)
        .order_by(Chapter.chapter_number)
    )
    result = await session.execute(stmt)
    previous_chapters = result.scalars().all()

    # 检查是否都有内容
    incomplete = [
        ch for ch in previous_chapters
        if not ch.selected_version or not ch.selected_version.content
    ]

    if incomplete:
        missing_numbers = [str(ch.chapter_number) for ch in incomplete]
        error_msg = f"需要先完成前置章节：第 {', '.join(missing_numbers)} 章"
        return False, error_msg

    return True, ""


@router.post("/novels/{project_id}/chapters/generate", response_model=NovelProjectSchema)
async def generate_chapter(
    project_id: str,
    request: GenerateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("用户 %s 开始为项目 %s 生成第 %s 章", current_user.id, project_id, request.chapter_number)

    # ✅ 新增：检查前置条件
    can_generate, error_msg = await _check_prerequisites(
        session, project_id, request.chapter_number
    )
    if not can_generate:
        logger.warning("项目 %s 第 %s 章前置条件检查失败: %s", project_id, request.chapter_number, error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        logger.warning("项目 %s 未找到第 %s 章纲要，生成流程终止", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)
    chapter.real_summary = None
    chapter.selected_version_id = None
    chapter.status = "generating"
    await session.commit()

    outlines_map = {item.chapter_number: item for item in project.outlines}
    # 收集所有可用的历史章节摘要，便于在 Prompt 中提供前情背景
    completed_chapters = []
    for existing in project.chapters:
        if existing.chapter_number >= request.chapter_number:
            continue
        if existing.selected_version is None or not existing.selected_version.content:
            continue
        if not existing.real_summary:
            summary = await llm_service.get_summary(
                existing.selected_version.content,
                temperature=0.15,
                user_id=current_user.id,
                timeout=180.0,
            )
            existing.real_summary = remove_think_tags(summary)
            await session.commit()
        # ✅ 修复：避免重复调用 get() 导致的潜在 None 引用错误
        outline = outlines_map.get(existing.chapter_number)
        completed_chapters.append(
            {
                "chapter_number": existing.chapter_number,
                "title": outline.title if outline else f"第{existing.chapter_number}章",
                "summary": existing.real_summary,
            }
        )

    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
        for relation in blueprint_dict["relationships"]:
            if "character_from" in relation:
                relation["from"] = relation.pop("character_from")
            if "character_to" in relation:
                relation["to"] = relation.pop("character_to")

    # 蓝图中禁止携带章节级别的细节信息，避免重复传输大段场景或对话内容
    # ✅ 保留 chapter_outline，让AI知道总章节数和整体规划
    banned_blueprint_keys = {
        "chapter_summaries",
        "chapter_details",
        "chapter_dialogues",
        "chapter_events",
        "conversation_history",
        "character_timelines",
    }
    for key in banned_blueprint_keys:
        if key in blueprint_dict:
            blueprint_dict.pop(key, None)

    writer_prompt = await prompt_service.get_prompt("writing")
    if not writer_prompt:
        logger.error("未配置名为 'writing' 的写作提示词，无法生成章节内容")
        raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置 'writing' 提示词")

    # ✅ 新方案：不使用RAG，改用简单上下文
    # 1. 所有章节的摘要
    # 2. 上两章的完整内容

    outline_title = outline.title or f"第{outline.chapter_number}章"
    outline_summary = outline.summary or "暂无摘要"

    # 构建所有章节摘要
    blueprint_text = json.dumps(blueprint_dict, ensure_ascii=False, indent=2)
    all_summaries_lines = [
        f"- 第{item['chapter_number']}章 - {item['title']}: {item['summary']}"
        for item in completed_chapters
    ]
    all_summaries_text = "\n".join(all_summaries_lines) if all_summaries_lines else "暂无已完成章节"

    # 获取上两章的完整内容
    previous_two_chapters = []
    for existing in sorted(project.chapters, key=lambda x: x.chapter_number, reverse=True):
        if existing.chapter_number >= request.chapter_number:
            continue
        if existing.selected_version and existing.selected_version.content:
            outline_item = outlines_map.get(existing.chapter_number)
            chapter_title = outline_item.title if outline_item else f"第{existing.chapter_number}章"
            previous_two_chapters.append({
                "number": existing.chapter_number,
                "title": chapter_title,
                "content": existing.selected_version.content
            })
            if len(previous_two_chapters) >= 2:
                break

    # 反转顺序，让最早的章节在前
    previous_two_chapters.reverse()

    # 构建上两章内容文本
    previous_chapters_text = ""
    if previous_two_chapters:
        previous_chapters_parts = []
        for ch in previous_two_chapters:
            previous_chapters_parts.append(f"### 第{ch['number']}章 - {ch['title']}\n{ch['content']}")
        previous_chapters_text = "\n\n".join(previous_chapters_parts)
    else:
        previous_chapters_text = "暂无前序章节"

    writing_notes = request.writing_notes or "无额外写作指令"

    prompt_sections = [
        ("[世界蓝图](JSON)", blueprint_text),
        ("[所有章节摘要]", all_summaries_text),
        ("[前两章完整内容]", previous_chapters_text),
        (
            "[当前章节目标]",
            f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}",
        ),
    ]
    prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
    logger.debug("章节写作提示词：%s\n%s", writer_prompt, prompt_input)
    async def _generate_single_version(idx: int) -> Dict:
        try:
            response = await llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": prompt_input}],
                temperature=0.9,
                user_id=current_user.id,
                timeout=600.0,
            )
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)
            try:
                return json.loads(normalized)
            except json.JSONDecodeError as parse_err:
                logger.warning(
                    "项目 %s 第 %s 章第 %s 个版本 JSON 解析失败，将原始内容作为纯文本处理: %s",
                    project_id,
                    request.chapter_number,
                    idx + 1,
                    parse_err,
                )
                return {"content": normalized}
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "项目 %s 生成第 %s 章第 %s 个版本时发生异常: %s",
                project_id,
                request.chapter_number,
                idx + 1,
                exc,
            )
            raise HTTPException(
                status_code=500,
                detail=f"生成章节第 {idx + 1} 个版本时失败: {str(exc)[:200]}"
            )

    version_count = await _resolve_version_count(session)
    logger.info(
        "项目 %s 第 %s 章计划生成 %s 个版本",
        project_id,
        request.chapter_number,
        version_count,
    )
    raw_versions = []
    for idx in range(version_count):
        raw_versions.append(await _generate_single_version(idx))

    # 提取full_content字段
    contents: List[str] = []
    for idx, variant in enumerate(raw_versions):
        if isinstance(variant, dict):
            # 优先提取full_content字段
            if "full_content" in variant and variant["full_content"]:
                contents.append(variant["full_content"])
                logger.info(f"第 {request.chapter_number} 章版本 {idx+1}: 提取full_content，长度={len(variant['full_content'])}")
            elif "content" in variant and variant["content"]:
                contents.append(variant["content"])
                logger.info(f"第 {request.chapter_number} 章版本 {idx+1}: 提取content，长度={len(variant['content'])}")
            else:
                # 如果没有找到内容字段，使用整个JSON
                content_str = json.dumps(variant, ensure_ascii=False)
                contents.append(content_str)
                logger.warning(f"第 {request.chapter_number} 章版本 {idx+1}: 未找到full_content或content字段，使用完整JSON")
        else:
            contents.append(str(variant))
            logger.info(f"第 {request.chapter_number} 章版本 {idx+1}: variant不是dict，直接转字符串")

    # 保存版本
    await novel_service.replace_chapter_versions(chapter, contents, None)
    logger.info(
        "项目 %s 第 %s 章生成完成，已写入 %s 个版本",
        project_id,
        request.chapter_number,
        len(contents),
    )
    return await _load_project_schema(novel_service, project_id, current_user.id)


async def _resolve_version_count(session: AsyncSession) -> int:
    repo = SystemConfigRepository(session)
    record = await repo.get_by_key("writer.chapter_versions")
    if record:
        try:
            value = int(record.value)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    env_value = os.getenv("WRITER_CHAPTER_VERSION_COUNT")
    if env_value:
        try:
            value = int(env_value)
            if value > 0:
                return value
        except ValueError:
            pass
    return 3


@router.post("/novels/{project_id}/chapters/select", response_model=NovelProjectSchema)
async def select_chapter_version(
    project_id: str,
    request: SelectVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法选择版本", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")

    selected = await novel_service.select_chapter_version(chapter, request.version_index)
    logger.info(
        "用户 %s 选择了项目 %s 第 %s 章的第 %s 个版本",
        current_user.id,
        project_id,
        request.chapter_number,
        request.version_index,
    )
    if selected and selected.content:
        summary = await llm_service.get_summary(
            selected.content,
            temperature=0.15,
            user_id=current_user.id,
            timeout=180.0,
        )
        chapter.real_summary = remove_think_tags(summary)
        await session.commit()

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/evaluate", response_model=NovelProjectSchema)
async def evaluate_chapter(
    project_id: str,
    request: EvaluateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法执行评估", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")
    if not chapter.versions:
        logger.warning("项目 %s 第 %s 章无可评估版本", project_id, request.chapter_number)
        raise HTTPException(status_code=400, detail="无可评估的章节版本")

    evaluator_prompt = await prompt_service.get_prompt("evaluation")
    if not evaluator_prompt:
        logger.error("缺少评估提示词，项目 %s 第 %s 章评估失败", project_id, request.chapter_number)
        raise HTTPException(status_code=500, detail="缺少评估提示词，请联系管理员配置 'evaluation' 提示词")

    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    versions_to_evaluate = [
        {"version_id": idx + 1, "content": version.content}
        for idx, version in enumerate(sorted(chapter.versions, key=lambda item: item.created_at))
    ]
    # print("blueprint_dict:",blueprint_dict)
    evaluator_payload = {
        "novel_blueprint": blueprint_dict,
        "content_to_evaluate": {
            "chapter_number": chapter.chapter_number,
            "versions": versions_to_evaluate,
        },
    }

    evaluation_raw = await llm_service.get_llm_response(
        system_prompt=evaluator_prompt,
        conversation_history=[{"role": "user", "content": json.dumps(evaluator_payload, ensure_ascii=False)}],
        temperature=0.3,
        user_id=current_user.id,
        timeout=360.0,
    )
    evaluation_clean = remove_think_tags(evaluation_raw)
    await novel_service.add_chapter_evaluation(chapter, None, evaluation_clean)
    logger.info("项目 %s 第 %s 章评估完成", project_id, request.chapter_number)

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/outline", response_model=NovelProjectSchema)
async def generate_chapter_outline(
    project_id: str,
    request: GenerateOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 请求生成项目 %s 的章节大纲，起始章节 %s，数量 %s",
        current_user.id,
        project_id,
        request.start_chapter,
        request.num_chapters,
    )
    outline_prompt = await prompt_service.get_prompt("outline")
    if not outline_prompt:
        logger.error("缺少大纲提示词，项目 %s 大纲生成失败", project_id)
        raise HTTPException(status_code=500, detail="缺少大纲提示词，请联系管理员配置 'outline' 提示词")

    project_schema = await novel_service.get_project_schema(project_id, current_user.id)
    blueprint_dict = project_schema.blueprint.model_dump()

    # 获取项目实体（用于查询已生成章节）
    project = await novel_service.get_project(project_id, current_user.id)

    # 构建已完成章节摘要列表
    completed_chapters = []
    outlines_map = {o.chapter_number: o for o in project.outlines}

    for ch in sorted(project.chapters, key=lambda x: x.chapter_number):
        if ch.selected_version and ch.selected_version.content:
            outline_item = outlines_map.get(ch.chapter_number)
            completed_chapters.append({
                "chapter_number": ch.chapter_number,
                "title": outline_item.title if outline_item else f"第{ch.chapter_number}章",
                "summary": outline_item.summary or ch.selected_version.summary or ""
            })

    # 获取上一分卷结束的最后两章完整内容
    previous_two_chapters = []
    for existing in sorted(project.chapters, key=lambda x: x.chapter_number, reverse=True):
        if existing.chapter_number >= request.start_chapter:
            continue
        if existing.selected_version and existing.selected_version.content:
            outline_item = outlines_map.get(existing.chapter_number)
            chapter_title = outline_item.title if outline_item else f"第{existing.chapter_number}章"
            previous_two_chapters.append({
                "number": existing.chapter_number,
                "title": chapter_title,
                "content": existing.selected_version.content
            })
            if len(previous_two_chapters) >= 2:
                break

    # 反转顺序，让最早的章节在前
    previous_two_chapters.reverse()

    # 获取所有分卷的快照数据
    volumes_data = []
    for vol in sorted(project.volumes, key=lambda x: x.volume_number):
        vol_data = {
            "volume_number": vol.volume_number,
            "title": vol.title,
            "characters": vol.characters or [],
            "relationships": vol.relationships or [],
            "world_setting": vol.world_setting or {}
        }
        volumes_data.append(vol_data)

    payload = {
        "novel_blueprint": blueprint_dict,
        "completed_chapters": completed_chapters,
        "previous_two_chapters": previous_two_chapters,
        "volumes": volumes_data,  # 传递所有分卷的快照数据
        "wait_to_generate": {
            "start_chapter": request.start_chapter,
            "num_chapters": request.num_chapters,
        },
    }

    response = await llm_service.get_llm_response(
        system_prompt=outline_prompt,
        conversation_history=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        temperature=0.7,
        user_id=current_user.id,
        timeout=360.0,
    )
    normalized = unwrap_markdown_json(remove_think_tags(response))
    try:
        data = json.loads(normalized)
    except json.JSONDecodeError as exc:
        logger.error(
            "项目 %s 大纲生成 JSON 解析失败: %s, 原始内容预览: %s",
            project_id,
            exc,
            normalized[:500],
        )
        raise HTTPException(
            status_code=500,
            detail=f"章节大纲生成失败，AI 返回的内容格式不正确: {str(exc)}"
        ) from exc

    # 提取数据
    volume_title = data.get("volume_title", "")
    new_outlines = data.get("chapters", [])
    volume_characters = data.get("characters", [])  # 该卷的完整角色快照
    volume_relationships = data.get("relationships", [])  # 该卷的完整关系快照
    volume_world_setting = data.get("world_setting", {})  # 该卷的完整世界观快照

    if not new_outlines:
        raise HTTPException(status_code=500, detail="AI 未生成任何章节大纲")

    # 1. 创建或更新分卷（保存快照数据）
    volume_id = None
    if volume_title:
        # 根据起始章节号推断卷号
        stmt = select(Volume).where(Volume.project_id == project_id).order_by(Volume.volume_number.desc())
        result = await session.execute(stmt)
        last_volume = result.scalars().first()
        next_volume_number = (last_volume.volume_number + 1) if last_volume else 1

        # 检查是否已存在该卷号
        stmt = select(Volume).where(
            Volume.project_id == project_id,
            Volume.volume_number == next_volume_number
        )
        result = await session.execute(stmt)
        existing_volume = result.scalars().first()

        if existing_volume:
            existing_volume.title = volume_title
            # 保存快照数据到 Volume
            existing_volume.characters = volume_characters
            existing_volume.relationships = volume_relationships
            existing_volume.world_setting = volume_world_setting
            volume_id = existing_volume.id
            logger.info(f"更新分卷 {next_volume_number}: {volume_title}（包含 {len(volume_characters)} 个角色，{len(volume_relationships)} 个关系）")
        else:
            new_volume = Volume(
                project_id=project_id,
                volume_number=next_volume_number,
                title=volume_title,
                # 保存快照数据到 Volume
                characters=volume_characters,
                relationships=volume_relationships,
                world_setting=volume_world_setting,
            )
            session.add(new_volume)
            await session.flush()  # 获取 volume_id
            volume_id = new_volume.id
            logger.info(f"创建新分卷 {next_volume_number}: {volume_title}（包含 {len(volume_characters)} 个角色，{len(volume_relationships)} 个关系）")

    # 2. 保存章节大纲
    for item in new_outlines:
        stmt = (
            select(ChapterOutline)
            .where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == item.get("chapter_number"),
            )
        )
        result = await session.execute(stmt)
        record = result.scalars().first()
        if record:
            record.title = item.get("title", record.title)
            record.summary = item.get("summary", record.summary)
            if volume_id and not record.volume_id:
                record.volume_id = volume_id
        else:
            session.add(
                ChapterOutline(
                    project_id=project_id,
                    volume_id=volume_id,
                    chapter_number=item.get("chapter_number"),
                    title=item.get("title", ""),
                    summary=item.get("summary"),
                )
            )

    # 注意：角色、关系、世界观已经保存到 Volume 的快照字段中
    # 不再需要单独添加到 BlueprintCharacter 或 NovelBlueprint

    await session.commit()
    logger.info("项目 %s 章节大纲生成完成", project_id)

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/update-outline", response_model=NovelProjectSchema)
async def update_chapter_outline(
    project_id: str,
    request: UpdateChapterOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 更新项目 %s 第 %s 章大纲",
        current_user.id,
        project_id,
        request.chapter_number,
    )

    stmt = (
        select(ChapterOutline)
        .where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    outline = result.scalars().first()
    if not outline:
        outline = ChapterOutline(
            project_id=project_id,
            chapter_number=request.chapter_number,
        )
        session.add(outline)

    outline.title = request.title
    outline.summary = request.summary
    await session.commit()
    logger.info("项目 %s 第 %s 章大纲已更新", project_id, request.chapter_number)

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/delete", response_model=NovelProjectSchema)
async def delete_chapters(
    project_id: str,
    request: DeleteChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    if not request.chapter_numbers:
        logger.warning("项目 %s 删除章节时未提供章节号", project_id)
        raise HTTPException(status_code=400, detail="请提供要删除的章节号列表")
    novel_service = NovelService(session)
    llm_service = LLMService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 删除项目 %s 的章节 %s",
        current_user.id,
        project_id,
        request.chapter_numbers,
    )
    await novel_service.delete_chapters(project_id, request.chapter_numbers)
    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/edit", response_model=NovelProjectSchema)
async def edit_chapter(
    project_id: str,
    request: EditChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter or chapter.selected_version is None:
        logger.warning("项目 %s 第 %s 章尚未生成或未选择版本，无法编辑", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节尚未生成或未选择版本")

    chapter.selected_version.content = request.content
    chapter.word_count = len(request.content)
    logger.info("用户 %s 更新了项目 %s 第 %s 章内容", current_user.id, project_id, request.chapter_number)

    if request.content.strip():
        summary = await llm_service.get_summary(
            request.content,
            temperature=0.15,
            user_id=current_user.id,
            timeout=180.0,
        )
        chapter.real_summary = remove_think_tags(summary)
    await session.commit()

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.get("/novels/{project_id}/export/all-chapters")
async def export_all_chapters(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """导出项目的所有已生成章节为文本文件"""
    novel_service = NovelService(session)

    # 验证项目所有权
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    # 获取项目标题
    project_title = project.blueprint.title if (project.blueprint and project.blueprint.title) else project.title

    # 获取所有已生成且已选择版本的章节
    result = await session.execute(
        select(Chapter, ChapterOutline)
        .outerjoin(ChapterOutline,
                   (Chapter.project_id == ChapterOutline.project_id) &
                   (Chapter.chapter_number == ChapterOutline.chapter_number))
        .where(
            Chapter.project_id == project_id,
            Chapter.status == "successful",
            Chapter.selected_version_id.isnot(None)
        )
        .order_by(Chapter.chapter_number)
    )
    chapters_with_outlines = result.all()

    if not chapters_with_outlines:
        raise HTTPException(status_code=404, detail="没有可导出的章节")

    # 构建导出内容
    content_parts = [f"《{project_title}》\n\n"]

    for chapter, outline in chapters_with_outlines:
        # 获取选中的版本内容
        if chapter.selected_version:
            chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
            content_parts.append(f"{chapter_title}\n\n")
            content_parts.append(f"{chapter.selected_version.content}\n\n")

    full_content = "".join(content_parts)

    # 生成文件名
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{project_title}_全文_{date_str}.txt"
    # URL 编码文件名以支持中文
    encoded_filename = quote(filename)

    # 返回文件下载响应
    logger.info("用户 %s 导出项目 %s 的所有章节，共 %s 章", current_user.id, project_id, len(chapters_with_outlines))

    return Response(
        content=full_content.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


@router.post("/novels/{project_id}/chapters/denoise", response_model=NovelProjectSchema)
async def denoise_chapter(
    project_id: str,
    request: DenoiseChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """
    ✅ 新增API：AI去味功能

    对指定章节的内容进行AI去味处理，去除AI生成文本的机械感。

    Args:
        project_id: 项目ID
        request: 去味请求（包含章节号和版本索引）
        session: 数据库会话
        current_user: 当前用户

    Returns:
        更新后的项目Schema
    """
    novel_service = NovelService(session)
    denoising_service = AIDenoisingService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 开始对项目 %s 的第 %s 章进行AI去味",
        current_user.id, project_id, request.chapter_number
    )

    # ✅ 修复：使用正确的方式获取章节（从project.chapters中查找）
    chapter = next(
        (ch for ch in project.chapters if ch.chapter_number == request.chapter_number),
        None
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    # 确定要去味的版本
    if request.version_index is not None:
        # 使用指定版本
        if request.version_index < 0 or request.version_index >= len(chapter.versions):
            raise HTTPException(status_code=400, detail="版本索引无效")
        target_version = chapter.versions[request.version_index]
    else:
        # 使用当前选中版本
        if not chapter.selected_version:
            raise HTTPException(status_code=400, detail="章节没有选中的版本")
        target_version = chapter.selected_version

    if not target_version.content:
        raise HTTPException(status_code=400, detail="版本内容为空")

    # 执行去味
    original_content = target_version.content
    logger.info(f"开始去味，原文长度={len(original_content)}")

    denoised_content = await denoising_service.denoise_chapter(
        chapter_content=original_content,
        user_id=current_user.id,
        timeout=60.0,
    )

    # ✅ 修复：使用正确的方式添加新版本
    # 方案1：直接修改当前版本的内容（最简单，类似edit_chapter）
    # 方案2：创建新版本（需要使用replace_chapter_versions）

    # 这里使用方案1：直接修改当前版本（保持简单）
    target_version.content = denoised_content
    target_version.extra = target_version.extra or {}
    target_version.extra["denoising_metadata"] = {
        "source": "ai_denoising",
        "original_length": len(original_content),
        "denoised_length": len(denoised_content),
        "denoised_at": datetime.now().isoformat(),
    }

    chapter.word_count = len(denoised_content)
    await session.commit()

    logger.info(
        f"AI去味完成，原文长度={len(original_content)}，"
        f"去味后长度={len(denoised_content)}"
    )

    return await _load_project_schema(novel_service, project_id, current_user.id)
