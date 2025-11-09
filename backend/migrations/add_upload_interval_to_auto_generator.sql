-- 添加上传间隔配置到自动生成器
-- 2025-11-02

-- 添加 upload_interval_seconds 字段（上传间隔秒数）
ALTER TABLE auto_generator_tasks 
ADD COLUMN upload_interval_seconds INTEGER DEFAULT 20;

-- 添加注释
COMMENT ON COLUMN auto_generator_tasks.upload_interval_seconds IS '上传间隔（秒）';

