-- 为 Volume 表添加分卷版本化字段
-- 每一卷保存该卷的角色、人物关系、世界观快照

-- 添加 characters 字段（角色快照）
ALTER TABLE volumes ADD COLUMN characters TEXT;

-- 添加 relationships 字段（人物关系快照）
ALTER TABLE volumes ADD COLUMN relationships TEXT;

-- 添加 world_setting 字段（世界观快照）
ALTER TABLE volumes ADD COLUMN world_setting TEXT;

-- 注释说明
-- characters: 该卷的角色快照（继承+新增+修改），JSON 格式
-- relationships: 该卷的人物关系快照，JSON 格式
-- world_setting: 该卷的世界观快照，JSON 格式

