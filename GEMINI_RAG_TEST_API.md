# Gemini RAG 测试 API 使用指南

## 📡 API 端点

```
POST /api/admin/test-gemini-rag
```

需要管理员权限（Bearer Token）

## 📝 请求格式

### 基础测试（不指定项目）

```bash
curl -X POST http://localhost:8000/api/admin/test-gemini-rag \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 测试指定项目的 Corpus 访问

```bash
curl -X POST http://localhost:8000/api/admin/test-gemini-rag \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "test_project_id": "your-project-uuid-here"
  }'
```

## 📊 返回格式

```json
{
  "success": true,
  "message": "✅ Gemini API Key 有效！已连接到 Google AI，找到 3 个 Corpus\n✅ 项目 abc123 的 Corpus 可访问: corpora/novel-project-abc123",
  "api_key_configured": true,
  "api_key_valid": true,
  "provider": "gemini",
  "corpus_accessible": true,
  "error_detail": null
}
```

## 🎯 测试场景

### 场景1：未配置 API Key

**返回：**
```json
{
  "success": false,
  "message": "未配置 Gemini API Key",
  "api_key_configured": false,
  "api_key_valid": false,
  "provider": "libsql",
  "corpus_accessible": null,
  "error_detail": "请在系统配置中设置 gemini.api_key"
}
```

### 场景2：API Key 无效

**返回：**
```json
{
  "success": false,
  "message": "❌ Gemini API Key 无效或权限不足",
  "api_key_configured": true,
  "api_key_valid": false,
  "provider": "gemini",
  "corpus_accessible": null,
  "error_detail": "错误详情: 400 API key not valid..."
}
```

### 场景3：API Key 有效

**返回：**
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

### 场景4：测试项目 Corpus 访问

**返回：**
```json
{
  "success": true,
  "message": "✅ Gemini API Key 有效！已连接到 Google AI，找到 1 个 Corpus\n✅ 项目 abc123 的 Corpus 可访问: corpora/novel-project-abc123",
  "api_key_configured": true,
  "api_key_valid": true,
  "provider": "gemini",
  "corpus_accessible": true,
  "error_detail": null
}
```

### 场景5：依赖未安装

**返回：**
```json
{
  "success": false,
  "message": "❌ 缺少 google-generativeai 依赖",
  "api_key_configured": true,
  "api_key_valid": false,
  "provider": "gemini",
  "corpus_accessible": null,
  "error_detail": "请运行: pip install google-generativeai"
}
```

## 🚀 使用流程

### 1. 配置 API Key

```bash
# 方式A：直接操作数据库
sqlite3 storage/arboris.db "UPDATE system_configs SET value='AIzaSy...' WHERE key='gemini.api_key';"
sqlite3 storage/arboris.db "UPDATE system_configs SET value='gemini' WHERE key='rag.provider';"

# 方式B：通过前端界面（需要实现）
# PUT /api/admin/system-config/gemini.api_key
```

### 2. 测试连接

```bash
# 获取管理员 Token
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}' \
  | jq -r '.access_token')

# 测试 Gemini RAG
curl -X POST http://localhost:8000/api/admin/test-gemini-rag \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  | jq
```

### 3. 查看结果

成功示例：
```
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

## 📋 测试检查项

API 会依次检查：

1. ✅ **配置检查**
   - 检查数据库中的 `gemini.api_key`
   - 回退检查环境变量 `GEMINI_API_KEY`
   - 检查 `rag.provider` 配置

2. ✅ **连接测试**
   - 使用 API Key 连接 Google AI
   - 尝试列出 Corpus（验证权限）
   - 返回已有 Corpus 数量

3. ✅ **项目测试**（可选）
   - 测试指定项目的 Corpus 创建/访问
   - 验证端到端功能

## 🔧 故障排查

### 问题1：401 Unauthorized

**原因：** 未提供管理员 Token 或 Token 无效

**解决：**
```bash
# 重新登录获取 Token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'
```

### 问题2：api_key_configured=false

**原因：** 未配置 Gemini API Key

**解决：**
```bash
# 配置 API Key
sqlite3 storage/arboris.db "UPDATE system_configs SET value='AIzaSy...' WHERE key='gemini.api_key';"

# 或设置环境变量
echo "GEMINI_API_KEY=AIzaSy..." >> .env
```

### 问题3：api_key_valid=false

**原因：** API Key 无效或权限不足

**解决：**
1. 检查 API Key 是否正确（格式：`AIzaSy...`，39个字符）
2. 访问 https://aistudio.google.com/app/apikey 重新生成
3. 确认 API Key 有 Semantic Retrieval 权限

### 问题4：corpus_accessible=false

**原因：** Corpus 创建/访问失败

**解决：**
1. 检查项目 ID 是否正确
2. 检查 API Key 是否有创建 Corpus 的权限
3. 查看后端日志获取详细错误信息

## 🎨 前端集成示例

### React/TypeScript 示例

```typescript
import { Button, message } from 'antd';
import { useState } from 'react';

interface TestResult {
  success: boolean;
  message: string;
  api_key_configured: boolean;
  api_key_valid: boolean;
  provider: string;
  corpus_accessible?: boolean;
  error_detail?: string;
}

function GeminiRAGTest() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);

  const testConnection = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/admin/test-gemini-rag', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      });

      const data = await response.json();
      setResult(data);

      if (data.success) {
        message.success('测试成功！');
      } else {
        message.error('测试失败');
      }
    } catch (error) {
      message.error('请求失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Button type="primary" onClick={testConnection} loading={loading}>
        测试 Gemini RAG 连接
      </Button>

      {result && (
        <div style={{ marginTop: 16 }}>
          <p><strong>状态：</strong>{result.success ? '✅ 成功' : '❌ 失败'}</p>
          <p><strong>消息：</strong>{result.message}</p>
          <p><strong>API Key 已配置：</strong>{result.api_key_configured ? '是' : '否'}</p>
          <p><strong>API Key 有效：</strong>{result.api_key_valid ? '是' : '否'}</p>
          <p><strong>RAG 提供方：</strong>{result.provider}</p>
          {result.error_detail && (
            <p style={{ color: 'red' }}><strong>错误详情：</strong>{result.error_detail}</p>
          )}
        </div>
      )}
    </div>
  );
}
```

## 📞 支持

如有问题，请检查：
1. 后端日志：`tail -f backend/logs/app.log`
2. API Key 格式是否正确
3. 网络连接是否正常

---

**快速测试脚本：**

```bash
#!/bin/bash
# test-gemini.sh

# 配置
API_URL="http://localhost:8000"
ADMIN_USER="admin"
ADMIN_PASS="your-password"

# 登录获取 Token
echo "1. 登录获取 Token..."
TOKEN=$(curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" \
  | jq -r '.access_token')

if [ "$TOKEN" = "null" ]; then
  echo "❌ 登录失败"
  exit 1
fi

echo "✅ 登录成功"

# 测试 Gemini RAG
echo -e "\n2. 测试 Gemini RAG..."
curl -s -X POST "$API_URL/api/admin/test-gemini-rag" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  | jq

echo -e "\n✅ 测试完成"
```

使用：
```bash
chmod +x test-gemini.sh
./test-gemini.sh
```
