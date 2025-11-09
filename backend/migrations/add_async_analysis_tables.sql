-- 异步分析表迁移脚本
-- 日期: 2025-10-30
-- 用途: 支持增强模式异步处理

-- 1. 创建待处理分析表
CREATE TABLE IF NOT EXISTS pending_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 关联信息
    chapter_id INTEGER NOT NULL,
    project_id VARCHAR(255) NOT NULL,
    user_id INTEGER NOT NULL,
    task_id INTEGER,
    
    -- 任务状态
    status VARCHAR(32) NOT NULL DEFAULT 'pending',  -- pending, processing, completed, failed
    priority INTEGER NOT NULL DEFAULT 5,  -- 1-10，数字越大优先级越高
    
    -- 重试信息
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    
    -- 配置信息
    generation_config TEXT,  -- JSON格式
    
    -- 结果信息
    result TEXT,  -- JSON格式
    error_message TEXT,
    error_type VARCHAR(64),
    
    -- 时间信息
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 性能指标
    duration_seconds INTEGER,
    token_usage TEXT,  -- JSON格式
    
    -- 外键约束
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES novel_projects(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES auto_generator_tasks(id) ON DELETE SET NULL
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_pending_analysis_chapter_id ON pending_analysis(chapter_id);
CREATE INDEX IF NOT EXISTS idx_pending_analysis_project_id ON pending_analysis(project_id);
CREATE INDEX IF NOT EXISTS idx_pending_analysis_user_id ON pending_analysis(user_id);
CREATE INDEX IF NOT EXISTS idx_pending_analysis_task_id ON pending_analysis(task_id);
CREATE INDEX IF NOT EXISTS idx_pending_analysis_status ON pending_analysis(status);
CREATE INDEX IF NOT EXISTS idx_pending_analysis_priority ON pending_analysis(priority);
CREATE INDEX IF NOT EXISTS idx_pending_analysis_created_at ON pending_analysis(created_at);

-- 创建复合索引（用于后台处理器查询）
CREATE INDEX IF NOT EXISTS idx_pending_analysis_status_priority 
ON pending_analysis(status, priority DESC, created_at ASC);

-- 2. 创建分析通知表
CREATE TABLE IF NOT EXISTS analysis_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 关联信息
    pending_analysis_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    chapter_id INTEGER NOT NULL,
    
    -- 通知类型
    notification_type VARCHAR(32) NOT NULL,  -- started, progress, completed, failed
    
    -- 通知内容
    title VARCHAR(255) NOT NULL,
    message TEXT,
    data TEXT,  -- JSON格式
    
    -- 状态
    is_read INTEGER NOT NULL DEFAULT 0,  -- 0未读，1已读
    
    -- 时间
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP,
    
    -- 外键约束
    FOREIGN KEY (pending_analysis_id) REFERENCES pending_analysis(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_analysis_notifications_pending_analysis_id 
ON analysis_notifications(pending_analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_notifications_user_id 
ON analysis_notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_notifications_chapter_id 
ON analysis_notifications(chapter_id);
CREATE INDEX IF NOT EXISTS idx_analysis_notifications_is_read 
ON analysis_notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_analysis_notifications_created_at 
ON analysis_notifications(created_at);

-- 创建复合索引（用于前端查询未读通知）
CREATE INDEX IF NOT EXISTS idx_analysis_notifications_user_unread 
ON analysis_notifications(user_id, is_read, created_at DESC);

-- 3. 创建触发器：自动更新updated_at
CREATE TRIGGER IF NOT EXISTS update_pending_analysis_updated_at
AFTER UPDATE ON pending_analysis
FOR EACH ROW
BEGIN
    UPDATE pending_analysis SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 4. 插入测试数据（可选，用于验证）
-- INSERT INTO pending_analysis (chapter_id, project_id, user_id, status, priority)
-- VALUES (1, 'test_project', 1, 'pending', 5);

