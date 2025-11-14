# 3Agent Planner内容误保存Bug修复设计文档

## Overview

本设计文档描述如何修复3Agent对话模式中Planner Agent的分析内容被误保存为章节正文的Bug。核心策略是在数据流的多个关键点添加验证和检测逻辑，确保只有Writer Agent生成的章节正文被保存到数据库。

## Architecture

### 数据流分析

```
Planner Agent
  ↓ 返回 {"analysis": "...", "plan": "...", ...}
  ↓
验证点1: _call_planner_agent() 
  ↓ 确保不包含 full_content 字段
  ↓
_build_writer_context()
  ↓ 只提取文本建议，不传递JSON结构
  ↓
Writer Agent
  ↓ 返回 {"full_content": "...", "writing_notes": "..."}
  ↓
验证点2: _call_writer_agent() - 清理前检测
  ↓ 检测Planner格式（支持Markdown包裹）
  ↓
验证点3: _call_writer_agent() - 清理后检测
  ↓ 再次检测Planner关键词
  ↓
_generate_with_agent_dialogue_impl()
  ↓ 提取 final_content
  ↓
验证点4: auto_generator_service.py
  ↓ 保存前最终验证
  ↓
ChapterVersion.content (数据库)
```

### 关键修复点

1. **Planner输出验证** - 确保Planner不返回full_content
2. **清理前检测** - 在Markdown清理前检测Planner格式
3. **增强关键词检测** - 支持Markdown包裹的关键词
4. **多层验证** - 在保存前再次验证

## Components and Interfaces

### Component 1: Planner输出验证器

**位置**: `backend/app/services/ai_orchestrator_helper.py` - `_call_planner_agent()`

**功能**: 验证Planner返回的格式，确保不包含full_content字段

**接口**:
```python
async def _call_planner_agent(...) -> Dict[str, Any]:
    """
    返回格式:
    {
        "analysis": str,
        "plan": str,
        "queries_summary": str,
        "notes_for_writer": str
    }
    
    不应包含: full_content, content, summary等Writer专属字段
    """
```

**验证逻辑**:
```python
# 在返回前验证
if "full_content" in response or "content" in response:
    logger.error(
        f"❌ Planner Agent返回了错误的字段: {list(response.keys())}\n"
        f"Planner不应该返回full_content或content字段"
    )
    raise ValueError(
        "Planner Agent返回格式错误：包含full_content字段。"
        "这是Writer Agent的职责，Planner只应返回analysis、plan等分析字段。"
    )
```

### Component 2: 增强的Planner格式检测器

**位置**: `backend/app/services/ai_orchestrator_helper.py` - `_call_writer_agent()`

**功能**: 在Markdown清理前检测Planner格式内容

**检测策略**:

1. **多格式关键词检测**:
```python
def _detect_planner_format(content: str, check_length: int = 1000) -> tuple[bool, int, list]:
    """
    检测内容是否为Planner格式
    
    Returns:
        (is_planner, suspicious_count, matched_keywords)
    """
    planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
    matched = []
    
    check_text = content[:check_length].lower()
    
    for kw in planner_keywords:
        # 检测多种格式
        patterns = [
            f'{kw}:',           # analysis:
            f'"{kw}":',         # "analysis":
            f'**{kw}**',        # **analysis** (Markdown粗体)
            f'__{kw}__',        # __analysis__ (Markdown粗体)
            f'## {kw}',         # ## analysis (Markdown标题)
            f'### {kw}',        # ### analysis
            f'# {kw}',          # # analysis
            f'*{kw}*',          # *analysis* (Markdown斜体)
        ]
        
        for pattern in patterns:
            if pattern.lower() in check_text:
                matched.append(f"{kw} ({pattern})")
                break
    
    suspicious_count = len(matched)
    is_planner = suspicious_count >= 2
    
    return is_planner, suspicious_count, matched
```

2. **检测时机**: 在`_clean_full_content()`调用之前

**实现位置**:
```python
# 在 _call_writer_agent() 中
# 步骤1: 先检测原始内容（清理前）
full_content_raw = response["full_content"]
is_planner, count, matched = _detect_planner_format(full_content_raw)

if is_planner:
    logger.error(
        f"❌ Writer返回的full_content包含Planner格式（检测到{count}个关键词）\n"
        f"  匹配的关键词: {matched}\n"
        f"  前200字: {full_content_raw[:200]}"
    )
    if round_num == 0:
        continue  # 第一轮重试
    else:
        raise ValueError(...)  # 第二轮抛异常

# 步骤2: 清理
response["full_content"] = _clean_full_content(...)

# 步骤3: 清理后再次检测（防止漏检）
full_content_cleaned = response["full_content"]
is_planner_after, count_after, matched_after = _detect_planner_format(full_content_cleaned)

if is_planner_after:
    # 清理后仍然检测到，说明是真的Planner格式
    ...
```

