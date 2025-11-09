# 自动恢复机制修复说明

## 📋 问题描述

### 原始问题

1. **`target_chapters=None` 导致任务卡住**
   - 用户在前端没填写"目标章节数"
   - 后端接收到 `target_chapters=None`
   - 任务启动但不知道要生成多少章节，导致卡住

2. **服务重启后任务丢失**
   - 后台任务（`_run_generator`）运行在 API 进程的内存中
   - 数据库状态：`running`
   - 实际状态：后台任务已丢失（`_running_tasks` 字典被清空）
   - 结果：任务显示运行中，但实际没有生成任何内容

### 时间线示例

```
08:37 - 用户启动任务42 (target_chapters=None)
10:25 - 用户启动任务44 (target_chapters=None, 三Agent对话模式)
10:26 - 用户启动任务45 (target_chapters=None)
         ↓
10:34 - 服务器重启 sudo systemctl restart arboris-api
         ↓
10:34 - 所有后台任务丢失（_running_tasks 字典清空）
10:34 - 但数据库中状态还是 'running'
         ↓
结果  - 任务显示运行中，但实际没有生成章节
      - 异步处理器空转（查不到 pending_analysis 记录）
```

---

## ✅ 修复方案

### 修复1：自动推断 target_chapters

**位置**: `backend/app/services/auto_generator_service.py` 第103-115行

**逻辑**:
```python
# 如果 target_chapters 为 None，从章节大纲数量自动推断
if target_chapters is None:
    result = await db.execute(
        select(ChapterOutline).where(
            ChapterOutline.project_id == project_id
        )
    )
    outlines = result.scalars().all()
    if outlines:
        target_chapters = len(outlines)
        logger.info(f"Auto-inferred target_chapters={target_chapters}")
    else:
        logger.warning(f"No outlines found, target_chapters will remain None")
```

**效果**:
- ✅ 有大纲：自动设置为大纲数量（如90章）
- ⚠️ 无大纲：保持 `None`（无限生成模式）

---

### 修复2：服务启动时自动恢复任务

**位置**:
- `auto_generator_service.py` 第266-333行 - `recover_running_tasks()` 方法
- `main.py` 第80-85行 - 启动时调用

**恢复逻辑**:
```python
@classmethod
async def recover_running_tasks(cls, db: AsyncSession) -> int:
    """恢复所有运行中的后台任务（服务器重启后调用）"""

    # 1. 查询所有状态为 'running' 的任务
    result = await db.execute(
        select(AutoGeneratorTask).where(
            AutoGeneratorTask.status == "running"
        )
    )
    running_tasks = result.scalars().all()

    # 2. 遍历每个任务
    for task in running_tasks:
        # 检查是否已经在运行
        if task.id in cls._running_tasks:
            continue

        # 修复 target_chapters=None
        if task.target_chapters is None:
            # 从大纲数量推断
            ...

        # 重新启动后台任务
        asyncio_task = asyncio.create_task(cls._run_generator(task.id))
        cls._running_tasks[task.id] = asyncio_task

    return recovered_count
```

**在 `main.py` 中调用**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_sqlite_wal()

    # ... 预热提示词缓存

    # ✅ 新增：恢复运行中的后台任务
    async with AsyncSessionLocal() as session:
        from .services.auto_generator_service import AutoGeneratorService
        recovered_count = await AutoGeneratorService.recover_running_tasks(session)
        if recovered_count > 0:
            logging.getLogger(__name__).info(f"✅ 自动恢复了 {recovered_count} 个运行中的任务")

    yield
