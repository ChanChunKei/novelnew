-- 添加自动上传功能到自动生成器
-- 2025-01-02

-- 添加 auto_upload 字段（是否自动上传到番茄小说）
ALTER TABLE auto_generator_tasks 
ADD COLUMN auto_upload BOOLEAN DEFAULT FALSE;

-- 添加 fanqie_account 字段（番茄小说账号名称）
ALTER TABLE auto_generator_tasks 
ADD COLUMN fanqie_account VARCHAR(64);

-- 添加注释
COMMENT ON COLUMN auto_generator_tasks.auto_upload IS '是否自动上传到番茄小说';
COMMENT ON COLUMN auto_generator_tasks.fanqie_account IS '番茄小说账号名称';