### Component 3: Writer上下文构建器改进

**位置**: `backend/app/services/ai_orchestrator_helper.py` - `_build_writer_context()`

**当前问题**: 已经正确实现，只提取文本建议

**验证**: 确保不传递完整的planner_result JSON

**当前实现**:
```python
# ✅ 正确：只提取文本建议
planner_guidance = []
if planner_result.get("analysis"):
    planner_guidance.append(f"【章节分析】\n{planner_result['analysis']}")
if planner_result.get("plan"):
    planner_guidance.append(f"【内容规划】\n{planner_result['plan']}")
# ...

# ❌ 错误（不要这样做）：
# context = json.dumps(planner_result)  # 会传递完整JSON
```

**无需修改**，当前实现已正确。

### Component 4: 保存前最终验证

**位置**: `backend/app/services/auto_generator_service.py` - 章节内容提取部分

**功能**: 在保存到数据库前进行最终验证

**实现**:
```python
# 在提取full_content后，保存前
if "full_content" in variant and variant["full_content"]:
    full_content = variant["full_content"]
    
    # ... 现有的嵌套JSON检测和清理 ...
    
    # ✅ 新增：最终Planner格式检测
    is_planner, count, matched = _detect_planner_format_final(full_content)
    if is_planner:
        logger.error(
            f"❌ 第 {next_chapter_number} 章版本 {idx+1}: "
            f"最终验证检测到Planner格式内容（{count}个关键词）\n"
            f"  匹配: {matched}\n"
            f"  这不应该发生，说明前置验证有漏洞"
        )
        raise ValueError(
            f"第 {next_chapter_number} 章版本 {idx+1} 保存失败："
            f"内容包含Planner格式（{matched}），拒绝保存。"
        )
    
    contents.append(full_content)
```

## Data Models

### Planner输出格式

```python
PlannnerOutput = {
    "analysis": str,              # 对章节的分析
    "plan": str,                  # 内容规划
    "queries_summary": str,       # 查询结果总结
    "notes_for_writer": str,      # 给Writer的建议
    # ❌ 不应包含: full_content, content, summary
}
```

### Writer输出格式

```python
WriterOutput = {
    "full_content": str,          # 章节正文（必需）
    "writing_notes": str,         # 创作说明（可选）
    # ❌ 不应包含: analysis, plan, queries_summary
}
```

### 检测结果格式

```python
DetectionResult = {
    "is_planner": bool,           # 是否为Planner格式
    "suspicious_count": int,      # 检测到的关键词数量
    "matched_keywords": List[str], # 匹配的关键词列表
    "check_length": int,          # 检测的字符长度
}
```

## Error Handling

### 错误类型

1. **PlannerFormatError**: Planner返回了full_content字段
2. **WriterPlannerFormatError**: Writer返回了Planner格式内容
3. **FinalValidationError**: 保存前检测到Planner格式

### 错误处理策略

```python
# 第一轮检测到Planner格式
if round_num == 0 and is_planner:
    logger.warning("⚠️ 第一轮检测到Planner格式，进入第二轮重试...")
    continue  # 重试

# 第二轮仍然是Planner格式
if round_num == 1 and is_planner:
    logger.error("❌ 第二轮仍然是Planner格式，终止生成")
    raise ValueError(
        f"生成失败：Writer连续两轮返回Planner格式内容（{matched}），"
        "而不是章节正文。请检查模型配置或prompt。"
    )

# 保存前检测到Planner格式
if is_planner_at_save:
    logger.critical("❌ 保存前检测到Planner格式，这是严重的验证漏洞！")
    raise ValueError("保存失败：内容验证未通过")
```

### 日志级别

- `logger.info`: 正常流程（检测通过）
- `logger.warning`: 第一轮检测到问题，准备重试
- `logger.error`: 第二轮检测到问题，准备抛异常
- `logger.critical`: 保存前检测到问题（不应该发生）

## Testing Strategy

### 单元测试

**测试文件**: `backend/tests/test_planner_format_detection.py`

**测试用例**:

1. **测试Planner格式检测 - 基础格式**
```python
def test_detect_planner_format_basic():
    content = "analysis: 这是分析\nplan: 这是规划"
    is_planner, count, matched = _detect_planner_format(content)
    assert is_planner == True
    assert count == 2
```

