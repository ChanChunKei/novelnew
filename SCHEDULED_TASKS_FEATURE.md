# 定时启动任务功能 - 使用说明

## 功能概述

新增的定时启动功能可以智能地错开多个项目的任务启动时间，避免 SQLite 写锁冲突，提高系统稳定性。

### 主要特性

1. **智能间隔计算** - 根据项目数量自动计算最佳启动间隔和生成间隔
2. **批量创建任务** - 一键为所有项目创建任务，自动错开启动时间
3. **时长选择器** - 预设的生成间隔选项（30分钟到24小时）
4. **单个任务调整** - 可以单独修改每个任务的调度设置

## 安装步骤

### 1. 运行数据库迁移

迁移文件已创建在 `backend/migrations/add_scheduled_start.sql`，需要运行迁移来添加新字段：

```bash
# 方法1: 使用项目的迁移脚本
cd backend
python run_migration.py

# 方法2: 如果使用 Docker
docker exec -it <container_name> python backend/run_migration.py
```

迁移会添加以下字段到 `auto_generator_tasks` 表：
- `scheduled_start_time` - 定时启动时间（TIMESTAMP）
- `delay_seconds` - 启动延迟秒数（INTEGER）
- `batch_id` - 批次ID，用于标识批量创建的任务（VARCHAR(36)）

### 2. 重启后端服务

```bash
# 重启服务以加载新的 API 端点
# 具体命令根据你的部署方式而定
```

## API 端点

### 1. 获取调度选项

**GET** `/api/auto-generator/schedule-options`

返回预设的生成间隔和启动延迟选项。

**响应示例:**
```json
{
  "generation_intervals": [
    {"value": 1800, "label": "30min", "display": "30分钟"},
    {"value": 3600, "label": "1hour", "display": "1小时"},
    {"value": 7200, "label": "2hour", "display": "2小时"},
    {"value": 10800, "label": "3hour", "display": "3小时"},
    {"value": 21600, "label": "6hour", "display": "6小时"},
    {"value": 43200, "label": "12hour", "display": "12小时"},
    {"value": 86400, "label": "24hour", "display": "24小时"}
  ],
  "start_delays": [
    {"value": 0, "label": "now", "display": "立即"},
    {"value": 300, "label": "5min", "display": "5分钟"},
    {"value": 600, "label": "10min", "display": "10分钟"},
    {"value": 1800, "label": "30min", "display": "30分钟"},
    {"value": 3600, "label": "1hour", "display": "1小时"},
    {"value": 10800, "label": "3hour", "display": "3小时"},
    {"value": 21600, "label": "6hour", "display": "6小时"},
    {"value": 43200, "label": "12hour", "display": "12小时"},
    {"value": 86400, "label": "24hour", "display": "24小时"}
  ]
}
```

### 2. 批量创建任务

**POST** `/api/auto-generator/batch-tasks`

为所有项目或指定项目批量创建任务，自动计算最佳启动间隔。

**请求体:**
```json
{
  "project_ids": null,              // 可选：项目ID列表，null表示所有项目
  "generation_interval": 3600,      // 可选：生成间隔（秒），null表示自动计算
  "auto_start": true,               // 是否自动启动
  "auto_upload": false,             // 是否自动上传到番茄
  "fanqie_account": null            // 番茄账号
}
```

