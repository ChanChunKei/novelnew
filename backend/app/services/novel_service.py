from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

_PREFERRED_CONTENT_KEYS: tuple[str, ...] = (
    "full_content",  # 优先提取full_content，这是AI生成章节时返回的完整内容字段
    "content",
    "chapter_content",
    "chapter_text",
    "text",
    "body",
    "story",
    "chapter",
    "real_summary",
    "summary",
)


def _normalize_version_content(raw_content: Any, metadata: Any) -> str:
    text = _coerce_text(metadata)
    if not text:
        text = _coerce_text(raw_content)
    return text or ""


def _coerce_text(value: Any) -> Optional[str]:
    import logging
    logger = logging.getLogger(__name__)

    if value is None:
        return None
    if isinstance(value, str):
        return _clean_string(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        logger.info(f"🔍 _coerce_text处理dict，keys={list(value.keys())}")
        for key in _PREFERRED_CONTENT_KEYS:
            if key in value and value[key]:
                logger.info(f"✅ 找到字段 '{key}'，值类型={type(value[key])}, 值长度={len(str(value[key]))}")
                nested = _coerce_text(value[key])
                if nested:
                    logger.info(f"✅ 成功提取字段 '{key}'，提取后长度={len(nested)}")
                    return nested
                else:
                    logger.warning(f"⚠️ 字段 '{key}' 提取后为空")
        logger.warning(f"⚠️ 未找到任何有效字段，返回完整JSON")
        return _clean_string(json.dumps(value, ensure_ascii=False))
    if isinstance(value, (list, tuple, set)):
        parts = [text for text in (_coerce_text(item) for item in value) if text]
        if parts:
            return "\n".join(parts)
        return None
    return _clean_string(str(value))


def _clean_string(text: str) -> str:
    import logging
    import re
    logger = logging.getLogger(__name__)

    stripped = text.strip()
    if not stripped:
        return stripped

    # 检测JSON格式
    if stripped.startswith("{") and stripped.endswith("}"):
        logger.info(f"🔍 _clean_string检测到JSON格式，长度={len(stripped)}")
        try:
            parsed = json.loads(stripped)
            logger.info(f"✅ JSON解析成功，keys={list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}")
            coerced = _coerce_text(parsed)
            if coerced:
                logger.info(f"✅ _coerce_text提取成功，提取后长度={len(coerced)}")
                return coerced
            else:
                logger.warning(f"⚠️ _coerce_text提取失败，返回None")
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ JSON解析失败: {e}，尝试手动提取full_content")
            # JSON格式不正确，尝试手动提取full_content字段
            # 匹配 "full_content":"..." 或 "full_content": "..."
            match = re.search(r'"full_content"\s*:\s*"(.*?)"\s*}', stripped, re.DOTALL)
            if match:
                content = match.group(1)
                logger.info(f"✅ 手动提取full_content成功，长度={len(content)}")
                return content
            # 尝试提取content字段
            match = re.search(r'"content"\s*:\s*"(.*?)"\s*[,}]', stripped, re.DOTALL)
            if match:
                content = match.group(1)
                logger.info(f"✅ 手动提取content成功，长度={len(content)}")
                return content
            logger.warning(f"⚠️ 手动提取失败，返回原始文本")

    if stripped.startswith('"') and stripped.endswith('"') and len(stripped) >= 2:
        stripped = stripped[1:-1]
    return (
        stripped.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    BlueprintCharacter,
    BlueprintRelationship,
    Chapter,
    ChapterEvaluation,
    ChapterOutline,
    ChapterVersion,
    NovelBlueprint,
    NovelConversation,
    NovelProject,
    Volume,
)
from ..repositories.novel_repository import NovelRepository
from ..schemas.admin import AdminNovelSummary
from ..schemas.novel import (
    Blueprint,
    Chapter as ChapterSchema,
    ChapterGenerationStatus,
    ChapterOutline as ChapterOutlineSchema,
    NovelProject as NovelProjectSchema,
    NovelProjectSummary,
    NovelSectionResponse,
    NovelSectionType,
    Volume as VolumeSchema,
)


class NovelService:
    """小说项目服务，基于拆表后的结构提供聚合与业务操作。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = NovelRepository(session)

    # ------------------------------------------------------------------
    # 项目与摘要
    # ------------------------------------------------------------------
    async def create_project(self, user_id: int, title: str, initial_prompt: str) -> NovelProject:
        project = NovelProject(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            initial_prompt=initial_prompt,
        )
        blueprint = NovelBlueprint(project=project)
        self.session.add_all([project, blueprint])
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def ensure_project_owner(self, project_id: str, user_id: int) -> NovelProject:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if project.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
        return project

    async def update_project_title(self, project_id: str, user_id: int, new_title: str) -> NovelProject:
        """更新项目标题"""
        project = await self.ensure_project_owner(project_id, user_id)
        project.title = new_title
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def update_fanqie_book_id(self, project_id: str, user_id: int, fanqie_book_id: str) -> NovelProject:
        """更新番茄小说book_id"""
        project = await self.ensure_project_owner(project_id, user_id)
        project.fanqie_book_id = fanqie_book_id
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def get_project_schema(self, project_id: str, user_id: int) -> NovelProjectSchema:
        project = await self.ensure_project_owner(project_id, user_id)
        return await self._serialize_project(project)

    async def get_section_data(
        self,
        project_id: str,
        user_id: int,
        section: NovelSectionType,
    ) -> NovelSectionResponse:
        project = await self.ensure_project_owner(project_id, user_id)
        return self._build_section_response(project, section)

    async def get_chapter_schema(
        self,
        project_id: str,
        user_id: int,
        chapter_number: int,
    ) -> ChapterSchema:
        project = await self.ensure_project_owner(project_id, user_id)
        return self._build_chapter_schema(project, chapter_number)

    async def list_projects_for_user(self, user_id: int) -> List[NovelProjectSummary]:
        projects = await self.repo.list_by_user(user_id)
        summaries: List[NovelProjectSummary] = []
        for project in projects:
            blueprint = project.blueprint
            genre = blueprint.genre if blueprint and blueprint.genre else "未知"
            outlines = project.outlines
            chapters = project.chapters
            total = len(outlines) or len(chapters)
            completed = sum(1 for chapter in chapters if chapter.selected_version_id)
            summaries.append(
                NovelProjectSummary(
                    id=project.id,
                    title=project.title,
                    genre=genre,
                    last_edited=project.updated_at.isoformat() if project.updated_at else "未知",
                    completed_chapters=completed,
                    total_chapters=total,
                )
            )
        return summaries

    async def list_projects_for_admin(self) -> List[AdminNovelSummary]:
        projects = await self.repo.list_all()
        summaries: List[AdminNovelSummary] = []
        for project in projects:
            blueprint = project.blueprint
            genre = blueprint.genre if blueprint and blueprint.genre else "未知"
            outlines = project.outlines
            chapters = project.chapters
            total = len(outlines) or len(chapters)
            completed = sum(1 for chapter in chapters if chapter.selected_version_id)
            owner = project.owner
            summaries.append(
                AdminNovelSummary(
                    id=project.id,
                    title=project.title,
                    owner_id=owner.id if owner else 0,
                    owner_username=owner.username if owner else "未知",
                    genre=genre,
                    last_edited=project.updated_at.isoformat() if project.updated_at else "",
                    completed_chapters=completed,
                    total_chapters=total,
                )
            )
        return summaries

    async def delete_projects(self, project_ids: List[str], user_id: int) -> None:
        for pid in project_ids:
            project = await self.ensure_project_owner(pid, user_id)
            await self.repo.delete(project)
        await self.session.commit()

    async def count_projects(self) -> int:
        result = await self.session.execute(select(func.count(NovelProject.id)))
        return result.scalar_one()

    # ------------------------------------------------------------------
    # 对话管理
    # ------------------------------------------------------------------
    async def list_conversations(self, project_id: str) -> List[NovelConversation]:
        stmt = (
            select(NovelConversation)
            .where(NovelConversation.project_id == project_id)
            .order_by(NovelConversation.seq.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def append_conversation(self, project_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        result = await self.session.execute(
            select(func.max(NovelConversation.seq)).where(NovelConversation.project_id == project_id)
        )
        current_max = result.scalar()
        next_seq = (current_max or 0) + 1
        convo = NovelConversation(
            project_id=project_id,
            seq=next_seq,
            role=role,
            content=content,
            metadata=metadata,
        )
        self.session.add(convo)
        await self.session.commit()
        await self._touch_project(project_id)

    # ------------------------------------------------------------------
    # 蓝图管理
    # ------------------------------------------------------------------
    async def replace_blueprint(self, project_id: str, blueprint: Blueprint) -> None:
        record = await self.session.get(NovelBlueprint, project_id)
        if not record:
            record = NovelBlueprint(project_id=project_id)
            self.session.add(record)
        record.title = blueprint.title
        record.target_audience = blueprint.target_audience
        record.genre = blueprint.genre
        record.style = blueprint.style
        record.tone = blueprint.tone
        record.one_sentence_summary = blueprint.one_sentence_summary
        record.full_synopsis = blueprint.full_synopsis
        record.world_setting = blueprint.world_setting

        await self.session.execute(delete(BlueprintCharacter).where(BlueprintCharacter.project_id == project_id))
        for index, data in enumerate(blueprint.characters):
            self.session.add(
                BlueprintCharacter(
                    project_id=project_id,
                    name=data.get("name", ""),
                    identity=data.get("identity"),
                    personality=data.get("personality"),
                    goals=data.get("goals"),
                    abilities=data.get("abilities"),
                    relationship_to_protagonist=data.get("relationship_to_protagonist"),
                    extra={k: v for k, v in data.items() if k not in {
                        "name",
                        "identity",
                        "personality",
                        "goals",
                        "abilities",
                        "relationship_to_protagonist",
                    }},
                    position=index,
                )
            )

        await self.session.execute(delete(BlueprintRelationship).where(BlueprintRelationship.project_id == project_id))
        for index, relation in enumerate(blueprint.relationships):
            self.session.add(
                BlueprintRelationship(
                    project_id=project_id,
                    character_from=relation.character_from,
                    character_to=relation.character_to,
                    description=relation.description,
                    position=index,
                )
            )

        # 处理分卷
        await self.session.execute(delete(Volume).where(Volume.project_id == project_id))
        volume_id_map = {}  # volume_number -> volume_id
        for volume in blueprint.volumes:
            # 🔥 提取第一卷的快照数据（如果有）
            snapshot_characters = None
            snapshot_relationships = None
            snapshot_world_setting = None

            if volume.volume_number == 1:
                # 第一卷可能包含快照数据
                snapshot_characters = volume.characters
                snapshot_relationships = volume.relationships
                snapshot_world_setting = volume.world_setting

            vol_record = Volume(
                project_id=project_id,
                volume_number=volume.volume_number,
                title=volume.title,
                description=volume.description,
                characters=snapshot_characters,
                relationships=snapshot_relationships,
                world_setting=snapshot_world_setting,
            )
            self.session.add(vol_record)
            await self.session.flush()  # 获取ID
            volume_id_map[volume.volume_number] = vol_record.id

        # 如果没有分卷,创建默认分卷
        if not blueprint.volumes:
            default_volume = Volume(
                project_id=project_id,
                volume_number=1,
                title="默认",
                description="第一卷",
            )
            self.session.add(default_volume)
            await self.session.flush()
            volume_id_map[1] = default_volume.id

        await self.session.execute(delete(ChapterOutline).where(ChapterOutline.project_id == project_id))
        for outline in blueprint.chapter_outline:
            # 确定章节所属分卷
            volume_id = None
            if outline.volume_number and outline.volume_number in volume_id_map:
                volume_id = volume_id_map[outline.volume_number]
            elif 1 in volume_id_map:
                volume_id = volume_id_map[1]  # 默认第一卷

            self.session.add(
                ChapterOutline(
                    project_id=project_id,
                    volume_id=volume_id,
                    chapter_number=outline.chapter_number,
                    title=outline.title,
                    summary=outline.summary,
                )
            )

        await self.session.commit()
        await self._touch_project(project_id)

    async def patch_blueprint(self, project_id: str, patch: Dict) -> None:
        blueprint = await self.session.get(NovelBlueprint, project_id)
        if not blueprint:
            blueprint = NovelBlueprint(project_id=project_id)
            self.session.add(blueprint)

        if "one_sentence_summary" in patch:
            blueprint.one_sentence_summary = patch["one_sentence_summary"]
        if "full_synopsis" in patch:
            blueprint.full_synopsis = patch["full_synopsis"]
        if "world_setting" in patch and patch["world_setting"] is not None:
            # 创建新字典对象以触发 SQLAlchemy 的变更检测
            existing = blueprint.world_setting or {}
            blueprint.world_setting = {**existing, **patch["world_setting"]}
        if "characters" in patch and patch["characters"] is not None:
            await self.session.execute(delete(BlueprintCharacter).where(BlueprintCharacter.project_id == project_id))
            for index, data in enumerate(patch["characters"]):
                self.session.add(
                    BlueprintCharacter(
                        project_id=project_id,
                        name=data.get("name", ""),
                        identity=data.get("identity"),
                        personality=data.get("personality"),
                        goals=data.get("goals"),
                        abilities=data.get("abilities"),
                        relationship_to_protagonist=data.get("relationship_to_protagonist"),
                        extra={k: v for k, v in data.items() if k not in {
                            "name",
                            "identity",
                            "personality",
                            "goals",
                            "abilities",
                            "relationship_to_protagonist",
                        }},
                        position=index,
                    )
                )
        if "relationships" in patch and patch["relationships"] is not None:
            await self.session.execute(delete(BlueprintRelationship).where(BlueprintRelationship.project_id == project_id))
            for index, relation in enumerate(patch["relationships"]):
                self.session.add(
                    BlueprintRelationship(
                        project_id=project_id,
                        character_from=relation.get("character_from"),
                        character_to=relation.get("character_to"),
                        description=relation.get("description"),
                        position=index,
                    )
                )
        if "chapter_outline" in patch and patch["chapter_outline"] is not None:
            await self.session.execute(delete(ChapterOutline).where(ChapterOutline.project_id == project_id))
            for outline in patch["chapter_outline"]:
                self.session.add(
                    ChapterOutline(
                        project_id=project_id,
                        chapter_number=outline.get("chapter_number"),
                        title=outline.get("title", ""),
                        summary=outline.get("summary"),
                    )
                )
        await self.session.commit()
        await self._touch_project(project_id)

    # ------------------------------------------------------------------
    # 章节与版本
    # ------------------------------------------------------------------
    async def get_outline(self, project_id: str, chapter_number: int) -> Optional[ChapterOutline]:
        stmt = (
            select(ChapterOutline)
            .where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == chapter_number,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_or_create_chapter(self, project_id: str, chapter_number: int) -> Chapter:
        """获取或创建章节，处理并发竞态条件

        ✅ 修复：添加 IntegrityError 处理，避免并发创建冲突
        """
        from sqlalchemy.exc import IntegrityError

        # 第一次查询
        stmt = (
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
        )
        result = await self.session.execute(stmt)
        chapter = result.scalars().first()
        if chapter:
            return chapter

        # 查找对应的大纲以获取volume_id
        outline_stmt = (
            select(ChapterOutline)
            .where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == chapter_number,
            )
        )
        outline_result = await self.session.execute(outline_stmt)
        outline = outline_result.scalars().first()

        volume_id = outline.volume_id if outline else None

        # 如果没有volume_id,获取或创建默认分卷
        if not volume_id:
            volume_stmt = (
                select(Volume)
                .where(Volume.project_id == project_id, Volume.volume_number == 1)
            )
            volume_result = await self.session.execute(volume_stmt)
            default_volume = volume_result.scalars().first()

            if not default_volume:
                try:
                    default_volume = Volume(
                        project_id=project_id,
                        volume_number=1,
                        title="默认",
                        description="第一卷"
                    )
                    self.session.add(default_volume)
                    await self.session.flush()
                except IntegrityError:
                    # 另一个并发任务已创建，重新查询
                    await self.session.rollback()
                    volume_result = await self.session.execute(volume_stmt)
                    default_volume = volume_result.scalars().first()
                    if not default_volume:
                        raise ValueError("Failed to create or find default volume")

            volume_id = default_volume.id

        # 尝试创建章节
        try:
            chapter = Chapter(
                project_id=project_id,
                chapter_number=chapter_number,
                volume_id=volume_id
            )
            self.session.add(chapter)
            await self.session.commit()
            await self.session.refresh(chapter)
            return chapter
        except IntegrityError:
            # ✅ 并发冲突：另一个任务已创建该章节，重新查询
            await self.session.rollback()
            result = await self.session.execute(stmt)
            chapter = result.scalars().first()
            if chapter:
                return chapter
            # 如果还是没有，说明有其他问题
            raise ValueError(f"Failed to create or find chapter {chapter_number}")

    async def replace_chapter_versions(self, chapter: Chapter, contents: List[str], metadata: Optional[List[Dict]] = None) -> List[ChapterVersion]:
        await self.session.execute(delete(ChapterVersion).where(ChapterVersion.chapter_id == chapter.id))
        versions: List[ChapterVersion] = []
        for index, content in enumerate(contents):
            extra = metadata[index] if metadata and index < len(metadata) else None
            text_content = _normalize_version_content(content, extra)
            version = ChapterVersion(
                chapter_id=chapter.id,
                content=text_content,
                metadata=None,
                version_label=f"v{index+1}",
            )
            self.session.add(version)
            versions.append(version)
        chapter.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
        await self.session.commit()
        await self.session.refresh(chapter)
        await self._touch_project(chapter.project_id)
        return versions

    async def select_chapter_version(self, chapter: Chapter, version_index: int) -> ChapterVersion:
        versions = sorted(chapter.versions, key=lambda item: item.created_at)
        if not versions or version_index < 0 or version_index >= len(versions):
            raise HTTPException(status_code=400, detail="版本索引无效")
        selected = versions[version_index]
        chapter.selected_version_id = selected.id
        chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
        chapter.word_count = len(selected.content or "")
        await self.session.commit()
        await self.session.refresh(chapter)
        await self._touch_project(chapter.project_id)
        return selected

    async def add_chapter_evaluation(self, chapter: Chapter, version: Optional[ChapterVersion], feedback: str, decision: Optional[str] = None) -> None:
        evaluation = ChapterEvaluation(
            chapter_id=chapter.id,
            version_id=version.id if version else None,
            feedback=feedback,
            decision=decision,
        )
        self.session.add(evaluation)
        chapter.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
        await self.session.commit()
        await self.session.refresh(chapter)
        await self._touch_project(chapter.project_id)

    async def delete_chapters(self, project_id: str, chapter_numbers: Iterable[int]) -> None:
        await self.session.execute(
            delete(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number.in_(list(chapter_numbers)),
            )
        )
        await self.session.execute(
            delete(ChapterOutline).where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number.in_(list(chapter_numbers)),
            )
        )
        await self.session.commit()
        await self._touch_project(project_id)

    # ------------------------------------------------------------------
    # 序列化辅助
    # ------------------------------------------------------------------
    async def get_project_schema_for_admin(self, project_id: str) -> NovelProjectSchema:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        return await self._serialize_project(project)

    async def get_section_data_for_admin(
        self,
        project_id: str,
        section: NovelSectionType,
    ) -> NovelSectionResponse:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        return self._build_section_response(project, section)

    async def get_chapter_schema_for_admin(
        self,
        project_id: str,
        chapter_number: int,
    ) -> ChapterSchema:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        return self._build_chapter_schema(project, chapter_number)

    async def _serialize_project(self, project: NovelProject) -> NovelProjectSchema:
        conversations = [
            {"role": convo.role, "content": convo.content}
            for convo in sorted(project.conversations, key=lambda c: c.seq)
        ]

        blueprint_schema = self._build_blueprint_schema(project)

        # ✅ 性能优化：打开项目时不加载章节列表，改为按需加载
        # 避免200+章节项目打开时卡顿
        # 章节数据通过 get_project_section(section='chapters') 按需获取
        chapters_schema: List[ChapterSchema] = []

        return NovelProjectSchema(
            id=project.id,
            user_id=project.user_id,
            title=project.title,
            initial_prompt=project.initial_prompt or "",
            conversation_history=conversations,
            blueprint=blueprint_schema,
            chapters=chapters_schema,  # 空列表，按需加载
        )

    async def _touch_project(self, project_id: str) -> None:
        await self.session.execute(
            update(NovelProject)
            .where(NovelProject.id == project_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        await self.session.commit()

    def _build_blueprint_schema(self, project: NovelProject) -> Blueprint:
        blueprint_obj = project.blueprint
        if blueprint_obj is not None:
            # ✅ 修复：添加防御性检查,确保blueprint_obj的属性访问安全
            try:
                return Blueprint(
                    title=getattr(blueprint_obj, 'title', None) or "",
                    target_audience=getattr(blueprint_obj, 'target_audience', None) or "",
                    genre=getattr(blueprint_obj, 'genre', None) or "",
                    style=getattr(blueprint_obj, 'style', None) or "",
                    tone=getattr(blueprint_obj, 'tone', None) or "",
                    one_sentence_summary=getattr(blueprint_obj, 'one_sentence_summary', None) or "",
                    full_synopsis=getattr(blueprint_obj, 'full_synopsis', None) or "",
                    world_setting=getattr(blueprint_obj, 'world_setting', None) or {},
                    characters=[
                        {
                            "name": character.name,
                            "identity": character.identity,
                            "personality": character.personality,
                            "goals": character.goals,
                            "abilities": character.abilities,
                            "relationship_to_protagonist": character.relationship_to_protagonist,
                            **(character.extra or {}),
                        }
                        for character in sorted(project.characters, key=lambda c: c.position)
                    ],
                    relationships=[
                        {
                            "character_from": relation.character_from,
                            "character_to": relation.character_to,
                            "description": relation.description or "",
                            "relationship_type": getattr(relation, "relationship_type", None),
                        }
                        for relation in sorted(project.relationships_, key=lambda r: r.position)
                    ],
                    volumes=[
                        VolumeSchema(
                            id=volume.id,
                            volume_number=volume.volume_number,
                            title=volume.title,
                            description=volume.description,
                        )
                        for volume in sorted(project.volumes, key=lambda v: v.volume_number)
                    ],
                    chapter_outline=[
                        ChapterOutlineSchema(
                            chapter_number=outline.chapter_number,
                            title=getattr(outline, 'title', None) or f"第{outline.chapter_number}章",
                            summary=getattr(outline, 'summary', None) or "",
                            volume_id=outline.volume_id,
                            volume_number=next((v.volume_number for v in project.volumes if v.id == outline.volume_id), None),
                        )
                        for outline in sorted(project.outlines, key=lambda o: o.chapter_number)
                    ],
                )
            except AttributeError as e:
                # 如果访问属性时出错,记录日志并返回空blueprint
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"构建blueprint schema时出错: {e}, blueprint_obj={blueprint_obj}")
                # 返回空blueprint
                pass

        return Blueprint(
            title="",
            target_audience="",
            genre="",
            style="",
            tone="",
            one_sentence_summary="",
            full_synopsis="",
            world_setting={},
            characters=[],
            relationships=[],
            volumes=[],
            chapter_outline=[],
        )

    def _build_section_response(
        self,
        project: NovelProject,
        section: NovelSectionType,
    ) -> NovelSectionResponse:
        blueprint = self._build_blueprint_schema(project)

        if section == NovelSectionType.OVERVIEW:
            data = {
                "title": project.title,
                "initial_prompt": project.initial_prompt or "",
                "status": project.status,
                "one_sentence_summary": blueprint.one_sentence_summary,
                "target_audience": blueprint.target_audience,
                "genre": blueprint.genre,
                "style": blueprint.style,
                "tone": blueprint.tone,
                "full_synopsis": blueprint.full_synopsis,
                "fanqie_book_id": project.fanqie_book_id,
                "updated_at": project.updated_at.isoformat() if project.updated_at else None,
            }
        elif section == NovelSectionType.WORLD_SETTING:
            data = {
                "world_setting": blueprint.world_setting or {},
            }
        elif section == NovelSectionType.CHARACTERS:
            data = {
                "characters": blueprint.characters,
            }
        elif section == NovelSectionType.RELATIONSHIPS:
            data = {
                "relationships": blueprint.relationships,
            }
        elif section == NovelSectionType.CHAPTER_OUTLINE:
            data = {
                "chapter_outline": [outline.model_dump() for outline in blueprint.chapter_outline],
            }
        elif section == NovelSectionType.CHAPTERS:
            # ✅ 性能优化：使用map避免重复查询
            # 系统不会一次性加载所有数据，而是构建高效的查找字典
            outlines_map = {outline.chapter_number: outline for outline in project.outlines}
            chapters_map = {chapter.chapter_number: chapter for chapter in project.chapters}
            chapter_numbers = sorted(set(outlines_map.keys()) | set(chapters_map.keys()))
            # 章节列表只返回元数据，不包含完整内容
            chapters = [
                self._build_chapter_schema(
                    project,
                    number,
                    outlines_map=outlines_map,
                    chapters_map=chapters_map,
                    include_content=False,
                ).model_dump()
                for number in chapter_numbers
            ]
            # 添加 volumes 数据
            volumes_data = [
                {
                    "id": volume.id,
                    "volume_number": volume.volume_number,
                    "title": volume.title,
                    "description": volume.description,
                }
                for volume in sorted(project.volumes, key=lambda v: v.volume_number)
            ]
            data = {
                "chapters": chapters,
                "volumes": volumes_data,
                "total": len(chapters),
            }
        elif section == NovelSectionType.AUTO_GENERATOR:
            # 自动生成器模块
            data = {
                "project_id": project.id,
                "available": True,
            }
        elif section == NovelSectionType.FANQIE_UPLOAD:
            # 番茄小说上传模块
            # ✅ 性能优化：使用map避免重复查询
            # 返回章节列表供上传使用
            chapters_map = {chapter.chapter_number: chapter for chapter in project.chapters}
            volumes_map = {volume.id: volume for volume in project.volumes}

            chapters_data = []
            for chapter in sorted(project.chapters, key=lambda c: c.chapter_number):
                volume_title = None
                if chapter.volume_id and chapter.volume_id in volumes_map:
                    volume_title = volumes_map[chapter.volume_id].title

                chapters_data.append({
                    "chapter_number": chapter.chapter_number,
                    "volume_id": chapter.volume_id,
                    "volume_title": volume_title,
                    "word_count": chapter.word_count,
                    "status": chapter.status,
                    "has_content": chapter.selected_version_id is not None,
                })

            volumes_data = [
                {
                    "id": volume.id,
                    "volume_number": volume.volume_number,
                    "title": volume.title,
                    "description": volume.description,
                }
                for volume in sorted(project.volumes, key=lambda v: v.volume_number)
            ]

            data = {
                "project_id": project.id,
                "project_title": project.title,
                "chapters": chapters_data,
                "volumes": volumes_data,
                "total_chapters": len(chapters_data),
            }
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未知的章节类型")

        return NovelSectionResponse(section=section, data=data)

    def _build_chapter_schema(
        self,
        project: NovelProject,
        chapter_number: int,
        *,
        outlines_map: Optional[Dict[int, ChapterOutline]] = None,
        chapters_map: Optional[Dict[int, Chapter]] = None,
        include_content: bool = True,
    ) -> ChapterSchema:
        outlines = outlines_map or {outline.chapter_number: outline for outline in project.outlines}
        chapters = chapters_map or {chapter.chapter_number: chapter for chapter in project.chapters}
        outline = outlines.get(chapter_number)
        chapter = chapters.get(chapter_number)

        if not outline and not chapter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")

        title = outline.title if outline else f"第{chapter_number}章"
        summary = outline.summary if outline else ""
        real_summary = chapter.real_summary if chapter else None
        content = None
        versions: Optional[List[str]] = None
        evaluation_text: Optional[str] = None
        status_value = ChapterGenerationStatus.NOT_GENERATED.value
        word_count = 0

        # 获取 volume_id 和 volume_number
        volume_id = None
        volume_number = None
        if outline and outline.volume_id:
            volume_id = outline.volume_id
            # 从 project.volumes 中查找对应的 volume_number
            volume = next((v for v in project.volumes if v.id == volume_id), None)
            if volume:
                volume_number = volume.volume_number
        elif chapter and chapter.volume_id:
            volume_id = chapter.volume_id
            # 从 project.volumes 中查找对应的 volume_number
            volume = next((v for v in project.volumes if v.id == volume_id), None)
            if volume:
                volume_number = volume.volume_number

        if chapter:
            status_value = chapter.status or ChapterGenerationStatus.NOT_GENERATED.value
            word_count = chapter.word_count or 0

            # 只有在 include_content=True 时才包含完整内容
            if include_content:
                if chapter.selected_version:
                    # 提取内容：如果是JSON格式，提取full_content等字段
                    raw_content = chapter.selected_version.content
                    content = _coerce_text(raw_content) if raw_content else None
                if chapter.versions:
                    versions = [
                        _coerce_text(v.content) if v.content else ""
                        for v in sorted(chapter.versions, key=lambda item: item.created_at)
                    ]
                if chapter.evaluations:
                    latest = sorted(chapter.evaluations, key=lambda item: item.created_at)[-1]
                    evaluation_text = latest.feedback or latest.decision

        return ChapterSchema(
            chapter_number=chapter_number,
            title=title,
            summary=summary,
            real_summary=real_summary,
            content=content,
            versions=versions,
            evaluation=evaluation_text,
            generation_status=ChapterGenerationStatus(status_value),
            word_count=word_count,
            volume_id=volume_id,
            volume_number=volume_number,
        )
