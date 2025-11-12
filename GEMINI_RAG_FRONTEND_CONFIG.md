# Gemini RAG 前端配置指南

## 📝 概述

Gemini RAG 现在支持前端配置！管理员可以在前端界面直接配置 API Key 和 RAG 提供方，无需修改后端代码或环境变量。

## ✨ 新功能

- ✅ **前端可配置**：通过前端界面配置 Gemini API Key
- ✅ **实时生效**：配置更新后立即生效，无需重启服务
- ✅ **数据库存储**：配置保存在数据库 `system_configs` 表中
- ✅ **环境变量后备**：未配置时自动回退到环境变量

## 🔧 配置方法

### 方式1：前端配置（推荐）

1. **运行数据库迁移**（首次使用）
   ```bash
   cd backend
   sqlite3 ../storage/arboris.db < migrations/add_gemini_rag_config.sql
   ```

2. **前端配置界面**（需要前端实现配置页面）

   配置项：
   - **gemini.api_key**: Google Gemini API Key（格式：`AIzaSy...`）
   - **rag.provider**: RAG 提供方（可选：`gemini` 或 `libsql`）

   示例代码（前端需要添加）：
   ```javascript
   // PUT /api/admin/system-config
   {
     "gemini.api_key": "AIzaSy...",
     "rag.provider": "gemini"
   }
   ```

### 方式2：直接操作数据库

```bash
cd backend

# 设置 Gemini API Key
sqlite3 ../storage/arboris.db "UPDATE system_configs SET value='AIzaSy...' WHERE key='gemini.api_key';"

# 设置 RAG 提供方为 gemini
sqlite3 ../storage/arboris.db "UPDATE system_configs SET value='gemini' WHERE key='rag.provider';"

# 验证配置
sqlite3 ../storage/arboris.db "SELECT * FROM system_configs WHERE key IN ('gemini.api_key', 'rag.provider');"
```

### 方式3：环境变量（向后兼容）

仍然支持通过 `.env` 文件配置：

```bash
# backend/.env 或项目根目录/.env
GEMINI_API_KEY=AIzaSy...
RAG_PROVIDER=gemini
```

**配置优先级：** 数据库 > 环境变量

## 📊 配置说明

### gemini.api_key

- **描述**：Google Gemini API Key
- **格式**：`AIzaSy...`（39个字符）
- **获取方式**：https://aistudio.google.com/app/apikey
- **是否必需**：仅在 `rag.provider=gemini` 时必需

### rag.provider

- **描述**：RAG 检索提供方
- **可选值**：
  - `gemini`：使用 Google Gemini Semantic Retrieval（推荐）
  - `libsql`：使用本地向量库（需配置 VECTOR_DB_URL）
- **默认值**：`libsql`（保持向后兼容）
- **是否必需**：是

## 🚀 测试配置

### 1. 验证配置已生效

启动后端服务后，查看日志：

```
✅ Gemini RAG 服务初始化成功
```

### 2. 生成章节测试

生成一章新内容，观察日志：

```
✅ 第 1 章已入库到 Gemini Corpus
```

### 3. 搜索测试

生成第二章时，3Agent 模式会调用 search_chapters 工具：

```
✅ Gemini RAG 搜索成功: query='xxx', 结果数=3
```

## 🛠️ 前端实现参考

### API 端点（需要实现）

```typescript
// GET /api/admin/system-config/:key
// 获取单个配置项
interface SystemConfig {
  key: string;
  value: string;
  description?: string;
}

// PUT /api/admin/system-config/:key
// 更新配置项
interface UpdateSystemConfig {
  value: string;
}

// GET /api/admin/system-config
// 批量获取配置
interface SystemConfigsResponse {
  configs: SystemConfig[];
}
```

### 前端配置表单示例

```tsx
// 管理后台 - 系统配置
<Form>
  <Form.Item label="Gemini API Key" name="gemini.api_key">
    <Input.Password
      placeholder="AIzaSy..."
      help="从 https://aistudio.google.com/app/apikey 获取"
    />
  </Form.Item>

  <Form.Item label="RAG 提供方" name="rag.provider">
    <Select>
      <Select.Option value="gemini">
        Gemini (Google 托管，免费)
      </Select.Option>
      <Select.Option value="libsql">
        LibSQL (本地向量库)
      </Select.Option>
    </Select>
  </Form.Item>

  <Form.Item>
    <Button type="primary" htmlType="submit">
      保存配置
    </Button>
  </Form.Item>
</Form>
```

## 🔒 安全建议

1. **API Key 安全**：
   - 仅管理员可访问配置界面
   - 前端显示时脱敏（`AIza****...`）
   - 传输时使用 HTTPS

2. **权限控制**：
   - 配置 API 端点需要管理员权限
   - 记录配置更改日志

3. **验证**：
   - 保存前验证 API Key 格式
   - 测试 API Key 是否有效

## 📝 配置示例

### 示例1：使用 Gemini（推荐）

```sql
UPDATE system_configs SET value='AIzaSyXXXXXX' WHERE key='gemini.api_key';
UPDATE system_configs SET value='gemini' WHERE key='rag.provider';
```

**效果：**
- 零配置向量搜索
- 免费额度 1500次/天
- Google 全托管

### 示例2：使用本地向量库

```sql
UPDATE system_configs SET value='libsql' WHERE key='rag.provider';
```

**需要额外配置：**
```bash
# .env
VECTOR_DB_URL=file:./storage/vector.db
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-...
```

## ❓ 常见问题

### Q1: 配置后没有生效？

**A**: 检查：
1. 数据库迁移是否执行成功
2. 后端服务是否重启
3. 日志中是否显示 "✅ Gemini RAG 服务初始化成功"

### Q2: 如何切换回环境变量配置？

**A**: 清空数据库配置：
```sql
UPDATE system_configs SET value='' WHERE key='gemini.api_key';
```
系统会自动回退到读取环境变量。

### Q3: 多个用户可以配置不同的 API Key 吗？

**A**: 当前版本是系统级配置（全局共享）。如需用户级配置，需要扩展 `llm_configs` 表。

## 📞 支持

如有问题，请查看日志或提交 Issue。
