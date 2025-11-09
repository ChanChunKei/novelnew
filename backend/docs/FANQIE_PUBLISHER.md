# 番茄小说自动发布服务使用文档

## 📚 功能概述

番茄小说自动发布服务(`FanqiePublisherService`)使用Playwright浏览器自动化技术,实现了以下功能:

- ✅ 自动登录番茄小说作家后台
- ✅ 自动发布章节(支持风险检测和智能纠错)
- ✅ 自动创建和管理分卷
- ✅ 批量发布章节
- ✅ Cookie持久化(避免重复登录)

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install playwright
playwright install chromium
```

### 2. 基本使用

```python
from app.services.fanqie_publisher_service import FanqiePublisherService

async def publish_example():
    async with FanqiePublisherService() as publisher:
        # 加载Cookie(如果有)
        await publisher.load_cookies()
        
        # 导航到书籍
        await publisher.navigate_to_book("你的书籍ID")
        
        # 发布章节
        result = await publisher.publish_chapter(
            chapter_number=1,
            chapter_title="穿越异世界",  # 不要包含"第1章"
            content="章节内容...",
            volume_name="第一卷",  # 可选
            run_risk_detection=True,
            auto_correct_errors=True
        )
        
        print(result)
```

## 📖 详细功能说明

### 1. 初始化和登录

#### 方式1: 使用Cookie自动登录(推荐)

```python
async with FanqiePublisherService() as publisher:
    # 加载保存的Cookie
    cookie_loaded = await publisher.load_cookies("fanqie_cookies.json")
    
    if not cookie_loaded:
        # 首次使用,需要手动登录
        await publisher.page.goto("https://fanqienovel.com/main/writer/book-manage")
        # 在浏览器中手动登录...
        await publisher.page.wait_for_url("**/main/writer/**", timeout=120000)
        # 保存Cookie供下次使用
        await publisher.save_cookies("fanqie_cookies.json")
```

#### 方式2: 程序化登录(如果支持)

```python
async with FanqiePublisherService() as publisher:
    success = await publisher.login("username", "password")
    if success:
        await publisher.save_cookies()
```

### 2. 发布章节

#### 基本发布

```python
result = await publisher.publish_chapter(
    chapter_number=1,
    chapter_title="穿越异世界",
    content="章节内容(至少1000字才能使用风险检测)...",
)
```

#### 完整参数

```python
result = await publisher.publish_chapter(
    chapter_number=1,              # 章节序号(纯数字)
    chapter_title="穿越异世界",     # 标题(不要包含"第X章")
    content="...",                 # 章节内容
    volume_name="第一卷",          # 分卷名称(可选)
    run_risk_detection=True,       # 是否运行风险检测
    auto_correct_errors=True,      # 是否自动纠错
    use_ai=False,                  # 是否标记为AI生成
    scheduled_publish=False        # 是否定时发布
)

# 返回结果
{
    "success": True,
    "chapter_number": 1,
    "title": "穿越异世界",
    "status": "审核中"
}
```

### 3. 批量发布

```python
chapters = [
    {
        "chapter_number": 1,
        "title": "穿越异世界",
        "content": "...",
        "volume_name": "第一卷"
    },
    {
        "chapter_number": 2,
        "title": "初入江湖",
        "content": "...",
        "volume_name": "第一卷"
    },
]

results = await publisher.batch_publish_chapters(
    chapters=chapters,
    interval_seconds=10  # 每章间隔10秒
)
```

### 4. 创建分卷

```python
result = await publisher.create_volume("第二卷")

# 注意:只有当前分卷有章节时才能创建新分卷
# 如果失败,返回:
{
    "success": False,
    "error": "暂不支持创建多个无章节的分卷",
    "message": "无法创建多个空分卷,请先在当前分卷发布章节"
}
```

## ⚠️ 重要注意事项

### 1. 章节标题格式

❌ **错误**: `chapter_title="第一章 穿越异世界"`  
✅ **正确**: `chapter_title="穿越异世界"`

番茄小说会自动添加"第X章"前缀,所以标题中不要重复包含。

### 2. 风险检测要求

- 章节内容至少需要**1000字**才能使用风险检测
- 建议每次发布都运行风险检测,避免违规内容

### 3. 分卷创建限制

- **不能创建多个空分卷**
- 必须先在当前分卷发布章节,才能创建下一个分卷
- 分卷名称最多20个字符

### 4. 发布间隔

- 批量发布时建议设置间隔(5-10秒)
- 避免频繁操作触发反爬虫机制

## 🔧 与AI生成系统集成

### 自动发布生成的章节

```python
from app.services.fanqie_publisher_service import FanqiePublisherService
from app.services.novel_service import NovelService

