# AI功能路由配置说明

## 🎯 功能概述

现在系统支持**不同的AI功能使用不同的API提供商和模型**！

### 核心组件

1. **AI功能配置** (`backend/app/config/ai_function_config.py`)
   - 定义了10个AI功能类型（F01-F10）
   - 每个功能配置了主模型和备用模型
   - 支持自定义温度、超时、重试次数等参数

2. **AI调度器** (`backend/app/services/ai_orchestrator.py`)
   - 根据功能类型自动选择对应的API
   - 支持自动fallback到备用模型
   - 处理重试和错误恢复

3. **LLM服务** (`backend/app/services/llm_service.py`)
   - 新增 `invoke()` 方法支持指定provider和model
   - 统一的API调用接口

## 📋 当前配置

### 优先使用的API

1. **硅基流动 (SiliconFlow)** - 用于高质量内容生成
   - 蓝图生成 (F02)
   - 批量大纲生成 (F03)
   - 章节正文生成 (F04)
   - 增强分析 (F07)
   - 世界观扩展 (F09)

2. **Gemini** - 用于快速响应和低成本任务
   - 概念对话 (F01)
   - 章节摘要提取 (F05)
   - 基础分析 (F06)
   - 角色追踪 (F08)
   - 卷名生成 (F10)

### 功能配置详情

| 功能ID | 功能名称 | 主模型 | 备用模型 | 温度 | 超时 | 必须成功 |
|--------|---------|--------|---------|------|------|---------|
| F01 | 概念对话 | Gemini Flash | DeepSeek-V3 | 0.8 | 240s | ✅ |
| F02 | 蓝图生成 | DeepSeek-V3 | Gemini Flash | 0.8 | 300s | ✅ |
| F03 | 批量大纲 | DeepSeek-V3 | Gemini Flash | 0.8 | 360s | ✅ |
| F04 | 章节正文 | DeepSeek-V3 | Gemini Flash | 0.9 | 600s | ✅ |
| F05 | 章节摘要 | Gemini Flash | Qwen2.5-7B | 0.15 | 180s | ✅ |
| F06 | 基础分析 | Gemini Flash | Qwen2.5-7B | 0.3 | 180s | ✅ |
| F07 | 增强分析 | DeepSeek-V3 | Gemini Flash | 0.5 | 600s | ❌ |
| F08 | 角色追踪 | Gemini Flash | Qwen2.5-7B | 0.3 | 300s | ❌ |
| F09 | 世界观扩展 | DeepSeek-V3 | Gemini Flash | 0.7 | 300s | ❌ |
| F10 | 卷名生成 | Gemini Flash | Qwen2.5-7B | 0.7 | 30s | ❌ |

## 🔧 配置步骤

### 1. 设置环境变量

在 `backend/.env` 文件中添加：

```bash
# 硅基流动 API (必需)
SILICONFLOW_API_KEY=your-siliconflow-api-key-here

# Gemini API (必需)
GEMINI_API_KEY=your-gemini-api-key-here

# DeepSeek API (可选，作为备用)
DEEPSEEK_API_KEY=your-deepseek-api-key-here

# OpenAI API (可选，作为备用)
OPENAI_API_KEY=your-openai-api-key-here
```

### 2. 获取API Key

#### 硅基流动
1. 访问 https://siliconflow.cn/
2. 注册账号
3. 在控制台获取API Key

#### Gemini
1. 访问 https://ai.google.dev/
2. 获取API Key
3. 注意：Gemini API可能需要科学上网

### 3. 测试配置

```bash
cd backend
source venv/bin/activate  # 激活虚拟环境
python3 test_ai_orchestrator.py
```

### 4. 重启应用

```bash
pm2 restart all
```

## 📊 使用示例

### 在代码中使用 AIOrchestrator

```python
from app.services.ai_orchestrator import AIOrchestrator
from app.config.ai_function_config import AIFunctionType

# 创建orchestrator
orchestrator = AIOrchestrator(llm_service)

# 调用AI功能
response = await orchestrator.execute(
    function=AIFunctionType.VOLUME_NAMING,
    system_prompt="你是一位专业的小说编辑...",
    user_prompt="请为这一卷生成标题...",
)
```

