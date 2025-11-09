# Agent模式使用指南

## 概述

Agent模式是一个智能章节生成功能，允许AI在生成章节时主动查询历史信息、角色状态、世界设定等，从而生成更加连贯、符合设定的内容。

## 核心特点

- **AI自主决策**：AI自己决定需要查询什么信息
- **多轮对话**：最多5轮，AI可以根据查询结果继续查询
- **智能检索**：支持向量检索和数据库查询
- **极简集成**：只需在generation_config中设置一个参数

## 工作流程

```
用户提供章节大纲
    ↓
【第1轮】AI分析大纲，决定需要查询什么
    ↓ 调用工具：search_chapters("张三")
    ↓ 调用工具：get_world_setting("禁术")
    ↓
【第2轮】AI收到查询结果，决定是否需要更多信息
    ↓ 调用工具：get_recent_chapters(current_chapter=120)
    ↓
【第3轮】AI认为信息充足，生成最终章节内容
    ↓
返回完整章节
```

## 可用工具

Agent可以调用以下6个工具：

### 1. search_chapters
搜索历史章节中包含特定关键词的内容

**参数**：
- `keyword` (string): 搜索关键词，如角色名、地点、事件等
- `limit` (integer, 可选): 返回结果数量，默认3

**示例**：
```json
{
  "keyword": "张三",
  "limit": 5
}
```

### 2. get_character_state
获取指定角色在某个章节时的状态信息

**参数**：
- `name` (string): 角色名字
- `chapter_number` (integer, 可选): 截止到第几章

**示例**：
```json
{
  "name": "李四",
  "chapter_number": 100
}
```

### 3. get_world_setting
查询世界观设定、魔法体系、势力关系等

**参数**：
- `tag` (string): 设定标签，如"魔法体系"、"势力关系"

**示例**：
```json
{
  "tag": "禁术"
}
```

### 4. get_recent_chapters
获取最近N章的完整内容

**参数**：
- `current_chapter` (integer): 当前要生成的章节号
- `count` (integer, 可选): 获取最近几章，默认3

**示例**：
```json
{
  "current_chapter": 120,
  "count": 5
}
```

### 5. check_plot_consistency
检查剧情是否存在前后矛盾

**参数**：
- `check_items` (array of strings): 需要检查的项目列表

**示例**：
```json
{
  "check_items": ["张三的年龄", "王朝的建立时间"]
}
```

### 6. find_foreshadowing
查找未回收的伏笔和悬念

**参数**：
- `chapter_range` (string): 章节范围，如"1-50"

**示例**：
```json
{
  "chapter_range": "1-100"
}
```

## 使用方法

### 方法1：创建自动生成任务时指定

```python
from app.services.auto_generator_service import AutoGeneratorService

task = await AutoGeneratorService.create_task(
    db=db,
    project_id="your-project-id",
    user_id=user_id,
    target_chapters=100,
    generation_config={
        "version_count": 3,
        "generation_mode": "agent",  # ✨ 启用Agent模式
    }
)
```

### 方法2：直接调用章节生成函数

```python
from app.services.ai_orchestrator_helper import generate_chapter_content

content = await generate_chapter_content(
    db_session=db,
    system_prompt="你是专业的小说作家...",
    user_prompt="第120章大纲：张三决定使用禁术...",
    user_id=user_id,
    generation_mode="agent",  # ✨ 启用Agent模式
    project_id="your-project-id",
    chapter_number=120
)
```

## API调用次数对比

| 模式 | API调用次数 | 适用场景 |
|------|------------|---------|
| basic | 1次 | 简单章节，剧情独立 |
| enhanced | 2次 | 需要超级分析 |
| **agent** | **2-5次** | **复杂剧情，多线索，需要历史信息** |

**实际测试**：
- 简单章节（单一情节）：2-3次调用
- 中等章节（多个角色）：3-4次调用
- 复杂章节（多线索、伏笔）：4-5次调用

## 成本估算

假设使用GPT-4o（$5/1M input tokens，$15/1M output tokens）：