```

---

## 🧪 测试步骤

### 测试1：验证自动推断功能

1. **前端操作**:
   - 打开"自动生成器"页面
   - **不填写**"目标章节数"（留空）
   - 选择任意生成模式
   - 点击"创建并启动任务"

2. **预期结果**:
   ```bash
   # 查看 API 日志
   sudo journalctl -u arboris-api -f | grep "Auto-inferred"

   # 应该看到：
   # Auto-inferred target_chapters=90 from outlines for project xxx
   ```

3. **数据库验证**:
   ```bash
   cd ~/novel/backend
   source venv/bin/activate

   python3 << 'EOF'
   import sqlite3
   conn = sqlite3.connect("storage/arboris.db")
   cursor = conn.cursor()

   cursor.execute("""
       SELECT id, project_id, target_chapters, status
       FROM auto_generator_tasks
       ORDER BY id DESC
       LIMIT 3
   """)

   for row in cursor.fetchall():
       print(f"任务 {row[0]}: target_chapters={row[2]}, status={row[3]}")

   conn.close()
   EOF
   ```

   **预期**: `target_chapters` 不再是 `None`，而是实际的大纲数量

---

### 测试2：验证自动恢复功能

1. **创建测试任务**:
   - 在前端创建一个新任务并启动
   - 确认任务状态为 `running`
   - 等待几秒让它开始生成

2. **模拟服务器重启**:
   ```bash
   # 重启 API 服务
   sudo systemctl restart arboris-api
   ```

3. **查看恢复日志**:
   ```bash
   sudo journalctl -u arboris-api -n 50 | grep -E "恢复|recover|running"

   # 应该看到类似输出：
   # 🔄 开始恢复运行中的后台任务...
   # ✅ 任务 45: 修复 target_chapters=90
   # ✅ 任务 45 已恢复运行
   # ✅ 自动恢复了 1 个运行中的任务
   ```

4. **验证任务继续运行**:
   ```bash
   # 监控异步处理器
   sudo journalctl -u arboris-async-processor -f

   # 应该看到章节生成任务开始执行
   ```

5. **前端验证**:
   - 刷新"自动生成器"页面
   - 任务状态应该还是 `running`
   - "已生成章节数"应该持续增加

---

### 测试3：验证三Agent对话模式恢复

1. **创建三Agent任务**:
   - 生成模式选择"👥 三Agent对话模式"
   - 不填写目标章节数（测试自动推断）
   - 启动任务

2. **重启服务**:
   ```bash
   sudo systemctl restart arboris-api
   sudo systemctl restart arboris-async-processor
   ```

3. **查看日志**:
   ```bash
   # 查看是否恢复
   sudo journalctl -u arboris-api -n 50 | grep "恢复"

   # 监控三Agent对话过程
   sudo journalctl -u arboris-async-processor -f | grep -E "三Agent|思考Agent|写作Agent|审批Agent"
   ```

4. **预期结果**:
   - ✅ 任务自动恢复
   - ✅ `target_chapters` 被正确设置
   - ✅ 三Agent对话流程正常运行
   - ✅ 可以看到完整的对话日志

---

## 📊 修复效果对比

### 修复前

| 场景 | 问题 | 表现 |
|------|------|------|
| 不填目标章节数 | `target_chapters=None` | 任务卡住，不生成内容 |
| 服务重启 | 后台任务丢失 | 任务显示 `running` 但实际停止 |
| 暂停/停止 | 数据库锁 | 操作失败，需要多次重试 |

### 修复后

| 场景 | 修复 | 表现 |
|------|------|------|
| 不填目标章节数 | 自动从大纲推断 | 任务正常运行，生成所有大纲章节 |
| 服务重启 | 自动恢复任务 | 任务继续运行，无需手动操作 |
| 暂停/停止 | 数据库锁重试 | 操作成功，自动重试恢复 |

---

## 📝 技术细节

### 1. 为什么后台任务会丢失？

**原因**: 后台任务存储在 Python 进程的内存中

```python
class AutoGeneratorService:
    # 类变量，存储在进程内存中
    _running_tasks: dict[int, asyncio.Task] = {}
```

- ❌ **进程重启** → 内存清空 → 字典被清空
- ✅ **数据库状态** → 持久化存储 → 状态保留为 `running`

**结果**: 状态不一致

### 2. 恢复机制的核心

**关键代码** (`main.py` 启动时):
```python
async with AsyncSessionLocal() as session:
    recovered_count = await AutoGeneratorService.recover_running_tasks(session)
```

**恢复流程**:
```
启动 API 服务
    ↓
初始化数据库
    ↓
启用 WAL 模式
    ↓
恢复运行中的任务 ← ✅ 新增
    ├─ 查询 status='running' 的任务
    ├─ 修复 target_chapters=None
    └─ 重新启动后台任务 (asyncio.create_task)
    ↓
启动验证码清理
    ↓
服务就绪
```

### 3. 并发安全

使用锁保护共享字典：
```python
async with cls._tasks_lock:
    if task.id in cls._running_tasks:
        continue  # 避免重复启动
```

---

## 🎯 适用场景

### 场景1：日常重启维护
```bash
# 部署新代码
git pull
pip install -r requirements.txt
sudo systemctl restart arboris-api  # ✅ 任务自动恢复
```

### 场景2：服务器故障恢复
```bash
# 服务器意外重启
# 系统启动 → systemd 启动服务 → 任务自动恢复
```

### 场景3：手动测试重启
```bash
# 测试恢复机制
sudo systemctl restart arboris-api
sudo journalctl -u arboris-api -f | grep "恢复"
```

---

## ⚠️ 注意事项

### 1. 无大纲的项目

如果项目没有章节大纲：
- `target_chapters` 保持 `None`
- 任务会**无限生成**（AI自主决定章节数）
- 需要**手动停止**任务

### 2. 恢复失败的处理

如果某个任务恢复失败：
- 会记录错误日志
- 继续恢复其他任务
- 可以手动重启该任务

### 3. 性能考虑

- 信号量限制：最多5个任务同时创建
- 数据库重试：最多10次，总计~204秒
- 适合几十个并发任务

---

## 📚 相关文档

- `EXTREME_CONCURRENCY_FIX.md` - 极端并发优化
- `AGENT_DIALOGUE_MODE.md` - 三Agent对话模式
- `VERSION_UPDATE_GUIDE.md` - 版本更新指南

---

## ✅ 总结

### 关键改进

1. **✅ 智能推断**: `target_chapters=None` → 自动从大纲数量推断
2. **✅ 自动恢复**: 服务重启 → 自动恢复所有运行中的任务
3. **✅ 状态同步**: 数据库状态 ↔ 实际运行状态保持一致

### 用户体验

- **无感知恢复**: 服务重启后任务继续运行，用户无需任何操作
- **智能默认值**: 不填目标章节数时自动使用大纲数量
- **稳定可靠**: 支持几十个任务同时运行，重启后全部恢复

### 下一步

如需进一步优化：
- 考虑将后台任务移到独立进程（如 Celery）
- 添加任务健康检查机制（检测卡住的任务）
- 实现任务优先级队列

---

**更新日期**: 2025-11-07
**版本**: v1.2.0
