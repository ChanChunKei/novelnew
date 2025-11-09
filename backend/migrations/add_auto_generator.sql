-- 自动生成器功能数据库迁移脚本

-- 创建自动生成任务表
CREATE TABLE IF NOT EXISTS auto_generator_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id VARCHAR(36) NOT NULL,
    user_id INTEGER NOT NULL,
    status VARCHAR(32) DEFAULT 'pending' NOT NULL,
    target_chapters INTEGER,
    chapters_per_batch INTEGER DEFAULT 1 NOT NULL,
    interval_seconds INTEGER DEFAULT 60 NOT NULL,
    auto_select_version BOOLEAN DEFAULT 1 NOT NULL,
    generation_config JSON,
    chapters_generated INTEGER DEFAULT 0 NOT NULL,
    total_tokens_used INTEGER DEFAULT 0 NOT NULL,
    error_count INTEGER DEFAULT 0 NOT NULL,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    last_generation_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES novel_projects(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auto_generator_tasks_project_id ON auto_generator_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_auto_generator_tasks_status ON auto_generator_tasks(status);

-- 创建自动生成日志表
CREATE TABLE IF NOT EXISTS auto_generator_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    chapter_number INTEGER,
    log_type VARCHAR(32) NOT NULL,
    message TEXT NOT NULL,
    details JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES auto_generator_tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auto_generator_logs_task_id ON auto_generator_logs(task_id);
