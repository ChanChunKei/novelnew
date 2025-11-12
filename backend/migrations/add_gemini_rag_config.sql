-- Gemini RAG 配置迁移脚本
-- 添加 Gemini API Key 和 RAG Provider 配置项到 system_configs 表
--
-- 配置说明：
-- - gemini.api_key: Google Gemini API Key，用于 Semantic Retrieval
-- - rag.provider: RAG 检索提供方，可选值 'gemini' 或 'libsql'
--
-- 注意：默认值为空，需要管理员在前端配置

-- 添加 gemini.api_key 配置（如果不存在）
INSERT OR IGNORE INTO system_configs (key, value, description)
VALUES (
    'gemini.api_key',
    '',
    'Google Gemini API Key，格式 AIzaSy...，用于 Semantic Retrieval RAG 搜索'
);

-- 添加 rag.provider 配置（如果不存在）
-- 默认值为 'libsql'（保持向后兼容）
INSERT OR IGNORE INTO system_configs (key, value, description)
VALUES (
    'rag.provider',
    'libsql',
    'RAG 检索提供方：gemini (Google 托管) 或 libsql (本地向量库)，默认 libsql'
);

-- 验证插入结果
SELECT key, value, description
FROM system_configs
WHERE key IN ('gemini.api_key', 'rag.provider');