**响应示例:**
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "tasks_created": 5,
  "start_interval": 300,            // 启动间隔：5分钟
  "generation_interval": 3600,      // 生成间隔：1小时
  "max_concurrent": 3,              // 建议最大并发数
  "estimated_cycle_time": 1500,     // 完成一轮启动的时间：25分钟
  "schedule": [
    {
      "project_id": "proj-001",
      "project_title": "我的小说1",
      "task_id": 101,
      "scheduled_start_time": "2025-11-07T16:00:00Z",
      "delay_seconds": 0,
      "interval_seconds": 3600
    },
    {
      "project_id": "proj-002",
      "project_title": "我的小说2",
      "task_id": 102,
      "scheduled_start_time": "2025-11-07T16:05:00Z",
      "delay_seconds": 300,
      "interval_seconds": 3600
    }
    // ... 更多任务
  ]
}
```

### 3. 更新任务调度

**PATCH** `/api/auto-generator/tasks/{task_id}/schedule`

修改单个任务的调度设置。

**请求体:**
```json
{
  "scheduled_start_time": "2025-11-07T18:00:00Z",  // 可选：新的启动时间
  "delay_seconds": 600,                             // 可选：新的延迟秒数
  "interval_seconds": 7200                          // 可选：新的生成间隔
}
```

**响应:** 返回更新后的任务对象

## 智能调度算法

### 启动间隔计算

启动间隔 = max(5分钟, 生成时长 × 2)

- 默认生成时长：2分钟
- 安全系数：2.0
- 最小间隔：5分钟

**目的:** 让任务错开启动，避免同时生成章节

### 生成间隔计算

根据项目数量动态调整：

| 项目数量 | 生成间隔 | 说明 |
|---------|---------|------|
| ≤ 3 个   | 1小时   | 少量项目，可以频繁生成 |
| 4-6 个   | 2小时   | 中等数量，适当延长 |
| 7-9 个   | 4小时   | 较多项目，延长间隔 |
| ≥ 10 个  | 6小时   | 大量项目，大幅延长 |

**目的:** 确保同时运行的任务数 ≤ 3（SQLite 最佳并发数）

## 使用场景

### 场景1: 一键启动所有项目

适合有多个项目需要同时自动生成的情况。

```bash
# API 调用示例
curl -X POST http://localhost:8000/api/auto-generator/batch-tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "project_ids": null,
    "generation_interval": 3600,
    "auto_start": true
  }'
```

系统会：
1. 自动获取所有项目
2. 计算最佳启动间隔（例如5分钟）
3. 为每个项目创建任务
4. 第1个项目立即开始
5. 第2个项目5分钟后开始
6. 第3个项目10分钟后开始
7. 依此类推...

### 场景2: 指定项目批量启动

只为选定的项目创建任务。

```bash
curl -X POST http://localhost:8000/api/auto-generator/batch-tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "project_ids": ["proj-001", "proj-003", "proj-005"],
    "generation_interval": 7200,
    "auto_start": true
  }'
```

### 场景3: 自动计算生成间隔

让系统根据项目数量自动计算最佳生成间隔。

```bash
curl -X POST http://localhost:8000/api/auto-generator/batch-tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "project_ids": null,
    "generation_interval": null,  // null表示自动计算
    "auto_start": true
  }'
```

### 场景4: 调整单个任务

创建批量任务后，可以单独调整某个任务的时间。

```bash
# 将任务102的启动时间推迟到晚上8点
curl -X PATCH http://localhost:8000/api/auto-generator/tasks/102/schedule \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "scheduled_start_time": "2025-11-07T20:00:00Z"
  }'
```

## 前端集成建议

### 1. 创建批量启动页面

```typescript
// 组件结构建议
<BatchTasksForm>
  <ProjectSelector />           // 选择项目（可选）
  <IntervalSelector />          // 生成间隔下拉选择
  <AutoUploadToggle />          // 自动上传开关
  <FanqieAccountInput />        // 番茄账号输入
  <SubmitButton />              // "一键启动所有项目"按钮
</BatchTasksForm>

<TaskScheduleTable>            // 显示调度计划
  <TaskRow                     // 每个任务一行
    project={task.project}
    scheduledTime={task.scheduled_start_time}
    interval={task.interval_seconds}
    onEdit={handleEditSchedule}  // 点击可编辑单个任务
  />
</TaskScheduleTable>
```

### 2. API 调用示例

```typescript
// 获取预设选项
async function getScheduleOptions() {
  const response = await fetch('/api/auto-generator/schedule-options');
  return response.json();
}

