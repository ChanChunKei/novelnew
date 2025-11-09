-- 添加分卷功能的数据库迁移
-- 执行日期: 2025-10-29

-- 1. 创建分卷表
CREATE TABLE IF NOT EXISTS volumes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id CHAR(36) NOT NULL,
    volume_number INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_volumes_project FOREIGN KEY (project_id) REFERENCES novel_projects(id) ON DELETE CASCADE,
    UNIQUE KEY uq_volume_project_number (project_id, volume_number)
);

-- 2. 为 chapter_outlines 表添加 volume_id 字段
ALTER TABLE chapter_outlines 
ADD COLUMN volume_id BIGINT NULL AFTER project_id,
ADD CONSTRAINT fk_outlines_volume FOREIGN KEY (volume_id) REFERENCES volumes(id) ON DELETE SET NULL;

-- 3. 为 chapters 表添加 volume_id 字段
ALTER TABLE chapters 
ADD COLUMN volume_id BIGINT NULL AFTER project_id,
ADD CONSTRAINT fk_chapters_volume FOREIGN KEY (volume_id) REFERENCES volumes(id) ON DELETE SET NULL;

-- 4. 为每个项目创建默认分卷
INSERT INTO volumes (project_id, volume_number, title, description)
SELECT 
    id as project_id,
    1 as volume_number,
    '默认' as title,
    '第一卷' as description
FROM novel_projects
WHERE NOT EXISTS (
    SELECT 1 FROM volumes WHERE volumes.project_id = novel_projects.id
);

-- 5. 将现有章节和大纲关联到默认分卷
UPDATE chapter_outlines co
JOIN volumes v ON co.project_id = v.project_id AND v.volume_number = 1
SET co.volume_id = v.id
WHERE co.volume_id IS NULL;

UPDATE chapters c
JOIN volumes v ON c.project_id = v.project_id AND v.volume_number = 1
SET c.volume_id = v.id
WHERE c.volume_id IS NULL;

