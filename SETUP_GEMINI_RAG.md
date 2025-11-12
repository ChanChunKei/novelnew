# Gemini RAG 快速上手指南

## 🎉 已完成的配置

你的 Gemini API Key 已经成功配置到数据库中！

- **API Key**: `AIzaSyA5t2...2kBQ` ✅
- **RAG Provider**: `gemini` ✅
- **数据库**: `backend/storage/arboris.db` ✅

## 📖 系统说明

### 什么是 Gemini RAG？

Gemini RAG（Retrieval-Augmented Generation）使用 Google Gemini 的 Semantic Retrieval API 实现向量搜索：

**优势：**
- ✅ 零配置：无需自建向量数据库
- ✅ 免费额度：1500次/天
- ✅ Google 托管：自动扩展、高可用
- ✅ 自动向量化：无需手动调用 embedding API

**工作原理：**
1. 每生成一章，自动创建 Document 并入库到 Gemini Corpus
2. 生成新章节时，3Agent 模式使用 `search_chapters` 工具搜索相关内容
3. Gemini API 返回语义相关的章节片段，供 AI 参考

### 配置方式

系统支持两种配置方式（优先级：数据库 > 环境变量）:

#### 方式1：数据库配置（推荐）
```sql
-- 已自动配置完成
INSERT INTO system_configs (key, value, description) VALUES
  ('gemini.api_key', 'AIzaSy...', 'Google Gemini API Key'),
  ('rag.provider', 'gemini', 'RAG 检索提供方');
```

#### 方式2：环境变量（备用）
```bash
# backend/.env
GEMINI_API_KEY=AIzaSy...
RAG_PROVIDER=gemini
```

## 🚀 如何使用

### 1. 启动后端服务

```bash
cd backend
python -m uvicorn app.main:app --reload
```

### 2. 创建小说项目并生成章节

使用 **3Agent 模式** 生成章节时，系统会自动：
1. 将生成的章节入库到 Gemini Corpus
2. 生成后续章节时自动搜索相关内容

### 3. 测试 API 配置（可选）

提供了测试 API 端点：

```bash
# 获取管理员 Token
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}' \
  | jq -r '.access_token')

# 测试 Gemini RAG 配置
curl -X POST http://localhost:8000/api/admin/test-gemini-rag \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  | jq
```

**预期返回：**
```json
{
  "success": true,
  "message": "✅ Gemini API Key 有效！已连接到 Google AI，找到 0 个 Corpus",
  "api_key_configured": true,
  "api_key_valid": true,
  "provider": "gemini",
  "corpus_accessible": null,
  "error_detail": null
}
```

## 🛠️ 测试脚本

项目根目录提供了几个测试脚本：

### 1. `test_gemini_key.py` - API Key 验证
```bash
python3 test_gemini_key.py
```

### 2. `check_config.py` - 查看数据库配置
```bash
python3 check_config.py
```

### 3. `insert_config.py` - 更新数据库配置
```bash
# 编辑脚本修改 API_KEY 和 PROVIDER 变量
python3 insert_config.py
```

## 📝 重要说明

### 网络环境

如果运行环境有 SSL 拦截或代理，可能无法直接测试 API Key。解决方案：
1. 在本地环境测试（无代理）
2. 通过前端界面配置后，由后端在实际使用时连接

### API Key 安全

- ✅ `.env` 文件已添加到 `.gitignore`，不会被提交
- ✅ 数据库文件 `arboris.db` 也不会被提交
- ⚠️  生产环境务必使用 HTTPS 传输
- ⚠️  前端显示时需脱敏（`AIza****...`）

### 配额管理

免费额度：1500次/天

- 每次章节生成 ≈ 1次写入 + 1次搜索 = 2次调用
- 理论上每天可生成 **750章**
- 如果超出配额，系统会自动降级到关键词搜索

## 🔗 参考文档

- 📖 [前端配置指南](./GEMINI_RAG_FRONTEND_CONFIG.md)
- 📖 [测试 API 文档](./GEMINI_RAG_TEST_API.md)
- 🔗 [Google AI Studio](https://aistudio.google.com/app/apikey) - 管理 API Key

## ❓ 常见问题

### Q1: 如何切换回本地向量库？
```bash
# 修改数据库配置
python3 insert_config.py  # 将 PROVIDER 改为 'libsql'
```

### Q2: 如何查看 Corpus 中有多少章节？
运行测试 API 会返回 Corpus 数量，或查看后端日志。

### Q3: 删除项目时 Corpus 会被清理吗？
会的，项目删除时会自动调用 `delete_corpus()` 清理 Gemini 数据。

---

🎉 **配置完成！现在可以开始使用 Gemini RAG 功能了。**
