"""
剧情指标数据模型

用于自动分卷功能
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship

from ..db.base import Base


class ChapterStoryMetrics(Base):
    """
    章节剧情指标
    
    记录每章的剧情强度、事件密度等指标，用于自动分卷判定
    """
    __tablename__ = "chapter_story_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联信息
    project_id = Column(String(36), ForeignKey("novel_projects.id"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False, index=True)
    
    # 基础指标
    word_count = Column(Integer, default=0, nullable=False, comment="章节字数")
    
    # 事件指标
    key_event_count = Column(Integer, default=0, nullable=False, comment="关键事件数量")
    major_event_flag = Column(Boolean, default=False, nullable=False, comment="是否有重大事件")
    
    # 伏笔指标
    foreshadow_count = Column(Integer, default=0, nullable=False, comment="伏笔数量")
    foreshadow_max_conf = Column(Float, default=0.0, nullable=False, comment="伏笔最高置信度")
    
    # 角色与世界观
    character_breakthrough_flag = Column(Boolean, default=False, nullable=False, comment="角色是否突破")
    world_shock_flag = Column(Boolean, default=False, nullable=False, comment="世界观是否震撼")
    
    # 评分
    climax_score = Column(Integer, default=0, nullable=False, comment="高潮评分(0-100)")
    stage_score = Column(Integer, default=0, nullable=False, comment="综合阶段评分(0-100)")
    
    # 原始数据快照（用于调试和重算）
    metrics = Column(JSON, nullable=True, comment="原始指标快照")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 关系
    project = relationship("NovelProject")
    chapter = relationship("Chapter")
    
    # 索引：project_id + chapter_number 唯一
    __table_args__ = (
        Index('idx_project_chapter', 'project_id', 'chapter_number', unique=True),
        Index('idx_stage_score', 'project_id', 'stage_score'),
        Index('idx_major_event', 'project_id', 'major_event_flag'),
    )
    
    def __repr__(self):
        return (
            f"<ChapterStoryMetrics(chapter={self.chapter_number}, "
            f"stage_score={self.stage_score}, major_event={self.major_event_flag})>"
        )
    
    @property
    def is_climax(self) -> bool:
        """是否为高潮章节（评分>=70）"""
        return self.climax_score >= 70
    
    @property
    def is_high_score(self) -> bool:
        """是否为高分章节（综合评分>=60）"""
        return self.stage_score >= 60

