"""
剧情指标分析服务

用于自动分卷功能：
1. 从增强分析结果中提取剧情指标
2. 计算章节的剧情阶段评分
3. 记录到 chapter_story_metrics 表
"""
import logging
from typing import Dict, Optional, List
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)


class StoryMetricsService:
    """剧情指标分析服务"""
    
    # 默认权重配置（可从generation_config覆盖）
    DEFAULT_WEIGHTS = {
        "key_event": 8,              # 每个关键事件 +8分
        "foreshadow": 5,             # 每个伏笔 +5分
        "foreshadow_conf": 10,       # 伏笔置信度 * 10
        "character_breakthrough": 20, # 角色突破 +20分
        "world_shock": 15,           # 世界观震撼 +15分
        "major_event": 25,           # 重大事件 +25分
        "climax_multiplier": 1.2,    # 高潮章节 * 1.2
    }
    
    @classmethod
    async def record_metrics(
        cls,
        db: AsyncSession,
        project_id: str,
        chapter_id: int,
        chapter_number: int,
        enhanced_result: dict,
        summary_result: dict,
        word_count: int = 0,
        config: Optional[dict] = None
    ) -> dict:
        """
        记录章节剧情指标
        
        参数:
            db: 数据库会话
            project_id: 项目ID
            chapter_id: 章节ID
            chapter_number: 章节号
            enhanced_result: 增强分析结果
            summary_result: 基础摘要结果
            word_count: 字数
            config: 配置（可选，用于覆盖默认权重）
        
        返回:
            计算后的指标字典
        """
        try:
            # 1. 提取原始指标
            metrics = cls._extract_metrics(
                enhanced_result=enhanced_result,
                summary_result=summary_result,
                word_count=word_count
            )
            
            # 2. 计算综合评分
            weights = config.get("metrics_weights", cls.DEFAULT_WEIGHTS) if config else cls.DEFAULT_WEIGHTS
            metrics["stage_score"] = cls._compute_stage_score(metrics, weights)
            
            # 3. 写入数据库（upsert）
            await cls._upsert_metrics(
                db=db,
                project_id=project_id,
                chapter_id=chapter_id,
                chapter_number=chapter_number,
                metrics=metrics,
                raw_data={
                    "enhanced": enhanced_result,
                    "summary": summary_result
                }
            )
            
            logger.info(
                f"章节 {chapter_number} 剧情指标已记录: "
                f"stage_score={metrics['stage_score']}, "
                f"major_event={metrics['major_event_flag']}"
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"记录剧情指标失败: {e}", exc_info=True)
            # 不阻塞主流程，返回空指标
            return {}
    
    @classmethod
    def _extract_metrics(
        cls,
        enhanced_result: dict,
        summary_result: dict,
        word_count: int
    ) -> dict:
        """
        从分析结果中提取剧情指标
        
        返回:
            {
                "key_event_count": int,
                "major_event_flag": bool,
                "character_breakthrough_flag": bool,
                "world_shock_flag": bool,
                "foreshadow_count": int,
                "foreshadow_max_conf": float,
                "climax_score": int,
                "word_count": int
            }
        """
        # ✅ 修复5：添加字段校验和默认值
        # 基础摘要中的关键事件
        key_events = summary_result.get("key_events", []) if isinstance(summary_result, dict) else []
        if not isinstance(key_events, list):
            key_events = []

        # 增强分析中的数据
        foreshadowings = enhanced_result.get("foreshadowings", []) if isinstance(enhanced_result, dict) else []
        char_changes = enhanced_result.get("character_changes", []) if isinstance(enhanced_result, dict) else []
        world_ext = enhanced_result.get("world_extensions", {}) if isinstance(enhanced_result, dict) else {}

        # 确保类型正确
        if not isinstance(foreshadowings, list):
            foreshadowings = []
        if not isinstance(char_changes, list):
            char_changes = []
        if not isinstance(world_ext, dict):
            world_ext = {}

        # 计算各项指标
        metrics = {
            "word_count": word_count,
            "key_event_count": len(key_events),
            "foreshadow_count": len(foreshadowings),
        }

        # 伏笔最高置信度（安全提取）
        if foreshadowings:
            confidences = []
            for f in foreshadowings:
                if isinstance(f, dict):
                    conf = f.get("confidence", 0)
                    # 确保是数字
                    try:
                        confidences.append(float(conf) if conf is not None else 0.0)
                    except (ValueError, TypeError):
                        confidences.append(0.0)
            metrics["foreshadow_max_conf"] = max(confidences) if confidences else 0.0
        else:
            metrics["foreshadow_max_conf"] = 0.0

        # 角色突破标志（成长等级>=5 或描述中包含"突破"）
        breakthrough_flags = []
        for change in char_changes:
            if isinstance(change, dict):
                growth_level = change.get("growth_level", 0)
                changes_text = str(change.get("changes", ""))
                try:
                    growth_level = int(growth_level) if growth_level is not None else 0
                except (ValueError, TypeError):
                    growth_level = 0

                breakthrough_flags.append(
                    growth_level >= 5 or
                    "突破" in changes_text or
                    "境界" in changes_text
                )
        metrics["character_breakthrough_flag"] = any(breakthrough_flags) if breakthrough_flags else False

        # 世界观震撼标志（有新增世界观元素）
        world_shock_flags = []
        for key, values in world_ext.items():
            if isinstance(values, list):
                world_shock_flags.append(len(values) > 0)
        metrics["world_shock_flag"] = any(world_shock_flags) if world_shock_flags else False

        # 重大事件标志（角色突破 或 高潮/灾难类伏笔）
        climax_types = {"climax", "catastrophe", "turning_point"}
        climax_foreshadow_flags = []
        for f in foreshadowings:
            if isinstance(f, dict):
                f_type = f.get("type", "")
                climax_foreshadow_flags.append(f_type in climax_types)
        has_climax_foreshadow = any(climax_foreshadow_flags) if climax_foreshadow_flags else False

        metrics["major_event_flag"] = (
            metrics["character_breakthrough_flag"] or
            has_climax_foreshadow or
            metrics["key_event_count"] >= 4  # 关键事件过多也算重大
        )
        
        # 高潮评分（0-100，基于事件密度和类型）
        metrics["climax_score"] = cls._compute_climax_score(
            key_events=key_events,
            foreshadowings=foreshadowings,
            char_changes=char_changes
        )
        
        return metrics
    
    @classmethod
    def _compute_climax_score(
        cls,
        key_events: list,
        foreshadowings: list,
        char_changes: list
    ) -> int:
        """
        计算高潮评分（0-100）

        基于：
        - 事件密度
        - 伏笔类型
        - 角色变化强度
        """
        score = 0

        # 事件密度（最多40分）
        score += min(len(key_events) * 10, 40)

        # 伏笔类型加权（最多30分）
        # ✅ 修复：跳过非字典条目，避免运行时错误
        for f in foreshadowings:
            if not isinstance(f, dict):
                continue
            f_type = f.get("type", "")
            if f_type == "climax":
                score += 15
            elif f_type == "catastrophe":
                score += 12
            elif f_type == "turning_point":
                score += 10
            else:
                score += 3

        # 角色变化强度（最多30分）
        # ✅ 修复：跳过非字典条目，避免运行时错误
        for change in char_changes:
            if not isinstance(change, dict):
                continue
            growth = change.get("growth_level", 0)
            score += min(growth * 3, 15)

        return min(score, 100)
    
    @classmethod
    def _compute_stage_score(cls, metrics: dict, weights: dict) -> int:
        """
        计算综合阶段评分（0-100）
        
        参数:
            metrics: 提取的指标
            weights: 权重配置
        
        返回:
            综合评分（0-100）
        """
        score = 0.0
        
        # 关键事件
        score += metrics["key_event_count"] * weights["key_event"]
        
        # 伏笔
        score += metrics["foreshadow_count"] * weights["foreshadow"]
        score += metrics["foreshadow_max_conf"] * weights["foreshadow_conf"]
        
        # 角色突破
        if metrics["character_breakthrough_flag"]:
            score += weights["character_breakthrough"]
        
        # 世界观震撼
        if metrics["world_shock_flag"]:
            score += weights["world_shock"]
        
        # 重大事件
        if metrics["major_event_flag"]:
            score += weights["major_event"]
        
        # 高潮章节加成
        if metrics["climax_score"] >= 70:
            score *= weights["climax_multiplier"]
        
        return min(int(score), 100)
    
    @classmethod
    async def _upsert_metrics(
        cls,
        db: AsyncSession,
        project_id: str,
        chapter_id: int,
        chapter_number: int,
        metrics: dict,
        raw_data: dict
    ):
        """
        写入或更新指标（PostgreSQL upsert）
        
        如果是SQLite，则先删除再插入
        """
        from ..models.story_metrics import ChapterStoryMetrics
        
        # 构建插入语句
        stmt = insert(ChapterStoryMetrics).values(
            project_id=project_id,
            chapter_id=chapter_id,
            chapter_number=chapter_number,
            word_count=metrics.get("word_count", 0),
            key_event_count=metrics.get("key_event_count", 0),
            major_event_flag=metrics.get("major_event_flag", False),
            foreshadow_count=metrics.get("foreshadow_count", 0),
            foreshadow_max_conf=metrics.get("foreshadow_max_conf", 0.0),
            character_breakthrough_flag=metrics.get("character_breakthrough_flag", False),
            world_shock_flag=metrics.get("world_shock_flag", False),
            climax_score=metrics.get("climax_score", 0),
            stage_score=metrics.get("stage_score", 0),
            metrics=raw_data
        )
        
        # PostgreSQL: on_conflict_do_update
        # SQLite: 先删除再插入
        try:
            # 尝试PostgreSQL语法
            stmt = stmt.on_conflict_do_update(
                index_elements=['project_id', 'chapter_number'],
                set_={
                    'word_count': metrics.get("word_count", 0),
                    'key_event_count': metrics.get("key_event_count", 0),
                    'major_event_flag': metrics.get("major_event_flag", False),
                    'foreshadow_count': metrics.get("foreshadow_count", 0),
                    'foreshadow_max_conf': metrics.get("foreshadow_max_conf", 0.0),
                    'character_breakthrough_flag': metrics.get("character_breakthrough_flag", False),
                    'world_shock_flag': metrics.get("world_shock_flag", False),
                    'climax_score': metrics.get("climax_score", 0),
                    'stage_score': metrics.get("stage_score", 0),
                    'metrics': raw_data
                }
            )
            await db.execute(stmt)
        except Exception:
            # SQLite fallback: 删除后插入
            from sqlalchemy import delete
            await db.execute(
                delete(ChapterStoryMetrics).where(
                    ChapterStoryMetrics.project_id == project_id,
                    ChapterStoryMetrics.chapter_number == chapter_number
                )
            )
            await db.execute(stmt)
        
        await db.commit()

