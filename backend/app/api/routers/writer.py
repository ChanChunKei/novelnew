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
from ...services.chapter_ingest_service import ChapterIngestionService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...utils.json_utils import remove_think_tags, unwrap_markdown_json
from ...repositories.system_config_repository import SystemConfigRepository
from ...core.config import settings

router = APIRouter(prefix="/api/writer", tags=["Writer"])
logger = logging.getLogger(__name__)


async def _invoke_with_specific_route(
    llm_service: LLMService,
    user_route_config: dict,
    route_index: int,
    messages: List[Dict[str, str]],
    temperature: float,
    timeout: float,
    user_id: int,
) -> str:
    """使用指定路由索引调用LLM"""
    routes = user_route_config.get("routes", [])
    if route_index >= len(routes) or not routes[route_index].get("enabled"):
        raise ValueError(f"路由索引 {route_index} 无效或未启用")

    route = routes[route_index]

    # 使用 LLMClient 直接调用（复用 utils.llm_tool 封装）
    from ...utils.llm_tool import LLMClient, ChatMessage

    client = LLMClient(api_key=route["apiKey"], base_url=route["url"])
    chat_messages = [ChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]

    # 调用并收集响应
    response_chunks: list[str] = []
    async for chunk in client.stream_chat(
        messages=chat_messages,
        model=route["model"],
        temperature=temperature,
        timeout=timeout,
        response_format="json_object",
    ):
        # chunk 可能是 {"content": "..."}，取 content 字段
        if isinstance(chunk, dict):
            content = chunk.get("content")
        else:
            content = str(chunk)
        if content:
            response_chunks.append(content)

    return "".join(response_chunks)


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

    # 🔥 先获取 blueprint 和分卷快照，用于生成摘要
    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    # 🔥 获取所有分卷快照（用于生成摘要）
    from sqlalchemy import select
    from ...models.novel import Volume

    volumes_stmt = select(Volume).where(Volume.project_id == project_id).order_by(Volume.volume_number)
    volumes_result = await session.execute(volumes_stmt)
    all_volumes = volumes_result.scalars().all()

    # 构建 volume_id 到快照的映射
    volumes_by_id = {}
    for vol in all_volumes:
        vol_snapshot = {
            "volume_number": vol.volume_number,
            "title": vol.title,
            "characters": vol.characters or [],
            "relationships": vol.relationships or [],
            "world_setting": vol.world_setting or {},
            "is_current": False
        }
        volumes_by_id[vol.id] = vol_snapshot

    outlines_map = {item.chapter_number: item for item in project.outlines}
    # 收集所有可用的历史章节摘要，便于在 Prompt 中提供前情背景
    completed_chapters = []
    for existing in project.chapters:
        if existing.chapter_number >= request.chapter_number:
            continue
        if existing.selected_version is None or not existing.selected_version.content:
            continue
        if not existing.real_summary:
            # 🔥 构建该章节的分卷快照上下文
            chapter_volumes_snapshot = []
            for vol_id, vol_data in volumes_by_id.items():
                vol_copy = vol_data.copy()
                # 标注该章节所属的卷
                if existing.volume_id and vol_id == existing.volume_id:
                    vol_copy["is_current"] = True
                chapter_volumes_snapshot.append(vol_copy)

            summary = await llm_service.get_summary(
                existing.selected_version.content,
                temperature=0.15,
                user_id=current_user.id,
                timeout=180.0,
                blueprint_dict=blueprint_dict,
                volumes_snapshot=chapter_volumes_snapshot,
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

    # 🔥 获取所有分卷的快照数据，并标注当前卷
    from sqlalchemy import select
    from ...models.novel import Volume

    volumes_stmt = select(Volume).where(Volume.project_id == project_id).order_by(Volume.volume_number)
    volumes_result = await session.execute(volumes_stmt)
    all_volumes = volumes_result.scalars().all()

    current_volume_number = None
    volumes_snapshot = []
    for vol in all_volumes:
        vol_data = {
            "volume_number": vol.volume_number,
            "title": vol.title,
            "characters": vol.characters or [],
            "relationships": vol.relationships or [],
            "world_setting": vol.world_setting or {},
            "is_current": False
        }
        # 标注当前章节所属的卷
        if outline.volume_id and vol.id == outline.volume_id:
            vol_data["is_current"] = True
            current_volume_number = vol.volume_number
        volumes_snapshot.append(vol_data)

    # 构建分卷快照文本
    volumes_snapshot_text = ""
    if volumes_snapshot:
        volumes_snapshot_text = json.dumps(volumes_snapshot, ensure_ascii=False, indent=2)
        logger.info(f"第 {request.chapter_number} 章：传递 {len(volumes_snapshot)} 个卷的快照数据，当前卷为第 {current_volume_number} 卷")
    else:
        volumes_snapshot_text = "暂无分卷快照数据（使用蓝图初始设定）"

    prompt_sections = [
        ("[世界蓝图](JSON)", blueprint_text),
        ("[所有分卷快照数据](JSON) - is_current=true 表示当前卷", volumes_snapshot_text),
        ("[所有章节摘要]", all_summaries_text),
        ("[前两章完整内容]", previous_chapters_text),
        (
            "[当前章节目标]",
            f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}",
        ),
    ]
    prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
    logger.debug("章节写作提示词：%s\n%s", writer_prompt, prompt_input)
    # 🎨 读取混合生成配置
    user_route_config = await llm_service.get_user_route_config(current_user.id)
    mixed_generation_config = None
    if user_route_config and user_route_config.get("mixedGeneration", {}).get("enabled"):
        mixed_generation_config = user_route_config["mixedGeneration"]
        logger.info(f"项目 {project_id} 第 {request.chapter_number} 章启用混合生成模式")

    async def _generate_single_version(idx: int) -> Dict:
        try:
            # 🎨 混合生成：为每个版本选择不同的路由
            if mixed_generation_config:
                route_indices = mixed_generation_config.get("chapter", [0, 1, 0, 1, 2])
                route_index = route_indices[idx] if idx < len(route_indices) else 0

                # 如果是随机(-1)，从启用的路由中随机选一个
                if route_index == -1:
                    import random
                    enabled_routes = [i for i, r in enumerate(user_route_config["routes"]) if r.get("enabled")]
                    route_index = random.choice(enabled_routes) if enabled_routes else 0

                # 获取路由信息
                routes = user_route_config.get("routes", [])
                if route_index < len(routes) and routes[route_index].get("enabled"):
                    logger.info(f"第 {request.chapter_number} 章版本 {idx + 1} 使用路由 {route_index + 1}: {routes[route_index].get('model')}")

                    # 使用指定路由调用
                    messages = [
                        {"role": "system", "content": writer_prompt},
                        {"role": "user", "content": prompt_input}
                    ]
                    response = await _invoke_with_specific_route(
                        llm_service=llm_service,
                        user_route_config=user_route_config,
                        route_index=route_index,
                        messages=messages,
                        temperature=0.9,
                        timeout=600.0,
                        user_id=current_user.id,
                    )
                else:
                    # 路由无效，使用默认方式
                    response = await llm_service.get_llm_response(
                        system_prompt=writer_prompt,
                        conversation_history=[{"role": "user", "content": prompt_input}],
                        temperature=0.9,
                        user_id=current_user.id,
                        timeout=600.0,
                    )
            else:
                # 非混合模式，使用默认方式
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
                parsed_json = json.loads(normalized)
                return parsed_json
            except json.JSONDecodeError as parse_err:
                # ❌ 不再fallback到保存原始字符串，而是抛出异常
                logger.error(
                    "❌ 项目 %s 第 %s 章第 %s 个版本 JSON解析失败！\n"
                    "  错误: %s\n"
                    "  normalized前500字: %s...\n"
                    "  这可能是LLM返回了错误的JSON格式，或unwrap_markdown_json提取错误",
                    project_id,
                    request.chapter_number,
                    idx + 1,
                    parse_err,
                    normalized[:500] if normalized else ""
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"第 {request.chapter_number} 章版本 {idx + 1} JSON解析失败: {str(parse_err)}"
                )
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

    # 提取full_content字段和metadata
    contents: List[str] = []
    metadatas: List[Dict] = []  # ✅ 新增：保存3Agent模式生成的metadata
    for idx, variant in enumerate(raw_versions):
        if isinstance(variant, dict):
            # 优先提取full_content字段
            if "full_content" in variant and variant["full_content"]:
                full_content = variant["full_content"]

                # ✅ 强制类型检查：full_content必须是字符串
                if not isinstance(full_content, str):
                    logger.error(
                        f"❌ 第 {request.chapter_number} 章版本 {idx+1}: full_content类型错误！\n"
                        f"  期望类型: str (字符串)\n"
                        f"  实际类型: {type(full_content)}\n"
                        f"  实际值: {str(full_content)[:500]}..."
                    )

                    # 检查是否是Planner格式
                    if isinstance(full_content, dict):
                        planner_keys = ["analysis", "plan", "queries_summary"]
                        found = [k for k in planner_keys if k in full_content]
                        if found:
                            logger.error(
                                f"❌❌❌ 检测到Planner格式被错误保存到full_content！\n"
                                f"  包含Planner字段: {found}"
                            )

                    raise HTTPException(
                        status_code=500,
                        detail=f"第 {request.chapter_number} 章版本 {idx+1}: full_content必须是字符串，"
                               f"但收到了{type(full_content).__name__}类型"
                    )

                contents.append(full_content)
                logger.info(f"第 {request.chapter_number} 章版本 {idx+1}: 提取full_content，长度={len(full_content)}")
            elif "content" in variant and variant["content"]:
                content = variant["content"]

                # ✅ 强制类型检查：content必须是字符串
                if not isinstance(content, str):
                    logger.error(
                        f"❌ 第 {request.chapter_number} 章版本 {idx+1}: content类型错误！\n"
                        f"  期望类型: str (字符串)\n"
                        f"  实际类型: {type(content)}"
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"第 {request.chapter_number} 章版本 {idx+1}: content必须是字符串，"
                               f"但收到了{type(content).__name__}类型"
                    )

                contents.append(content)
                logger.info(f"第 {request.chapter_number} 章版本 {idx+1}: 提取content，长度={len(content)}")
            else:
                # ❌ 如果没有找到内容字段，抛出异常而不是保存JSON
                logger.error(
                    f"❌ 第 {request.chapter_number} 章版本 {idx+1}: 返回的JSON缺少full_content或content字段\n"
                    f"  返回的字段: {list(variant.keys())}\n"
                    f"  这可能是LLM返回了错误的格式"
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"第 {request.chapter_number} 章版本 {idx+1} 生成失败：返回的JSON缺少full_content或content字段，"
                           f"收到的字段为 {list(variant.keys())}"
                )
            
            # ✅ 新增：提取metadata（3Agent的对话历史、评分等）
            agent_metadata = variant.get("metadata", {})
            metadatas.append(agent_metadata if agent_metadata else None)
            if agent_metadata:
                logger.info(
                    f"第 {request.chapter_number} 章版本 {idx+1}: 已提取metadata"
                    f"（迭代{agent_metadata.get('iterations', 'N/A')}次，"
                    f"评分{agent_metadata.get('final_score', 'N/A')}）"
                )
        else:
            contents.append(str(variant))
            metadatas.append(None)
            logger.info(f"第 {request.chapter_number} 章版本 {idx+1}: variant不是dict，直接转字符串")

    # 保存版本（包含metadata）
    await novel_service.replace_chapter_versions(chapter, contents, metadatas)
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
        # 🔥 获取 blueprint 和分卷快照，用于生成摘要
        project_schema = await novel_service._serialize_project(project)
        blueprint_dict = project_schema.blueprint.model_dump()

        # 🔥 获取所有分卷的快照数据，并标注当前卷
        from sqlalchemy import select
        from ...models.novel import Volume

        volumes_stmt = select(Volume).where(Volume.project_id == project_id).order_by(Volume.volume_number)
        volumes_result = await session.execute(volumes_stmt)
        all_volumes = volumes_result.scalars().all()

        volumes_snapshot = []
        for vol in all_volumes:
            vol_data = {
                "volume_number": vol.volume_number,
                "title": vol.title,
                "characters": vol.characters or [],
                "relationships": vol.relationships or [],
                "world_setting": vol.world_setting or {},
                "is_current": False
            }
            # 标注当前章节所属的卷
            if chapter.volume_id and vol.id == chapter.volume_id:
                vol_data["is_current"] = True
            volumes_snapshot.append(vol_data)

        summary = await llm_service.get_summary(
            selected.content,
            temperature=0.15,
            user_id=current_user.id,
            timeout=180.0,
            blueprint_dict=blueprint_dict,
            volumes_snapshot=volumes_snapshot,
        )
        chapter.real_summary = remove_think_tags(summary)
        await session.commit()

        # ✅ 将选定版本写入向量库（libsql/siliconflow 模式）
        if settings.vector_store_enabled and settings.rag_provider in {"libsql", "siliconflow"}:
            try:
                ingestion_service = ChapterIngestionService(llm_service=llm_service)
                title = (
                    getattr(chapter, "title", None)
                    or (selected.metadata.get("title") if selected.metadata else None)
                    or ""
                )
                await ingestion_service.ingest_chapter(
                    project_id=project_id,
                    chapter_number=chapter.chapter_number,
                    title=title,
                    content=selected.content,
                    summary=chapter.real_summary,
                    user_id=current_user.id,
                )
            except Exception as e:  # pragma: no cover - 入库失败不阻断主流程
                logger.warning("章节向量入库失败: project=%s chapter=%s error=%s", project_id, chapter.chapter_number, e)

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

    # 🔥 获取所有分卷的快照数据，并标注当前卷
    from sqlalchemy import select
    from ...models.novel import Volume

    volumes_stmt = select(Volume).where(Volume.project_id == project_id).order_by(Volume.volume_number)
    volumes_result = await session.execute(volumes_stmt)
    all_volumes = volumes_result.scalars().all()

    current_volume_number = None
    volumes_snapshot = []
    for vol in all_volumes:
        vol_data = {
            "volume_number": vol.volume_number,
            "title": vol.title,
            "characters": vol.characters or [],
            "relationships": vol.relationships or [],
            "world_setting": vol.world_setting or {},
            "is_current": False
        }
        # 标注当前章节所属的卷
        if chapter.volume_id and vol.id == chapter.volume_id:
            vol_data["is_current"] = True
            current_volume_number = vol.volume_number
        volumes_snapshot.append(vol_data)

    logger.info(f"章节评估：第 {chapter.chapter_number} 章，传递 {len(volumes_snapshot)} 个卷的快照数据，当前卷为第 {current_volume_number} 卷")

    # print("blueprint_dict:",blueprint_dict)
    evaluator_payload = {
        "novel_blueprint": blueprint_dict,
        "volumes_snapshot": volumes_snapshot,
        "content_to_evaluate": {
            "chapter_number": chapter.chapter_number,
            "versions": versions_to_evaluate,
        },
    }

    # 使用AI Orchestrator的路由系统进行评估
    from ...services.ai_orchestrator_helper import call_ai_function
    from ...config.ai_function_config import AIFunctionType

    evaluation_raw = await call_ai_function(
        db_session=session,
        function=AIFunctionType.CHAPTER_EVALUATION,
        system_prompt=evaluator_prompt,
        user_prompt=json.dumps(evaluator_payload, ensure_ascii=False),
        user_id=current_user.id,
        response_format="json_object",
    )
    evaluation_clean = remove_think_tags(evaluation_raw)
    await novel_service.add_chapter_evaluation(chapter, None, evaluation_clean)
    logger.info("项目 %s 第 %s 章评估完成", project_id, request.chapter_number)

    return await _load_project_schema(novel_service, project_id, current_user.id)


