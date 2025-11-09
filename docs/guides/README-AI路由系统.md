# AI路由系统 - 快速开始

## 🎯 这是什么？

一个**生产就绪**的AI路由系统，让不同的AI功能使用不同的API提供商和模型。

**核心特性**：
- ✅ 10个AI功能独立配置（概念对话、蓝图生成、章节写作等）
- ✅ 优先使用硅基流动和Gemini（成本优化）
- ✅ 自动fallback和重试（高可用性）
- ✅ 完整的监控和日志（Prometheus + 数据库）
- ✅ 管理API接口（配置管理）

## 🚀 快速开始（3步）

### 1. 设置API Keys

编辑 `backend/.env`：

```bash
# 必需
SILICONFLOW_API_KEY=sk-xxxxx
GEMINI_API_KEY=AIzaSyxxxxx
```

### 2. 重启应用

```bash
pm2 restart backend
```

### 3. 验证系统

```bash
cd backend
./verify_ai_routing.sh
```

**预期输出**：
```
✅ 数据库层: 已就绪 (4 providers, 10 routes)
✅ 代码层: 已完成
✅ 监控层: 已集成
```

## 📊 功能配置

| 功能 | 主模型 | 用途 |
|------|--------|------|
| 概念对话 | Gemini Flash | 快速响应 |
| 蓝图生成 | DeepSeek-V3 | 高质量 |
| 章节正文 | DeepSeek-V3 | 高质量 |
| 章节摘要 | Gemini Flash | 快速+便宜 |
| 卷名生成 | Gemini Flash | 快速 |

完整配置见：[AI路由系统实施完成报告-最终版.md](./AI路由系统实施完成报告-最终版.md)

## 💻 使用示例

### 方式1: 使用辅助函数（推荐）

```python
from app.services.ai_orchestrator_helper import generate_chapter_content

response = await generate_chapter_content(
    db_session=db,
    system_prompt="你是专业的小说作家...",
    user_prompt="请生成第1章...",
    user_id=user_id,
)
```

### 方式2: 向后兼容包装器

```python
from app.services.ai_orchestrator_helper import OrchestratorWrapper

# 替换原来的 LLMService
llm_service = OrchestratorWrapper(db)

# 其他代码不变
response = await llm_service.get_llm_response(...)
```

## 📈 监控和管理

### 查看实时指标

```bash
curl http://localhost:8000/metrics | grep ai_
```

**关键指标**：
- `ai_calls_total` - 调用总次数
- `ai_duration_seconds` - 调用耗时
- `ai_fallback_total` - Fallback次数
- `ai_error_total` - 错误统计

### 查看调用日志

```bash
curl http://localhost:8000/api/ai-routing/logs?limit=10
```

### 管理路由配置

```bash
# 查看所有路由
curl http://localhost:8000/api/ai-routing/routes

# 更新配置
curl -X PATCH http://localhost:8000/api/ai-routing/routes/chapter_content_writing \
  -H "Content-Type: application/json" \
  -d '{"temperature": 0.95, "max_retries": 5}'
```

## 🏗️ 架构概览

```
用户请求
    ↓
AIOrchestrator (路由调度)
    ↓
根据功能类型选择API
    ↓
┌─────────────┬─────────────┬─────────────┐
│ SiliconFlow │   Gemini    │   OpenAI    │
│ (DeepSeek)  │   (Flash)   │   (GPT-4)   │
└─────────────┴─────────────┴─────────────┘
    ↓
自动fallback + 重试
    ↓
记录日志 + 指标
    ↓
返回结果
```

## 📁 核心文件

```
backend/
├── migrations/
│   └── add_ai_routing_tables.sql          # 数据库迁移
├── app/
│   ├── config/
│   │   └── ai_function_config.py          # 功能配置
│   ├── services/
│   │   ├── ai_orchestrator.py             # 路由调度器
│   │   └── ai_orchestrator_helper.py      # 辅助函数
│   └── api/routers/
│       └── ai_routing.py                  # 管理API
└── verify_ai_routing.sh                   # 验证脚本
```

## 🔧 故障排查

### 问题1: API调用失败

**症状**: 日志显示 "未配置 xxx 的 API Key"

**解决**:
```bash
# 检查环境变量
grep "SILICONFLOW_API_KEY" backend/.env
grep "GEMINI_API_KEY" backend/.env

# 重启应用
pm2 restart backend
```

### 问题2: 数据库表不存在

**症状**: 错误 "no such table: ai_providers"

**解决**:
```bash
cd backend
sqlite3 storage/arboris.db < migrations/add_ai_routing_tables.sql
```

### 问题3: 所有模型都失败

**症状**: 日志显示 "所有模型都失败了"

**解决**:
1. 检查网络连接
2. 检查API配额
3. 查看详细错误日志：`pm2 logs backend`

## 📚 完整文档

- [AI路由系统实施完成报告-最终版.md](./AI路由系统实施完成报告-最终版.md) - 完整的实施报告
- [AI功能路由配置说明.md](./AI功能路由配置说明.md) - 详细的配置说明
- [Bug修复报告-20251030.md](./Bug修复报告-20251030.md) - Bug修复记录

## 🎯 下一步

1. ✅ 设置API Keys
2. ✅ 重启应用
3. ✅ 验证系统
4. 🔲 测试实际AI调用
5. 🔲 查看监控指标
6. 🔲 根据需要调整配置

## 💡 最佳实践

1. **成本优化**: 低成本任务用Gemini Flash，高质量任务用DeepSeek-V3
2. **可靠性**: 核心功能设置多个备用模型
3. **性能**: 调整timeout和temperature优化响应
4. **监控**: 定期查看日志和指标

## 🆘 获取帮助

- 查看日志: `pm2 logs backend`
- 运行验证: `cd backend && ./verify_ai_routing.sh`
- 查看指标: `curl http://localhost:8000/metrics`
- 查看API文档: `http://localhost:8000/docs`

---

**状态**: ✅ 生产就绪  
**版本**: 2.0  
**最后更新**: 2025-10-30

