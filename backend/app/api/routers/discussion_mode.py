"""
讨论模式 API 路由

提供讨论模式的 RESTful API 接口。
"""

from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import asyncio

from ...db.database import get_session
from ...db.session import AsyncSessionLocal
from ..dependencies import get_current_user
from ...models.user import UserInDB
from ...models.novel import Chapter, ChapterVersion, Volume
from ...schemas.discussion_mode import (
    GenerateChapterRequest,
    GenerateChapterResponse,
    GenerateOutlineRequest,
    GenerateOutlineResponse,
    DiscussionModeConfig,
    DialogueSummary,
    VolumeDecision,
)
from ...services.agent_dialogue import DiscussionMode
from ...services.agent_dialogue.state import DialogueConfig
from ...services.llm_service import LLMService
from ...services.gemini_rag_service import GeminiRAGService
from ...services.fanqie_publisher_service import FanqiePublisherService
from ...services.novel_service import NovelService
from ...models.novel import Volume, ChapterVersion
from sqlalchemy import select, func
from ...core.config import settings
from ...repositories.system_config_repository import SystemConfigRepository
from ...services.vector_store_service import VectorStoreService
from ...models.novel import Chapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discussion-mode", tags=["讨论模式"])


def get_llm_service(session: AsyncSession) -> LLMService:
    """获取 LLM 服务（绑定当前会话）"""
    return LLMService(session)


class DiscussionRAG:
    """讨论模式 RAG 适配器：复用系统 rag.provider 配置"""

    def __init__(self, session: AsyncSession, llm_service: LLMService):
        self.session = session
        self.llm_service = llm_service

    async def _get_provider(self) -> str:
        provider = settings.rag_provider or ""
        try:
            repo = SystemConfigRepository(self.session)
            record = await repo.get_by_key("rag.provider")
            if record and record.value:
                provider = record.value
        except Exception as e:
            logger.warning(f"[DiscussionRAG] 读取rag.provider失败，使用默认: {e}")
        return (provider or "").strip().lower()

    async def search(self, project_id: str, query: str, top_k: int = 5):
        provider = await self._get_provider()

        # 向量库优先
        if provider in ["libsql", "siliconflow"] and settings.vector_store_enabled:
            try:
                vector_service = VectorStoreService()
                embedding = await self.llm_service.get_embedding(query)
                chunks = await vector_service.query_chunks(
                    project_id=project_id,
                    embedding=embedding,
                    top_k=top_k
                )
                if chunks:
                    return [
                        {
                            "chapter_number": c.chapter_number,
                            "chapter_title": c.chapter_title or "",
                            "content_snippet": (c.content or "")[:500],
                        }
                        for c in chunks
                    ]
            except Exception as e:
                logger.warning(f"[DiscussionRAG] 向量检索失败，降级: {e}")

        # Gemini 次选
        if provider == "gemini":
            try:
                gemini = GeminiRAGService(self.session)
                return await gemini.search(project_id=project_id, query=query, top_k=top_k)
            except Exception as e:
                logger.warning(f"[DiscussionRAG] Gemini 检索失败，降级: {e}")

        # DB 关键词回退
        try:
            stmt = (
                select(Chapter)
                .where(Chapter.project_id == str(project_id))
                .order_by(Chapter.chapter_number.desc())
                .limit(top_k * 3)
            )
            res = await self.session.execute(stmt)
            chapters = res.scalars().all()
            results = []
            for ch in chapters:
                if ch.selected_version and query in (ch.selected_version.content or ""):
                    content = ch.selected_version.content
                    pos = content.find(query)
                    snippet = content[max(0, pos - 100): pos + 200]
                    results.append({
                        "chapter_number": ch.chapter_number,
                        "chapter_title": f"第{ch.chapter_number}章",
                        "content_snippet": snippet,
                    })
                    if len(results) >= top_k:
                        break
            return results
        except Exception as e:
            logger.error(f"[DiscussionRAG] 数据库检索失败: {e}")
            return []


def get_rag_service(session: AsyncSession, llm_service: LLMService):
    """获取 RAG 适配器（共用 rag.provider 配置）"""
    return DiscussionRAG(session, llm_service)