async def evaluate_outline_versions(
    outline_versions: list,
    blueprint_dict: dict,
    llm_service: LLMService,
    prompt_service: PromptService,
    user_id: int,
    completed_chapters: list = None,
    previous_two_chapters: list = None,
    start_chapter: int = None,
    volumes_data: list = None
) -> int:
    """
    AI评估多个大纲版本，返回最佳版本的索引

    Args:
        outline_versions: 大纲版本列表
        blueprint_dict: 蓝图信息
        llm_service: LLM服务
        prompt_service: PromptService
        user_id: 用户ID
        completed_chapters: 已完成章节摘要列表
        previous_two_chapters: 前两章完整内容
        start_chapter: 新大纲起始章节号
        volumes_data: 所有分卷的快照数据

    Returns:
        最佳版本的索引（0-based）
    """
    try:
        # 1. 获取评估提示词
        evaluator_prompt_content = await prompt_service.get_prompt("outline_evaluation")

        if not evaluator_prompt_content:
            # 降级：使用通用评估提示词
            evaluator_prompt_content = await prompt_service.get_prompt("evaluation")

        if not evaluator_prompt_content:
            logger.warning("缺少大纲评估提示词，默认选择第一个版本")
            return 0

        # 2. 构建评估payload
        versions_to_evaluate = []
        for v in outline_versions:
            version_info = {
                "version_id": v["version_id"],
                "volume_title": v["data"].get("volume_title", ""),
                "chapters": v["data"].get("chapters", []),
                "characters": v["data"].get("characters", []),
                "total_chapters": len(v["data"].get("chapters", []))
            }
            versions_to_evaluate.append(version_info)

        # 🔥 传递所有卷的快照数据，并标注即将生成的新卷
        volumes_snapshot = []
        new_volume_number = 1
        if volumes_data and len(volumes_data) > 0:
            new_volume_number = len(volumes_data) + 1
            for vol in volumes_data:
                vol_snapshot = {
                    "volume_number": vol.get("volume_number"),
                    "title": vol.get("title", ""),
                    "characters": vol.get("characters", []),
                    "relationships": vol.get("relationships", []),
                    "world_setting": vol.get("world_setting", {}),
                    "is_current": False
                }
                volumes_snapshot.append(vol_snapshot)
            logger.info(f"大纲评估：传递 {len(volumes_snapshot)} 个已有卷的快照数据，即将生成第 {new_volume_number} 卷")

        evaluator_payload = {
            "novel_blueprint": blueprint_dict,
            "volumes_snapshot": volumes_snapshot,
            "new_volume_number": new_volume_number,
            "completed_chapters": completed_chapters or [],
            "previous_chapters_content": previous_two_chapters or [],
            "generation_context": {
                "start_chapter": start_chapter,
                "total_previous_chapters": len(completed_chapters) if completed_chapters else 0
            },
            "content_to_evaluate": {
                "type": "outline",
                "versions": versions_to_evaluate
            },
            "evaluation_criteria": [
                "情节连贯性和吸引力",
                "章节间节奏把控",
                "冲突和转折设计",
                "符合蓝图设定",
                "章节标题吸引力"
            ]
        }

        # 3. 调用AI评估（使用AI Orchestrator的路由系统）
        from ...services.ai_orchestrator_helper import call_ai_function
        from ...config.ai_function_config import AIFunctionType

        evaluation_response = await call_ai_function(
            db_session=llm_service.db_session,
            function=AIFunctionType.OUTLINE_EVALUATION,
            system_prompt=evaluator_prompt_content,
            user_prompt=json.dumps(evaluator_payload, ensure_ascii=False),
            user_id=user_id,
            response_format="json_object",
        )

        evaluation_clean = unwrap_markdown_json(remove_think_tags(evaluation_response))
        evaluation_data = json.loads(evaluation_clean)

        # 4. 提取最佳版本
        best_choice = evaluation_data.get("best_choice")
        if best_choice and isinstance(best_choice, int):
            best_index = best_choice - 1  # 转为0-based
            if 0 <= best_index < len(outline_versions):
                logger.info(f"AI评估推荐大纲版本 {best_choice}，原因: {evaluation_data.get('reason_for_choice', '未提供')}")
                return best_index

        logger.warning("AI评估结果无效，默认选择第一个版本")
        return 0

    except Exception as e:
        logger.error(f"大纲评估失败: {str(e)}，默认选择第一个版本")
        return 0


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

    # 🔄 生成多个版本
    version_count = max(1, min(request.version_count, 5))  # 限制在1-5之间
    outline_versions = []

    # 🎨 读取混合生成配置
    user_route_config = await llm_service.get_user_route_config(current_user.id)
    mixed_generation_config = None
    if user_route_config and user_route_config.get("mixedGeneration", {}).get("enabled"):
        mixed_generation_config = user_route_config["mixedGeneration"]
        logger.info(f"项目 {project_id} 启用混合生成模式：{mixed_generation_config}")

    for version_idx in range(version_count):
        logger.info(f"项目 {project_id} 正在生成大纲版本 {version_idx + 1}/{version_count}")

        try:
            # 🎨 混合生成：为每个版本选择不同的路由
            if mixed_generation_config:
                route_indices = mixed_generation_config.get("outline", [0, 1, 2, 0, 1])
                route_index = route_indices[version_idx] if version_idx < len(route_indices) else 0

                # 如果是随机(-1)，从启用的路由中随机选一个
                if route_index == -1:
                    import random
                    enabled_routes = [i for i, r in enumerate(user_route_config["routes"]) if r.get("enabled")]
                    route_index = random.choice(enabled_routes) if enabled_routes else 0

                # 获取路由信息
                routes = user_route_config.get("routes", [])
                if route_index < len(routes) and routes[route_index].get("enabled"):
                    route = routes[route_index]
                    logger.info(f"版本 {version_idx + 1} 使用路由 {route_index + 1}: {route.get('model')}")

                    # 使用指定路由调用
                    messages = [
                        {"role": "system", "content": outline_prompt},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
                    ]
                    response = await _invoke_with_specific_route(
                        llm_service=llm_service,
                        user_route_config=user_route_config,
                        route_index=route_index,
                        messages=messages,
                        temperature=0.7 + (version_idx * 0.1),
                        timeout=360.0,
                        user_id=current_user.id,
                    )
                else:
                    # 路由无效，使用默认方式
                    response = await llm_service.get_llm_response(
                        system_prompt=outline_prompt,
                        conversation_history=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                        temperature=0.7 + (version_idx * 0.1),
                        user_id=current_user.id,
                        timeout=360.0,
                    )
            else:
                # 非混合模式，使用默认方式
                response = await llm_service.get_llm_response(
                    system_prompt=outline_prompt,
                    conversation_history=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                    temperature=0.7 + (version_idx * 0.1),
                    user_id=current_user.id,
                    timeout=360.0,
                )
            normalized = unwrap_markdown_json(remove_think_tags(response))
            version_data = json.loads(normalized)

            # 验证基本结构
            if version_data.get("chapters"):
                outline_versions.append({
                    "version_id": version_idx + 1,
                    "data": version_data,
                    "raw_response": normalized[:500]  # 保留前500字用于日志
                })
                logger.info(f"版本 {version_idx + 1} 生成成功，包含 {len(version_data.get('chapters', []))} 个章节")
            else:
                logger.warning(f"版本 {version_idx + 1} 生成的内容缺少章节数据")

        except json.JSONDecodeError as exc:
            logger.warning(f"版本 {version_idx + 1} JSON解析失败: {exc}")
            continue
        except Exception as e:
            logger.error(f"版本 {version_idx + 1} 生成失败: {str(e)}")
            continue

    if not outline_versions:
        raise HTTPException(
            status_code=500,
            detail="所有版本均生成失败，请检查提示词或重试"
        )

    # 🎯 AI评估选择最佳版本（只有多版本时才评估）
    if len(outline_versions) > 1:
        logger.info(f"项目 {project_id} 开始AI评估 {len(outline_versions)} 个大纲版本")
        best_version_idx = await evaluate_outline_versions(
            outline_versions=outline_versions,
            blueprint_dict=blueprint_dict,
            llm_service=llm_service,
            prompt_service=prompt_service,
            user_id=current_user.id,
            completed_chapters=completed_chapters,
            previous_two_chapters=previous_two_chapters,
            start_chapter=request.start_chapter,
            volumes_data=volumes_data
        )
        data = outline_versions[best_version_idx]["data"]
        logger.info(f"项目 {project_id} AI选择了版本 {best_version_idx + 1} 作为最佳大纲")
    else:
        # 只有一个版本，直接使用
        data = outline_versions[0]["data"]
        logger.info(f"项目 {project_id} 只生成了1个版本，直接使用")

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
        # 🔥 获取 blueprint 和分卷快照，用于生成摘要
        project_schema = await novel_service._serialize_project(project)
        blueprint_dict = project_schema.blueprint.model_dump()

        # 🔥 获取所有分卷的快照数据，并标注当前卷
        from sqlalchemy import select
        from ...models.novel import Volume

        volumes_stmt = select(Volume).where(Volume.project_id == project_id).order_by(Volume.volume_number)
        volumes_result = await session.execute(volumes_stmt)
        all_volumes = volumes_result.scalars().all()

        volumes_snapshot = []
        for vol in all_volumes:
            vol_data = {
                "volume_number": vol.volume_number,
                "title": vol.title,
                "characters": vol.characters or [],
                "relationships": vol.relationships or [],
                "world_setting": vol.world_setting or {},
                "is_current": False
            }
            # 标注当前章节所属的卷
            if chapter.volume_id and vol.id == chapter.volume_id:
                vol_data["is_current"] = True
            volumes_snapshot.append(vol_data)

        summary = await llm_service.get_summary(
            request.content,
            temperature=0.15,
            user_id=current_user.id,
            timeout=180.0,
            blueprint_dict=blueprint_dict,
            volumes_snapshot=volumes_snapshot,
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
