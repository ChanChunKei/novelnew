-- 添加剧情指标表（用于自动分卷功能）
-- 日期: 2025-10-30

-- 创建 chapter_story_metrics 表
CREATE TABLE IF NOT EXISTS chapter_story_metrics (
    id SERIAL PRIMARY KEY,
    
    -- 关联信息
    project_id VARCHAR(36) NOT NULL,
    chapter_id BIGINT NOT NULL,
    chapter_number INT NOT NULL,
    
    -- 基础指标
    word_count INT DEFAULT 0 NOT NULL,
    
    -- 事件指标
    key_event_count INT DEFAULT 0 NOT NULL,
    major_event_flag BOOLEAN DEFAULT FALSE NOT NULL,
    
    -- 伏笔指标
    foreshadow_count INT DEFAULT 0 NOT NULL,
    foreshadow_max_conf DOUBLE PRECISION DEFAULT 0.0 NOT NULL,
    
    -- 角色与世界观
    character_breakthrough_flag BOOLEAN DEFAULT FALSE NOT NULL,
    world_shock_flag BOOLEAN DEFAULT FALSE NOT NULL,
    
    -- 评分
    climax_score INT DEFAULT 0 NOT NULL,
    stage_score INT DEFAULT 0 NOT NULL,
    
    -- 原始数据快照
    metrics JSONB,
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- 外键约束
    CONSTRAINT fk_story_metrics_project FOREIGN KEY (project_id) 
        REFERENCES novel_projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_story_metrics_chapter FOREIGN KEY (chapter_id) 
        REFERENCES chapters(id) ON DELETE CASCADE
);

-- 创建索引
CREATE UNIQUE INDEX idx_project_chapter_unique 
    ON chapter_story_metrics(project_id, chapter_number);

CREATE INDEX idx_story_metrics_project 
    ON chapter_story_metrics(project_id);

CREATE INDEX idx_story_metrics_chapter 
    ON chapter_story_metrics(chapter_id);

CREATE INDEX idx_story_metrics_stage_score 
    ON chapter_story_metrics(project_id, stage_score);

CREATE INDEX idx_story_metrics_major_event 
    ON chapter_story_metrics(project_id, major_event_flag);

-- 添加注释
COMMENT ON TABLE chapter_story_metrics IS '章节剧情指标，用于自动分卷判定';
COMMENT ON COLUMN chapter_story_metrics.word_count IS '章节字数';
COMMENT ON COLUMN chapter_story_metrics.key_event_count IS '关键事件数量';
COMMENT ON COLUMN chapter_story_metrics.major_event_flag IS '是否有重大事件';
COMMENT ON COLUMN chapter_story_metrics.foreshadow_count IS '伏笔数量';
COMMENT ON COLUMN chapter_story_metrics.foreshadow_max_conf IS '伏笔最高置信度';
COMMENT ON COLUMN chapter_story_metrics.character_breakthrough_flag IS '角色是否突破';
COMMENT ON COLUMN chapter_story_metrics.world_shock_flag IS '世界观是否震撼';
COMMENT ON COLUMN chapter_story_metrics.climax_score IS '高潮评分(0-100)';
COMMENT ON COLUMN chapter_story_metrics.stage_score IS '综合阶段评分(0-100)';
COMMENT ON COLUMN chapter_story_metrics.metrics IS '原始指标快照（JSON）';

-- SQLite 兼容版本（如果使用SQLite，请使用此版本）
/*
CREATE TABLE IF NOT EXISTS chapter_story_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id VARCHAR(36) NOT NULL,
    chapter_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    word_count INTEGER DEFAULT 0 NOT NULL,
    key_event_count INTEGER DEFAULT 0 NOT NULL,
    major_event_flag INTEGER DEFAULT 0 NOT NULL,
    foreshadow_count INTEGER DEFAULT 0 NOT NULL,
    foreshadow_max_conf REAL DEFAULT 0.0 NOT NULL,
    character_breakthrough_flag INTEGER DEFAULT 0 NOT NULL,
    world_shock_flag INTEGER DEFAULT 0 NOT NULL,
    climax_score INTEGER DEFAULT 0 NOT NULL,
    stage_score INTEGER DEFAULT 0 NOT NULL,
    metrics TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (project_id) REFERENCES novel_projects(id) ON DELETE CASCADE,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX idx_project_chapter_unique 
    ON chapter_story_metrics(project_id, chapter_number);

CREATE INDEX idx_story_metrics_project 
    ON chapter_story_metrics(project_id);

CREATE INDEX idx_story_metrics_chapter 
    ON chapter_story_metrics(chapter_id);

CREATE INDEX idx_story_metrics_stage_score 
    ON chapter_story_metrics(project_id, stage_score);

CREATE INDEX idx_story_metrics_major_event 
    ON chapter_story_metrics(project_id, major_event_flag);
*/