// 批量创建任务
async function createBatchTasks(params) {
  const response = await fetch('/api/auto-generator/batch-tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_ids: params.projectIds,
      generation_interval: params.interval,
      auto_start: true,
      auto_upload: params.autoUpload,
      fanqie_account: params.fanqieAccount
    })
  });
  return response.json();
}

// 更新任务调度
async function updateTaskSchedule(taskId, schedule) {
  const response = await fetch(`/api/auto-generator/tasks/${taskId}/schedule`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(schedule)
  });
  return response.json();
}
```

### 3. UI/UX 建议

1. **生成间隔选择器** - 使用下拉菜单或单选按钮
   - 30分钟
   - 1小时 ⭐ 推荐
   - 2小时
   - 3小时
   - 6小时
   - 12小时
   - 24小时

2. **调度计划展示** - 表格形式显示
   - 项目名称
   - 预计启动时间（倒计时）
   - 生成间隔
   - 编辑按钮

3. **实时状态更新** - WebSocket 或轮询
   - 显示任务当前状态
   - 显示距离下次生成的剩余时间
   - 显示已生成章节数

## 注意事项

1. **SQLite 并发限制**
   - SQLite 同时只能有1个写操作
   - 建议同时运行的任务数 ≤ 3
   - 如果项目数 > 10，建议使用 PostgreSQL

2. **启动时间精度**
   - 系统每10秒检查一次是否到达启动时间
   - 实际启动时间可能有 ±10秒的误差

3. **任务状态**
   - 任务创建后状态为 `running`
   - 但在到达 `scheduled_start_time` 之前，任务会等待
   - 日志会记录 "定时启动：将在 XXX 开始生成"

4. **修改已启动的任务**
   - 如果任务已经到达启动时间并开始生成，修改 `scheduled_start_time` 不会生效
   - 只能修改 `interval_seconds` 来调整生成间隔

## 故障排查

### 问题1: 任务创建缓慢

**症状:** 调用 `/batch-tasks` 接口很慢，需要等很久才返回

**原因:** SQLite 写锁竞争，已有太多任务在运行

**解决:**
1. 检查当前运行的任务数：
   ```bash
   python check_task_performance.py
   ```
2. 停止部分任务，减少并发数
3. 或使用定时启动功能错开任务

### 问题2: 任务不启动

**症状:** 任务创建后一直不开始生成

**原因:** 可能 `scheduled_start_time` 设置在未来

**解决:**
1. 检查任务的 `scheduled_start_time` 字段
2. 如果需要立即启动，将该字段设置为 `null`
3. 或等待到达预定时间

### 问题3: 所有任务同时启动

**症状:** 虽然设置了不同的 `scheduled_start_time`，但任务还是同时开始

**原因:** 可能数据库迁移未正确执行

**解决:**
1. 检查数据库表结构：
   ```sql
   PRAGMA table_info(auto_generator_tasks);
   ```
2. 确认存在 `scheduled_start_time`、`delay_seconds`、`batch_id` 字段
3. 如果不存在，重新运行迁移

## 性能优化建议

1. **项目数量 ≤ 5**
   - 生成间隔：1小时
   - 启动间隔：5分钟
   - 预计：25分钟内所有任务启动完成

2. **项目数量 6-10**
   - 生成间隔：2-4小时
   - 启动间隔：5分钟
   - 预计：30-50分钟内所有任务启动完成

3. **项目数量 > 10**
   - 生成间隔：6小时
   - 启动间隔：5分钟
   - 建议考虑迁移到 PostgreSQL
   - 或分批启动（每批3-5个项目）

## 版本信息

- **创建日期:** 2025-11-07
- **数据库迁移:** `add_scheduled_start.sql`
- **相关服务:** `TaskSchedulerService`
- **API 版本:** v1