def _convert_config(config: Optional[DiscussionModeConfig]) -> Optional[DialogueConfig]:
    """转换配置"""
    if not config:
        return None
    
    return DialogueConfig(
        max_iterations=config.max_iterations,
        approval_threshold=config.approval_threshold,
        discussion_threshold=config.discussion_threshold,
        timeout_seconds=config.timeout_seconds,
        enable_tools=config.enable_tools,
        verbose=config.verbose,
        # 分卷配置
        enable_volume_decision=config.enable_volume_decision,
        min_chapters_per_volume=config.min_chapters_per_volume,
        max_chapters_per_volume=config.max_chapters_per_volume,
    )


async def _load_volumes_snapshot(session: AsyncSession, project_id: int) -> List[Dict[str, Any]]:
    """从数据库加载分卷快照（如果调用方未提供）"""
    stmt = select(Volume).where(Volume.project_id == str(project_id)).order_by(Volume.volume_number)
    result = await session.execute(stmt)
    volumes = result.scalars().all()
    snapshot = []
    for vol in volumes:
        snapshot.append({
            "volume_number": vol.volume_number,
            "title": vol.title,
            "description": vol.description or "",
            "characters": vol.characters or [],
            "relationships": vol.relationships or [],
            "world_setting": vol.world_setting or {},
        })
    return snapshot


