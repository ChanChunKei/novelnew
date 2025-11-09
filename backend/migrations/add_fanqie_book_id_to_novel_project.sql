-- 为 novel_projects 表添加 fanqie_book_id 字段
-- 用于存储番茄小说平台的书籍ID，避免每次都需要通过书名查找

ALTER TABLE novel_projects
ADD COLUMN fanqie_book_id VARCHAR(64) DEFAULT NULL COMMENT '番茄小说书籍ID';

-- 添加索引以提高查询性能
CREATE INDEX idx_fanqie_book_id ON novel_projects(fanqie_book_id);
