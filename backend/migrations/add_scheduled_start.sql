-- 添加定时启动功能字段
-- 创建时间：2025-11-07

-- 1. 添加定时启动时间字段
ALTER TABLE auto_generator_tasks ADD COLUMN scheduled_start_time TIMESTAMP NULL;

-- 2. 添加启动延迟字段（秒）
ALTER TABLE auto_generator_tasks ADD COLUMN delay_seconds INTEGER DEFAULT 0;

-- 3. 为定时启动时间添加索引（优化查询）
CREATE INDEX IF NOT EXISTS idx_auto_generator_tasks_scheduled_start
ON auto_generator_tasks(scheduled_start_time)
WHERE scheduled_start_time IS NOT NULL;

-- 4. 添加批次ID字段（用于标识批量创建的任务）
ALTER TABLE auto_generator_tasks ADD COLUMN batch_id VARCHAR(36) NULL;

-- 5. 为批次ID添加索引
CREATE INDEX IF NOT EXISTS idx_auto_generator_tasks_batch_id
ON auto_generator_tasks(batch_id)
WHERE batch_id IS NOT NULL;