@router.post("/generate-chapter", response_model=GenerateChapterResponse)
async def generate_chapter(
    request: GenerateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    使用讨论模式生成章节
    
    讨论模式是一个真正的多 Agent 对话系统，由 Coordinator 协调 Planner、Writer、Reviewer 进行协作对话。
    
    与普通 3-Agent 模式的区别：
    - Agent 之间可以互相提问和回应
    - 遇到分歧时会召集三方讨论
    - Coordinator 会仲裁并做出决定
    - 完整的对话历史记录
    """
    logger.info(f"[API] 讨论模式生成章节: project={request.project_id}, chapter={request.chapter_number}")
    
    # 基础校验
    if request.auto_upload and not request.fanqie_account:
        raise HTTPException(status_code=400, detail="auto_upload 为 True 时 fanqie_account 为必填")

    try:
        # 初始化服务
        llm_service = get_llm_service(session)
        rag_service = get_rag_service(session, llm_service)
        
        # 转换配置
        config = _convert_config(request.config)
        
        # 自动补全分卷快照（如果未传）
        volumes_snapshot = request.volumes_snapshot
        if not volumes_snapshot:
            volumes_snapshot = await _load_volumes_snapshot(session, request.project_id)

        # 创建讨论模式实例
        discussion_mode = DiscussionMode(
            llm_service=llm_service,
            rag_service=rag_service,
            config=config,
        )
        
        # 构建上下文
        context = {
            "genre": request.genre,
            "word_count": request.word_count,
            "previous_summary": request.previous_summary,
            "character_states": request.character_states,
            "blueprint_summary": request.blueprint_summary,
            # 分卷相关上下文
            "current_volume_chapters": request.current_volume_chapters,
            "current_volume_number": request.current_volume_number,
            "volumes_snapshot": volumes_snapshot,
        }
        
        # 生成章节
        result = await discussion_mode.generate_chapter(
            project_id=request.project_id,
            chapter_number=request.chapter_number,
            context={**context, "user_id": current_user.id},
        )

        # ========== 章节落库 ==========
        saved_chapter_id = None
        if result.get("success") and result.get("content"):
            saved_chapter_id = await _save_chapter_to_db(
                session=session,
                project_id=request.project_id,
                chapter_number=request.chapter_number,
                content=result.get("content", ""),
                title=result.get("title", f"第{request.chapter_number}章"),
                volume_decision=result.get("volume_decision"),
                current_volume_number=request.current_volume_number,
            )
            logger.info(f"[DB] 章节已落库: chapter_id={saved_chapter_id}")
        
        # ========== 自动上传番茄（基于落库后的章节）==========
        if request.auto_upload and request.fanqie_account and saved_chapter_id:
            asyncio.create_task(
                _upload_chapter_to_fanqie(
                    project_id=request.project_id,
                    fanqie_account=request.fanqie_account,
                    chapter_number=request.chapter_number,
                )
            )
        
        # 转换响应
        dialogue_summary = None
        if result.get("dialogue_summary"):
            summary = result["dialogue_summary"]
            dialogue_summary = DialogueSummary(
                total_messages=summary.get("total_messages", 0),
                by_sender=summary.get("by_sender", {}),
                by_type=summary.get("by_type", {}),
                decisions_count=summary.get("decisions_count", 0),
                artifacts=summary.get("artifacts", []),
                pending_questions=summary.get("pending_questions", 0),
            )
        
        # 转换分卷决策
        volume_decision = None
        if result.get("volume_decision"):
            vd = result["volume_decision"]
            volume_decision = VolumeDecision(
                should_create_volume=vd.get("should_create_volume", False),
                volume_title=vd.get("volume_title"),
                reason=vd.get("reason"),
            )
        
        return GenerateChapterResponse(
            success=result.get("success", False),
            content=result.get("content"),
            title=result.get("title"),
            final_score=result.get("final_score", 0),
            iterations=result.get("iterations", 0),
            total_duration_seconds=result.get("total_duration_seconds", 0),
            volume_decision=volume_decision,
            dialogue_summary=dialogue_summary,
            decisions=result.get("decisions", []),
            dialogue_export=result.get("dialogue_export"),
            error=result.get("error"),
        )
        
    except Exception as e:
        logger.error(f"讨论模式生成章节失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-outline", response_model=GenerateOutlineResponse)
async def generate_outline(
    request: GenerateOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    使用讨论模式生成大纲
    
    生成指定范围内的章节大纲，通过 Agent 对话协作完成。
    """
    logger.info(f"[API] 讨论模式生成大纲: project={request.project_id}, "
                f"chapters={request.start_chapter}-{request.end_chapter}")
    
    try:
        llm_service = get_llm_service(session)
        rag_service = get_rag_service(session, llm_service)
        
        config = _convert_config(request.config)
        
        discussion_mode = DiscussionMode(
            llm_service=llm_service,
            rag_service=rag_service,
            config=config,
        )
        
        context = {
            "genre": request.genre,
            "blueprint_summary": request.blueprint_summary,
            "current_progress": request.current_progress,
        }
        
        result = await discussion_mode.generate_outline(
            project_id=request.project_id,
            start_chapter=request.start_chapter,
            end_chapter=request.end_chapter,
            context={**context, "user_id": current_user.id},
        )
        
        # 解析大纲内容
        outline = None
        if result.get("success") and result.get("content"):
            content = result["content"]
            if isinstance(content, dict) and "outline" in content:
                outline = content["outline"]
            elif isinstance(content, list):
                outline = content
        
        dialogue_summary = None
        if result.get("dialogue_summary"):
            summary = result["dialogue_summary"]
            dialogue_summary = DialogueSummary(
                total_messages=summary.get("total_messages", 0),
                by_sender=summary.get("by_sender", {}),
                by_type=summary.get("by_type", {}),
                decisions_count=summary.get("decisions_count", 0),
                artifacts=summary.get("artifacts", []),
                pending_questions=summary.get("pending_questions", 0),
            )
        
        return GenerateOutlineResponse(
            success=result.get("success", False),
            outline=outline,
            final_score=result.get("final_score", 0),
            iterations=result.get("iterations", 0),
            total_duration_seconds=result.get("total_duration_seconds", 0),
            dialogue_summary=dialogue_summary,
            decisions=result.get("decisions", []),
            error=result.get("error"),
        )
        
    except Exception as e:
        logger.error(f"讨论模式生成大纲失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/default")
async def get_default_config():
    """
    获取默认配置
    """
    return DiscussionModeConfig()


@router.get("/info")
async def get_info():
    """
    获取讨论模式信息
    """
    return {
        "name": "讨论模式 (Discussion Mode)",
        "description": "一个真正的多 Agent 对话系统，由 Coordinator 协调 Planner、Writer、Reviewer 进行协作对话。",
        "features": [
            "Agent 之间可以互相提问和回应",
            "共享对话历史，信息透明",
            "遇到分歧时召集三方讨论",
            "Coordinator 仲裁并做出决定",
            "完整的对话记录导出",
        ],
        "agents": {
            "coordinator": "协调者 - 决定发言顺序、仲裁冲突、判断结束",
            "planner": "规划者 - 分析项目、规划章节结构",
            "writer": "创作者 - 撰写章节内容",
            "reviewer": "审核者 - 审核质量、提供反馈",
        },
        "phases": [
            "planning - 规划阶段",
            "drafting - 起草阶段",
            "reviewing - 审核阶段",
            "discussing - 三方讨论（如需要）",
            "revising - 修改阶段",
            "approved/end - 结束",
        ],
        "default_config": DiscussionModeConfig().model_dump(),
    }


async def _save_chapter_to_db(
    session: AsyncSession,
    project_id: int,
    chapter_number: int,
    content: str,
    title: str,
    volume_decision: Optional[dict],
    current_volume_number: int,
) -> Optional[int]:
    """
    将生成的章节保存到数据库
    
    Args:
        session: 数据库会话
        project_id: 项目 ID
        chapter_number: 章节号
        content: 章节内容
        title: 章节标题
        volume_decision: 分卷决策结果
        current_volume_number: 当前卷号
    
    Returns:
        保存的章节 ID
    """
    try:
        novel_service = NovelService(session)
        
        # ========== 处理分卷决策 ==========
        volume_id = None
        target_volume_number = current_volume_number
        
        if volume_decision and volume_decision.get("should_create_volume"):
            # 需要创建新卷
            new_volume_title = volume_decision.get("volume_title", "新的篇章")
            new_volume_number = current_volume_number + 1
            
            # 检查新卷是否已存在
            existing_stmt = select(Volume).where(
                Volume.project_id == str(project_id),
                Volume.volume_number == new_volume_number
            )
            existing_result = await session.execute(existing_stmt)
            existing_volume = existing_result.scalars().first()
            
            if not existing_volume:
                # 创建新卷
                new_volume = Volume(
                    project_id=str(project_id),
                    volume_number=new_volume_number,
                    title=new_volume_title,
                    description=volume_decision.get("reason", ""),
                )
                session.add(new_volume)
                await session.flush()
                volume_id = new_volume.id
                logger.info(f"[DB] 创建新卷: 第{new_volume_number}卷《{new_volume_title}》")
            else:
                volume_id = existing_volume.id
            
            target_volume_number = new_volume_number
        else:
            # 使用当前卷
            volume_stmt = select(Volume).where(
                Volume.project_id == str(project_id),
                Volume.volume_number == current_volume_number
            )
            volume_result = await session.execute(volume_stmt)
            current_volume = volume_result.scalars().first()
            
            if current_volume:
                volume_id = current_volume.id
            else:
                # 创建默认卷
                default_volume = Volume(
                    project_id=str(project_id),
                    volume_number=1,
                    title="第一卷",
                    description="",
                )
                session.add(default_volume)
                await session.flush()
                volume_id = default_volume.id
        
        # ========== 创建或更新章节 ==========
        chapter = await novel_service.get_or_create_chapter(
            project_id=str(project_id),
            chapter_number=chapter_number
        )
        
        # 更新章节的 volume_id（如果分卷有变化）
        if volume_id and chapter.volume_id != volume_id:
            chapter.volume_id = volume_id
        
        # ========== 创建章节版本 ==========
        word_count = len(content)
        version = ChapterVersion(
            chapter_id=chapter.id,
            content=content,
            version_label="discussion_mode_v1",
            provider="discussion_mode",
            metadata_={
                "title": title,
                "word_count": word_count,
                "source": "discussion_mode",
                "volume_number": target_volume_number,
            },
        )
        session.add(version)
        await session.flush()
        
        # 更新章节状态
        chapter.selected_version_id = version.id
        chapter.word_count = word_count
        chapter.status = "completed"
        
        await session.commit()
        
        logger.info(f"[DB] 章节落库成功: project={project_id}, chapter={chapter_number}, "
                   f"volume={target_volume_number}, words={word_count}")
        
        return chapter.id
        
    except Exception as e:
        logger.error(f"[DB] 章节落库失败: {e}", exc_info=True)
        await session.rollback()
        return None


async def _upload_chapter_to_fanqie(
    project_id: int,
    fanqie_account: str,
    chapter_number: int,
) -> None:
    """
    异步上传章节到番茄小说（基于已落库的章节）
    
    注意：此函数从数据库读取已保存的章节，而非直接使用内存中的内容
    """
    try:
        async with AsyncSessionLocal() as db:
            async with FanqiePublisherService(headless=True) as publisher:
                result = await publisher.upload_novel_to_fanqie(
                    db=db,
                    project_id=project_id,
                    account=fanqie_account,
                    upload_interval=0
                )
                if result.get("success"):
                    logger.info(f"[Fanqie] 第{chapter_number}章上传成功（账号: {fanqie_account}）")
                else:
                    logger.warning(f"[Fanqie] 第{chapter_number}章上传失败: {result.get('error', '未知错误')}")
    except Exception as e:
        logger.error(f"[Fanqie] 第{chapter_number}章上传异常: {e}")