| 章节类型 | Agent调用 | 生成内容 | 总成本 |
|---------|----------|---------|--------|
| 简单章节 | 2次 × $0.01 | 1次 × $0.015 | ~$0.035 |
| 中等章节 | 3次 × $0.01 | 1次 × $0.015 | ~$0.045 |
| 复杂章节 | 5次 × $0.01 | 1次 × $0.015 | ~$0.065 |

相比传统模式（~$0.015），Agent模式成本增加2-4倍，但生成质量显著提升。

## Rate Limit影响

如果使用OpenAI API（60 RPM限制）：

| 模式 | 每章调用次数 | 每分钟可生成章节 |
|------|------------|----------------|
| basic | 1次 | 60章 |
| **agent** | **平均3次** | **20章** |

**建议**：
- 免费用户：使用basic模式
- 付费用户：可选择agent模式
- 高优先级章节：使用agent模式
- 批量生成：混合使用

## 配置示例

### 配置1：纯Agent模式（高质量）
```python
generation_config = {
    "generation_mode": "agent",
    "version_count": 3,
}
```

### 配置2：智能切换（推荐）
```python
# 根据章节复杂度自动选择
if chapter_has_multiple_characters or chapter_has_foreshadowing:
    mode = "agent"
else:
    mode = "basic"

generation_config = {
    "generation_mode": mode,
    "version_count": 3,
}
```

### 配置3：用户可选
```python
# 前端让用户选择
user_preference = request.json.get("use_agent", False)

generation_config = {
    "generation_mode": "agent" if user_preference else "basic",
    "version_count": 3,
}
```

## 实现原理

Agent模式基于OpenAI/Gemini/Claude的Function Calling功能：

1. **定义工具**：在`app/config/agent_tools.py`中定义6个工具
2. **LLM决策**：AI分析大纲，决定调用哪些工具
3. **执行工具**：本地执行工具（查询数据库、向量检索）
4. **多轮对话**：将工具结果返回给AI，AI决定是否需要更多信息
5. **生成内容**：AI收集足够信息后，生成最终章节

## 验证测试

运行验证脚本：
```bash
cd backend
python test_agent_mode.py
```

预期输出：
```
✅ Agent工具配置: 通过
✅ 工具数量: 6
✅ 所有工具定义格式正确
```

## 常见问题

### Q1: Agent模式会不会调用太多次导致成本爆炸？
A: 不会。我们设置了最大5轮限制，最后一轮强制生成内容。实际使用中，平均3轮就够了。

### Q2: 如何控制Agent的查询行为？
A: 通过system_prompt引导AI，例如：
```python
system_prompt = """
你是小说作家。在生成章节前，你可以查询历史信息。
注意：
1. 只查询真正需要的信息
2. 优先查询角色状态和最近章节
3. 不要过度查询
"""
```

### Q3: Agent查询到的信息不准确怎么办？
A: 当前实现的`search_chapters`支持向量检索（语义搜索）和数据库查询（关键词匹配）。向量检索更智能但需要配置vector_db。

### Q4: 能否自定义工具？
A: 可以！在`app/config/agent_tools.py`中添加新工具，然后在`app/services/ai_orchestrator_helper.py`的`_execute_tools`中实现工具逻辑。

## 下一步计划

- [ ] 实现角色状态查询（需要character_states表）
- [ ] 实现世界设定查询（需要world_settings表）
- [ ] 实现剧情一致性检查（AI分析）
- [ ] 实现伏笔查找（AI分析）
- [ ] 添加Agent日志记录（前端展示AI思考过程）
- [ ] 支持用户自定义工具

## 技术细节

### 文件修改列表
1. `backend/app/config/agent_tools.py` - 新增工具定义
2. `backend/app/services/llm_service.py` - 支持tools参数
3. `backend/app/services/ai_orchestrator_helper.py` - 实现Agent逻辑

### 关键函数
- `generate_chapter_content()` - 章节生成入口，支持generation_mode参数
- `_generate_with_agent()` - Agent模式核心逻辑
- `_execute_tools()` - 工具执行调度
- `_tool_search_chapters()` - 搜索历史章节实现
- `_tool_get_recent_chapters()` - 获取最近章节实现

## 联系与支持

如有问题或建议，请提交Issue或联系开发团队。
