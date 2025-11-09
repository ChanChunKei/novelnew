# 番茄小说自动上传功能使用指南

## 功能概述

本功能实现了将本地创作的小说一键上传到番茄小说平台的能力。基于Playwright浏览器自动化技术，完全模拟真实用户操作流程。

## 核心特性

- ✅ **Cookie持久化登录** - 一次登录，长期使用
- ✅ **自动分卷同步** - 自动创建和编辑分卷，与本地结构保持一致
- ✅ **批量章节上传** - 按顺序自动上传所有章节
- ✅ **失败即停止** - 遇到错误立即停止，避免数据混乱
- ✅ **审核后立即发布** - 不使用AI，审核通过后自动发布
- ✅ **详细日志记录** - 完整记录上传过程，便于排查问题

## 使用流程

### 第一步：准备工作

1. **在本地系统中创作小说**
   - 创建小说项目
   - 完善分卷结构
   - 生成50-100章内容（或更多）
   - 确保章节内容完整

2. **在番茄小说平台手动创建书籍**
   - 访问 [番茄小说作家专区](https://fanqienovel.com/writer/zone/)
   - 点击"创建新书"
   - 填写书籍信息（**书名必须与本地小说名称一致**）
   - 完成创建

### 第二步：登录并保存Cookie

#### 方法1：使用API接口（推荐）

```bash
# 发送POST请求到登录接口
curl -X POST "http://localhost:8000/api/novels/fanqie/login" \
  -H "Content-Type: application/json" \
  -d '{
    "account": "default",
    "wait_seconds": 60
  }'
```

#### 方法2：使用测试脚本

```bash
cd backend
python test_fanqie_upload.py login
```

**操作步骤：**
1. 执行上述命令后，会自动打开浏览器窗口
2. 在浏览器中手动完成登录（输入账号密码、滑块验证等）
3. 登录成功后，页面会跳转到作家专区
4. Cookie会自动保存到 `storage/fanqie_cookies/default_cookies.json`

**注意事项：**
- 默认等待60秒，如果登录较慢可以增加 `wait_seconds` 参数
- Cookie保存后可以长期使用，除非番茄小说要求重新登录
- 如果有多个账号，可以使用不同的 `account` 标识

### 第三步：一键上传小说

#### 方法1：使用API接口（推荐）

```bash
# 发送POST请求到上传接口
curl -X POST "http://localhost:8000/api/novels/{project_id}/upload-to-fanqie" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "account": "default"
  }'
```

#### 方法2：使用测试脚本

```bash
cd backend
python test_fanqie_upload.py upload <project_id>
```

**上传流程：**
1. 系统自动加载保存的Cookie
2. 通过书名查找番茄小说上的书籍
3. 同步分卷结构：
   - 第一卷：编辑默认分卷名称
   - 后续分卷：创建新分卷
4. 批量上传章节：
   - 按章节号顺序上传
   - 自动填写章节号、标题、正文
   - 自动处理风险检测
   - 选择"否"使用AI
   - 关闭定时发布（审核通过后立即发布）
5. 返回详细的上传结果

**返回结果示例：**
```json
{
  "success": true,
  "book_id": "7566974951480118297",
  "book_name": "修仙之路",
  "volume_count": 3,
  "chapter_count": 50,
  "volume_sync_results": [
    {"success": true, "old_name": "默认", "new_name": "初入修仙界"},
    {"success": true, "volume_name": "筑基之路"},
    {"success": true, "volume_name": "金丹大道"}
  ],
  "upload_results": [
    {"success": true, "chapter_number": 1, "title": "踏入仙途", "status": "已提交审核"},
    {"success": true, "chapter_number": 2, "title": "筑基之路", "status": "已提交审核"},
    ...
  ]
}
```

## 技术实现细节

### 1. 书籍匹配

通过书名精确匹配本地小说和番茄小说上的书籍：

```python
book_id = await publisher.find_book_by_name(book_name)
```

- 访问作家专区
- 遍历所有书籍卡片
- 查找书名匹配的书籍
- 提取book_id

### 2. 分卷同步

根据本地分卷结构，自动创建/编辑番茄小说的分卷：

```python
# 第一卷：编辑默认分卷名称
await publisher.edit_volume_name("默认", volume.title)

# 后续分卷：创建新分卷
await publisher.create_volume(volume.title)
```

**编辑分卷流程：**
1. 点击"编辑分卷"按钮
2. 点击编辑图标进入编辑模式
3. 填写新的分卷名称
4. 点击对勾图标确认
5. 点击"确定"按钮保存

### 3. 章节上传

按顺序上传每一章：

```python
await publisher.publish_chapter(
    chapter_number=chapter.chapter_number,
    chapter_title=chapter_title,
    content=content,
    volume_name=volume_name,
    use_ai=False
)
```

**上传流程：**
1. 点击"新建章节"按钮
2. 填写章节号（纯数字）
3. 填写标题（自动清理"第X章"前缀，确保至少5字）
4. 填写正文（使用ProseMirror编辑器）
5. 点击"下一步"
6. 处理内容风险检测对话框
7. 选择"否"使用AI
8. 确保定时发布关闭
9. 点击"确认发布"
10. 验证提交成功

### 4. 错误处理

- **失败即停止策略**：任何步骤失败都会立即停止上传
- **详细错误信息**：返回具体的错误原因和失败位置
- **状态保存**：记录已上传的章节，便于断点续传（未来功能）

## 常见问题

### Q1: Cookie过期怎么办？

**A:** 重新执行登录流程即可：
```bash
python test_fanqie_upload.py login
```

### Q2: 书名不匹配怎么办？

**A:** 确保番茄小说上的书名与本地小说名称完全一致。如果不一致，可以：
1. 修改番茄小说上的书名
2. 或修改本地小说的标题

### Q3: 上传失败如何重试？

**A:** 检查错误信息，解决问题后重新执行上传命令。系统会跳过已上传的章节（未来功能）。

### Q4: 可以同时上传多本书吗？

**A:** 不建议。建议一本一本上传，避免并发问题。

### Q5: 上传速度慢怎么办？

**A:** 番茄小说平台有速率限制，建议：
- 不要频繁上传
- 每章之间有自动延迟
- 避免在高峰期上传

### Q6: 支持定时发布吗？

**A:** 当前版本不支持定时发布，所有章节审核通过后立即发布。如需定时发布，请在番茄小说平台手动设置。

## 注意事项

1. **书名必须一致**：番茄小说上的书名必须与本地小说名称一致
2. **手动创建书籍**：必须先在番茄小说平台手动创建书籍
3. **Cookie安全**：Cookie文件包含登录凭证，请妥善保管
4. **内容审核**：上传后需要等待平台审核，预计1小时内完成
5. **章节顺序**：按章节号顺序上传，不支持乱序
6. **分卷限制**：只有当前分卷有章节时才能创建新分卷

## 未来计划

- [ ] 断点续传：记录上传进度，支持从失败处继续
- [ ] 实时进度：WebSocket实时推送上传进度
- [ ] 批量管理：支持批量上传多本书
- [ ] 定时上传：支持定时发布章节
- [ ] 自动重试：失败后自动重试
- [ ] 章节更新：支持更新已发布的章节

## 技术支持

如有问题，请查看日志文件或联系开发团队。

日志位置：
- 应用日志：`logs/app.log`
- 上传日志：控制台输出

## 相关文件

- 服务实现：`backend/app/services/fanqie_publisher_service.py`
- API路由：`backend/app/api/routers/novels.py`
- 测试脚本：`backend/test_fanqie_upload.py`
- Cookie存储：`storage/fanqie_cookies/`