2. **测试Planner格式检测 - Markdown包裹**
```python
def test_detect_planner_format_markdown():
    content = "## Analysis\n内容...\n\n**plan**: 规划..."
    is_planner, count, matched = _detect_planner_format(content)
    assert is_planner == True
    assert count >= 2
```

3. **测试正常章节内容不被误判**
```python
def test_normal_content_not_detected():
    content = "第一章\n\n张三走在路上，心中暗自分析着局势..."
    is_planner, count, matched = _detect_planner_format(content)
    assert is_planner == False
```

4. **测试清理前后检测**
```python
def test_detection_before_and_after_cleaning():
    content = "**analysis**: 分析\n## plan\n规划内容"
    
    # 清理前应该检测到
    is_planner_before, _, _ = _detect_planner_format(content)
    assert is_planner_before == True
    
    # 清理后
    cleaned = _strip_markdown_formatting(content)
    is_planner_after, _, _ = _detect_planner_format(cleaned)
    # 清理后可能检测不到，这就是为什么要在清理前检测
```

### 集成测试

**测试场景**:

1. **模拟Writer返回Planner格式**
   - 第一轮返回Planner格式 → 应该重试
   - 第二轮返回正常内容 → 应该成功

2. **模拟Writer连续两轮返回Planner格式**
   - 应该抛出ValueError异常
   - 异常消息应包含具体的关键词信息

3. **模拟Planner返回full_content字段**
   - 应该在_call_planner_agent中被拒绝
   - 应该抛出ValueError异常

### 手动测试

1. **测试正常流程**
   - 生成一个章节，验证内容正确
   - 检查日志，确认所有验证点都通过

2. **测试异常情况**
   - 修改代码模拟Planner返回错误格式
   - 验证是否被正确拒绝

## Implementation Plan

### Phase 1: 核心检测函数（优先级：高）

1. 实现`_detect_planner_format()`函数
2. 添加单元测试
3. 验证检测准确性

### Phase 2: Planner输出验证（优先级：高）

1. 在`_call_planner_agent()`添加输出验证
2. 测试Planner返回错误格式的情况

### Phase 3: Writer清理前检测（优先级：高）

1. 在`_call_writer_agent()`中调整检测顺序
2. 在清理前调用`_detect_planner_format()`
3. 保留清理后的二次检测

### Phase 4: 保存前最终验证（优先级：中）

1. 在`auto_generator_service.py`添加最终验证
2. 作为最后一道防线

### Phase 5: 日志和监控（优先级：中）

1. 完善所有验证点的日志
2. 添加检测统计（触发次数、成功率等）

### Phase 6: 文档和测试（优先级：低）

1. 更新API文档
2. 添加集成测试
3. 编写故障排查指南

## Performance Considerations

### 检测性能

- 检测只扫描前1000字符，性能影响可忽略
- 正则表达式匹配复杂度：O(n)，n为检测长度
- 预期每次检测耗时：< 1ms

### 内存影响

- 检测不创建额外的大对象
- 只存储匹配的关键词列表（通常< 10个元素）
- 内存影响可忽略

## Security Considerations

### 注入攻击防护

虽然本修复主要关注功能正确性，但也考虑了安全性：

1. **不执行用户输入**: 所有检测都是字符串匹配，不执行代码
2. **日志脱敏**: 日志中只记录内容预览（前200字），不记录完整内容
3. **异常消息**: 不暴露内部实现细节

## Rollback Plan

如果修复导致问题：

1. **快速回滚**: 通过Git回滚到修复前的版本
2. **功能开关**: 可以添加配置项临时禁用新的检测逻辑
3. **降级策略**: 保留原有的检测逻辑作为fallback

## Monitoring and Metrics

### 关键指标

1. **Planner格式检测触发次数**: 监控检测到Planner格式的频率
2. **Writer重试次数**: 监控第一轮检测到问题的频率
3. **生成失败率**: 监控因Planner格式导致的失败率
4. **检测准确率**: 监控误判率（正常内容被误判为Planner格式）

### 告警规则

- 如果Planner格式检测触发率 > 5%，发送告警
- 如果生成失败率突然上升，发送告警
- 如果保存前检测触发（不应该发生），立即告警

## Summary

本设计通过在数据流的多个关键点添加验证和检测逻辑，确保Planner Agent的分析内容不会被误保存为章节正文。核心策略是：

1. **在Markdown清理前检测** - 避免关键词被移除
2. **支持多种格式** - 检测Markdown包裹的关键词
3. **多层验证** - 在Planner输出、Writer输出、保存前都进行验证
4. **完善错误处理** - 第一轮重试，第二轮拒绝

预期效果：100%阻止Planner格式内容被保存到数据库。