### 已集成的功能

✅ **卷名生成** (`volume_split_service.py`)
- 已改用 AIOrchestrator
- 使用 Gemini Flash 快速生成
- 失败自动fallback到默认格式

🔲 **待集成的功能**
- 章节生成 (chapter_service.py)
- 蓝图生成 (blueprint_service.py)
- 概念对话 (concept_service.py)
- 其他分析功能

## 🔍 监控和调试

### 查看日志

```bash
# 查看应用日志
pm2 logs backend

# 查看特定功能的调用
grep "执行AI功能" logs/app.log
grep "调用.*API" logs/app.log
```

### 日志示例

```
INFO: 执行AI功能: volume_naming, 主模型: gemini/gemini-2.0-flash-exp
INFO: 尝试 主模型: gemini/gemini-2.0-flash-exp
INFO: 调用 gemini API: model=gemini-2.0-flash-exp, base_url=https://generativelanguage.googleapis.com/v1beta/openai
INFO: ✅ 主模型 调用成功: gemini/gemini-2.0-flash-exp
INFO: ✅ AI生成卷名: 第一卷·序章
```

## 🎨 自定义配置

### 修改功能配置

编辑 `backend/app/config/ai_function_config.py`：

```python
AIFunctionType.CHAPTER_CONTENT_WRITING: FunctionRouteConfig(
    function_type=AIFunctionType.CHAPTER_CONTENT_WRITING,
    primary=ProviderConfig(
        provider="siliconflow",
        model="deepseek-ai/DeepSeek-V3",  # 修改模型
    ),
    temperature=0.9,  # 修改温度
    timeout=600.0,    # 修改超时
    max_retries=3,    # 修改重试次数
    required=True,    # 是否必须成功
),
```

### 添加新的Provider

1. 在 `PROVIDER_CONFIGS` 中添加配置：

```python
PROVIDER_CONFIGS = {
    "your_provider": {
        "base_url": "https://api.your-provider.com/v1",
        "env_key": "YOUR_PROVIDER_API_KEY",
    },
}
```

2. 在环境变量中设置API Key：

```bash
YOUR_PROVIDER_API_KEY=your-key-here
```

## 🚨 故障排查

### 问题1: API调用失败

**症状**: 日志显示 "未配置 xxx 的 API Key"

**解决**:
1. 检查 `.env` 文件是否设置了对应的环境变量
2. 重启应用使环境变量生效
3. 检查API Key是否有效

### 问题2: 所有模型都失败

**症状**: 日志显示 "所有模型都失败了"

**解决**:
1. 检查网络连接
2. 检查API配额是否用完
3. 查看详细错误日志
4. 如果是可选功能，会返回默认值

### 问题3: 响应格式错误

**症状**: JSON解析失败

**解决**:
1. 检查 `response_format` 参数设置
2. 某些功能（如卷名生成）不需要JSON格式，设置为 `None`
3. 调整提示词使其更明确

## 📈 下一步计划

- [ ] 集成所有功能模块使用 AIOrchestrator
- [ ] 添加成本追踪和统计
- [ ] 实现配置热刷新
- [ ] 开发管理后台UI
- [ ] 添加A/B测试功能
- [ ] 实现智能模型选择

## 💡 最佳实践

1. **成本优化**: 低成本任务使用 Gemini Flash，高质量任务使用 DeepSeek-V3
2. **可靠性**: 核心功能设置 `required=True` 并配置多个备用模型
3. **性能**: 调整 `timeout` 和 `temperature` 参数优化响应速度和质量
4. **监控**: 定期查看日志，了解各API的使用情况和成功率

## 📞 支持

如有问题，请查看：
- 日志文件: `logs/app.log`
- 配置文件: `backend/app/config/ai_function_config.py`
- 测试脚本: `backend/test_ai_orchestrator.py`

