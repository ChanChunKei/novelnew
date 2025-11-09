-- AI路由系统数据库表
-- 创建日期: 2025-10-30

-- ==================== AI提供商表 ====================
CREATE TABLE IF NOT EXISTS ai_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,           -- provider名称 (siliconflow, gemini, etc.)
    display_name VARCHAR(200) NOT NULL,          -- 显示名称
    base_url VARCHAR(500) NOT NULL,              -- API base URL
    api_key_env VARCHAR(100),                    -- 环境变量名称
    status VARCHAR(20) DEFAULT 'active',         -- active/inactive/maintenance
    priority INTEGER DEFAULT 100,                -- 优先级（数字越小越优先）
    max_concurrent INTEGER DEFAULT 10,           -- 最大并发数
    rate_limit_per_minute INTEGER DEFAULT 60,   -- 每分钟请求限制
    timeout_seconds INTEGER DEFAULT 300,         -- 默认超时时间
    cost_per_1k_tokens DECIMAL(10, 6),          -- 每1k tokens成本（USD）
    metadata TEXT,                               -- JSON格式的额外配置
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_ai_providers_status ON ai_providers(status);
CREATE INDEX IF NOT EXISTS idx_ai_providers_priority ON ai_providers(priority);

-- ==================== AI功能路由表 ====================
CREATE TABLE IF NOT EXISTS ai_function_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    function_type VARCHAR(100) NOT NULL UNIQUE,  -- 功能类型 (concept_dialogue, etc.)
    display_name VARCHAR(200) NOT NULL,          -- 显示名称
    description TEXT,                            -- 功能描述
    
    -- 主模型配置
    primary_provider_id INTEGER NOT NULL,        -- 主provider ID
    primary_model VARCHAR(200) NOT NULL,         -- 主模型名称
    
    -- 备用模型配置（JSON数组）
    fallback_configs TEXT,                       -- [{"provider_id": 2, "model": "xxx"}, ...]
    
    -- 调用参数
    temperature DECIMAL(3, 2) DEFAULT 0.7,       -- 温度参数
    timeout_seconds INTEGER DEFAULT 300,         -- 超时时间
    max_retries INTEGER DEFAULT 2,               -- 最大重试次数
    
    -- 功能属性
    async_mode BOOLEAN DEFAULT 0,                -- 是否异步执行
    required BOOLEAN DEFAULT 1,                  -- 是否必须成功
    
    -- 配额和限制
    daily_quota INTEGER,                         -- 每日调用配额
    cost_limit_daily DECIMAL(10, 2),            -- 每日成本上限（USD）
    
    -- 元数据
    version INTEGER DEFAULT 1,                   -- 配置版本号
    enabled BOOLEAN DEFAULT 1,                   -- 是否启用
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (primary_provider_id) REFERENCES ai_providers(id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_ai_function_routes_type ON ai_function_routes(function_type);
CREATE INDEX IF NOT EXISTS idx_ai_function_routes_enabled ON ai_function_routes(enabled);
CREATE INDEX IF NOT EXISTS idx_ai_function_routes_version ON ai_function_routes(version);

-- ==================== AI调用日志表 ====================
CREATE TABLE IF NOT EXISTS ai_function_call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 调用信息
    function_type VARCHAR(100) NOT NULL,         -- 功能类型
    provider_id INTEGER,                         -- 使用的provider ID
    model VARCHAR(200),                          -- 使用的模型
    
    -- 用户和项目
    user_id INTEGER,                             -- 用户ID
    project_id VARCHAR(100),                     -- 项目ID
    
    -- 调用参数
    temperature DECIMAL(3, 2),                   -- 温度参数
    timeout_seconds INTEGER,                     -- 超时时间
    
    -- 调用结果
    status VARCHAR(20) NOT NULL,                 -- success/failed/timeout/fallback
    is_fallback BOOLEAN DEFAULT 0,               -- 是否使用了fallback
    fallback_count INTEGER DEFAULT 0,            -- fallback次数
    
    -- 性能指标
    duration_ms INTEGER,                         -- 调用耗时（毫秒）
    input_tokens INTEGER,                        -- 输入token数
    output_tokens INTEGER,                       -- 输出token数
    total_tokens INTEGER,                        -- 总token数
    
    -- 成本
    cost_usd DECIMAL(10, 6),                    -- 本次调用成本（USD）
    
    -- 错误信息
    error_type VARCHAR(100),                     -- 错误类型
    error_message TEXT,                          -- 错误消息
    
    -- 元数据
    finish_reason VARCHAR(50),                   -- 完成原因 (stop/length/error)
    metadata TEXT,                               -- JSON格式的额外信息
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (provider_id) REFERENCES ai_providers(id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_ai_call_logs_function ON ai_function_call_logs(function_type);
CREATE INDEX IF NOT EXISTS idx_ai_call_logs_status ON ai_function_call_logs(status);
CREATE INDEX IF NOT EXISTS idx_ai_call_logs_user ON ai_function_call_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_call_logs_created ON ai_function_call_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_call_logs_provider ON ai_function_call_logs(provider_id);

-- ==================== 配置变更历史表 ====================
CREATE TABLE IF NOT EXISTS ai_config_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name VARCHAR(100) NOT NULL,            -- 表名
    record_id INTEGER NOT NULL,                  -- 记录ID
    action VARCHAR(20) NOT NULL,                 -- create/update/delete
    old_value TEXT,                              -- 旧值（JSON）
    new_value TEXT,                              -- 新值（JSON）
    changed_by INTEGER,                          -- 操作人ID
    change_reason TEXT,                          -- 变更原因
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_ai_config_history_table ON ai_config_history(table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_ai_config_history_created ON ai_config_history(created_at);

-- ==================== 初始化数据 ====================

-- 插入默认providers
INSERT OR IGNORE INTO ai_providers (name, display_name, base_url, api_key_env, priority, cost_per_1k_tokens) VALUES
('siliconflow', '硅基流动', 'https://api.siliconflow.cn/v1', 'SILICONFLOW_API_KEY', 10, 0.0001),
('gemini', 'Google Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', 'GEMINI_API_KEY', 20, 0.00005),
('openai', 'OpenAI', 'https://api.openai.com/v1', 'OPENAI_API_KEY', 30, 0.0015),
('deepseek', 'DeepSeek', 'https://api.deepseek.com/v1', 'DEEPSEEK_API_KEY', 40, 0.0001);

-- 插入默认功能路由（从配置文件迁移）
INSERT OR IGNORE INTO ai_function_routes (
    function_type, display_name, description,
    primary_provider_id, primary_model,
    fallback_configs,
    temperature, timeout_seconds, max_retries,
    async_mode, required
) VALUES
-- F01: 概念对话
('concept_dialogue', '概念对话', 'AI辅助用户构思小说概念',
 (SELECT id FROM ai_providers WHERE name='gemini'), 'gemini-2.0-flash-exp',
 '[{"provider_id": ' || (SELECT id FROM ai_providers WHERE name='siliconflow') || ', "model": "deepseek-ai/DeepSeek-V3"}]',
 0.8, 240, 2, 0, 1),

-- F02: 蓝图生成
('blueprint_generation', '蓝图生成', '生成完整的小说蓝图',
 (SELECT id FROM ai_providers WHERE name='siliconflow'), 'deepseek-ai/DeepSeek-V3',
 '[{"provider_id": ' || (SELECT id FROM ai_providers WHERE name='gemini') || ', "model": "gemini-2.0-flash-exp"}]',
 0.8, 300, 2, 0, 1),

-- F03: 批量大纲生成
('outline_generation', '批量大纲生成', '批量生成章节大纲',
 (SELECT id FROM ai_providers WHERE name='siliconflow'), 'deepseek-ai/DeepSeek-V3',
 '[{"provider_id": ' || (SELECT id FROM ai_providers WHERE name='gemini') || ', "model": "gemini-2.0-flash-exp"}]',
 0.8, 360, 2, 0, 1),

-- F04: 章节正文生成
('chapter_content_writing', '章节正文生成', '生成章节正文内容',
 (SELECT id FROM ai_providers WHERE name='siliconflow'), 'deepseek-ai/DeepSeek-V3',
 '[{"provider_id": ' || (SELECT id FROM ai_providers WHERE name='gemini') || ', "model": "gemini-2.0-flash-exp"}]',
 0.9, 600, 3, 0, 1),

-- F05: 章节摘要提取
('summary_extraction', '章节摘要提取', '提取章节摘要和关键信息',
 (SELECT id FROM ai_providers WHERE name='gemini'), 'gemini-2.0-flash-exp',
 '[{"provider_id": ' || (SELECT id FROM ai_providers WHERE name='siliconflow') || ', "model": "Qwen/Qwen2.5-7B-Instruct"}]',
 0.15, 180, 2, 0, 1),

-- F06: 基础分析
('basic_analysis', '基础分析', '基础章节分析',
 (SELECT id FROM ai_providers WHERE name='gemini'), 'gemini-2.0-flash-exp',
 '[{"provider_id": ' || (SELECT id FROM ai_providers WHERE name='siliconflow') || ', "model": "Qwen/Qwen2.5-7B-Instruct"}]',
 0.3, 180, 2, 0, 1),

-- F07: 增强分析
('enhanced_analysis', '增强分析', '深度章节分析',
 (SELECT id FROM ai_providers WHERE name='siliconflow'), 'deepseek-ai/DeepSeek-V3',
 '[{"provider_id": ' || (SELECT id FROM ai_providers WHERE name='gemini') || ', "model": "gemini-2.0-flash-exp"}]',
 0.5, 600, 1, 1, 0),

-- F08: 角色追踪
('character_tracking', '角色追踪', '追踪角色发展',
 (SELECT id FROM ai_providers WHERE name='gemini'), 'gemini-2.0-flash-exp',
 '[{"provider_id": ' || (SELECT id FROM ai_providers WHERE name='siliconflow') || ', "model": "Qwen/Qwen2.5-7B-Instruct"}]',
 0.3, 300, 1, 1, 0),

-- F09: 世界观扩展
('worldview_expansion', '世界观扩展', '扩展世界观设定',
 (SELECT id FROM ai_providers WHERE name='siliconflow'), 'deepseek-ai/DeepSeek-V3',
 '[{"provider_id": ' || (SELECT id FROM ai_providers WHERE name='gemini') || ', "model": "gemini-2.0-flash-exp"}]',
 0.7, 300, 1, 1, 0),

-- F10: 卷名生成
('volume_naming', '卷名生成', '自动生成卷名',
 (SELECT id FROM ai_providers WHERE name='gemini'), 'gemini-2.0-flash-exp',
 '[{"provider_id": ' || (SELECT id FROM ai_providers WHERE name='siliconflow') || ', "model": "Qwen/Qwen2.5-7B-Instruct"}]',
 0.7, 30, 1, 0, 0);