async def auto_publish_generated_chapters(project_id: str, user_id: int, db: AsyncSession):
    """自动发布AI生成的章节"""

    # 1. 获取项目信息
    novel_service = NovelService(db)
    # ✅ 修复：使用 ensure_project_owner 获取包含 chapters 的完整对象
    # get_project_schema 返回的 chapters 字段是空列表（性能优化）
    project = await novel_service.ensure_project_owner(project_id, user_id)

    # 2. 筛选已生成但未发布的章节
    unpublished_chapters = [
        ch for ch in project.chapters
        if ch.selected_version_id is not None  # 已选择版本
    ]
    
    # 3. 准备发布数据
    chapters_to_publish = []
    for ch in unpublished_chapters:
        # 获取分卷信息
        volume_name = None
        if ch.volume_number:
            volume = next((v for v in project.blueprint.volumes if v.volume_number == ch.volume_number), None)
            if volume:
                volume_name = volume.title
        
        chapters_to_publish.append({
            "chapter_number": ch.chapter_number,
            "title": ch.title,
            "content": ch.content,
            "volume_name": volume_name
        })
    
    # 4. 发布到番茄小说
    async with FanqiePublisherService() as publisher:
        await publisher.load_cookies()
        await publisher.navigate_to_book("你的书籍ID")
        
        results = await publisher.batch_publish_chapters(
            chapters=chapters_to_publish,
            interval_seconds=10
        )
    
    # 5. 更新发布状态
    for i, result in enumerate(results):
        if result["success"]:
            chapter = unpublished_chapters[i]
            # 标记为已发布
            await novel_service.mark_chapter_published(
                project_id,
                chapter.chapter_number
            )
    
    return results
```

## 🐛 调试技巧

### 1. 查看浏览器操作

```python
# 使用非无头模式,可以看到浏览器操作
async with FanqiePublisherService() as publisher:
    await publisher.init_browser(headless=False)  # 显示浏览器
    # ...
```

### 2. 截图调试

```python
# 在关键步骤截图
await publisher.page.screenshot(path="debug_screenshot.png")
```

### 3. 日志输出

```python
import logging
logging.basicConfig(level=logging.INFO)

# 服务会自动输出详细日志
```

## 📝 测试脚本

运行测试脚本:

```bash
cd backend
python scripts/test_fanqie_publisher.py
```

测试脚本提供三种测试模式:
1. 发布单个章节
2. 批量发布章节
3. 创建分卷

## 🔐 安全建议

1. **Cookie文件保护**: `fanqie_cookies.json`包含登录信息,不要提交到Git
2. **添加到.gitignore**:
   ```
   fanqie_cookies.json
   ```
3. **定期更新Cookie**: Cookie可能过期,需要重新登录

## 📊 性能优化

1. **复用浏览器实例**: 批量发布时复用同一个浏览器
2. **合理设置间隔**: 避免过快操作被限流
3. **异步并发**: 如果有多本书,可以并发发布

## ❓ 常见问题

### Q: Cookie过期怎么办?
A: 删除`fanqie_cookies.json`,重新手动登录并保存Cookie

### Q: 发布失败怎么办?
A: 检查日志输出,常见原因:
- 章节序号重复
- 内容违规
- 网络问题
- Cookie过期

### Q: 如何获取书籍ID?
A: 在番茄小说作家后台,书籍管理页面的URL中包含书籍ID

### Q: 可以同时发布多本书吗?
A: 可以,创建多个`FanqiePublisherService`实例

## 📞 技术支持

如有问题,请查看:
- 日志输出
- 浏览器截图
- 网络请求记录

