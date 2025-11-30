"""
收尾辅助服务

基于现有 3Agent 流程，为项目生成收尾清单和终章大纲。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.novel import Chapter
from ..services.llm_service import LLMService
from ..services.novel_service import NovelService

logger = logging.getLogger(__name__)


class EndingService:
    """收尾规划服务"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_service = LLMService(session)

    async def generate_ending_checklist(
        self,
        project_id: str,
        user_id: int,
        max_recent: int = 10,
    ) -> Dict[str, Any]:
        """
        生成收尾清单（粗略版）

        - 读取蓝图
        - 抽取最近章节摘要
        - 基于关键词简单发现未回收伏笔
        """
        novel_service = NovelService(self.session)
        project_schema = await novel_service.get_project_schema(project_id, user_id)
        blueprint_dict = project_schema.blueprint.model_dump()

        # 最近章节摘要
        stmt = (
            select(Chapter)
            .where(Chapter.project_id == project_id, Chapter.status == "successful")
            .order_by(Chapter.chapter_number.desc())
            .limit(max_recent)
            .options(selectinload(Chapter.selected_version))
        )
        result = await self.session.execute(stmt)
        chapters = result.scalars().all()

        recent_summaries: List[Dict[str, Any]] = []
        for ch in chapters:
            recent_summaries.append(
                {
                    "chapter_number": ch.chapter_number,
                    "summary": ch.real_summary or "",
                }
            )

        # 简单伏笔探测（关键词启发式）
        foreshadow_keywords = ["伏笔", "预言", "暗示", "秘密", "线索", "悬念"]
        unresolved: List[Dict[str, Any]] = []
        for ch in chapters:
            text = (ch.real_summary or "") + " " + (ch.selected_version.content if ch.selected_version else "")
            for kw in foreshadow_keywords:
                if kw in text:
                    unresolved.append(
                        {
                            "chapter_number": ch.chapter_number,
                            "keyword": kw,
                            "excerpt": text[:200],
                        }
                    )
                    break  # 该章命中一次即可

        last_chapter = chapters[0].chapter_number if chapters else 0
        planned_total = max(len(project_schema.chapters), last_chapter or 1)
        main_plot_progress = min(100, round(100 * last_chapter / planned_total)) if planned_total else 0

        return {
            "blueprint": blueprint_dict,
            "recent_summaries": recent_summaries,
            "unresolved_foreshadowing": unresolved,
            "main_plot_progress": main_plot_progress,
        }

    async def plan_ending_outline(
        self,
        project_id: str,
        user_id: int,
        checklist: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        规划终章大纲（1-2 章）

        使用 ending_planner 提示词生成 JSON 大纲。
        """
        prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / "ending_planner.md"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()
        except FileNotFoundError:
            raise ValueError("缺少 ending_planner.md 提示词，请先配置 prompts/ending_planner.md")

        prompt = prompt_template.format(
            blueprint_json=json.dumps(checklist.get("blueprint", {}), ensure_ascii=False),
            recent_summaries=json.dumps(checklist.get("recent_summaries", []), ensure_ascii=False),
            unresolved_foreshadowing=json.dumps(checklist.get("unresolved_foreshadowing", []), ensure_ascii=False),
            main_plot_progress=checklist.get("main_plot_progress", 0),
        )

        response = await self.llm_service.get_llm_response(
            system_prompt="你是资深网文主编，专注为长篇小说设计收尾章节。",
            conversation_history=[{"role": "user", "content": prompt}],
            temperature=0.6,
            user_id=user_id,
            timeout=180.0,
        )

        outline = self._parse_json_response(response)
        return outline

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """从 LLM 返回文本中提取 JSON"""
        text_stripped = text.strip()
        # 优先直接解析
        if text_stripped.startswith("{"):
            try:
                return json.loads(text_stripped)
            except json.JSONDecodeError:
                pass

        # 回退：尝试找到第一个花括号片段
        import re

        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError as e:
                logger.error(f"解析收尾大纲 JSON 失败: {e}")
        raise ValueError("未能从模型输出中解析有效的 JSON 收尾大纲")
