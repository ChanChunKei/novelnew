# Planner 格式问题根本原因分析与修复方案

## 🔍 问题现象

用户生成的1903章中，有7章保存的内容是 Planner 格式的 JSON：
```json
{
  "analysis": "xxx",
  "plan": "xxx",
  "queries_summary": "xxx",
  "notes_for_writer": "xxx"
}
```

而不是实际的章节正文内容。

---

## 🧐 根本原因分析

### 代码流程追踪

1. **Writer Agent 调用** (`ai_orchestrator_helper.py:1657`)
   - 最多2轮生成（round 0 和 round 1）
   - 第二轮强制使用 `response_format="json_object"`
   - 返回应该包含 `full_content` 字段

2. **输出格式验证** (`ai_orchestrator_helper.py:1735-1751`)
   ```python
   if "full_content" not in response or not response["full_content"]:
       if round_num == 0:
           continue  # 进入第二轮
       else:
           raise ValueError(...)  # 第二轮失败，抛出异常
   ```

3. **Planner 格式检测** (`ai_orchestrator_helper.py:1766-1779`)
   ```python
   if suspicious_count >= 2:
       logger.warning(...)  # ⚠️  只是警告，不阻止
   ```

4. **内容保存** (`auto_generator_service.py:919-1022`)
   ```python
   if "full_content" in variant and variant["full_content"]:
       contents.append(full_content)  # 保存
   else:
       raise ValueError(...)  # 没有 full_content 应该抛出异常
   ```

### 可能的原因

**最可能的原因**：Writer Agent 在第一轮返回了包含 `full_content` 字段的响应，但 **`full_content` 的值本身是 Planner 格式的 JSON 字符串**。

例如：
```json
{
  "full_content": "{\n  \"analysis\": \"...\",\n  \"plan\": \"...\"\n}",
  "writing_notes": "..."
}
```

这样：
1. ✅ 通过了第1735行的检查（有 `full_content` 字段）
2. ✅ 第1766-1779行只是警告，不阻止保存
3. ✅ 通过了第919行的检查（有 `full_content` 字段）
4. ❌ 最终保存的内容是 Planner JSON

### 为什么 Writer 会返回 Planner 格式？

**可能的原因**：
1. **Prompt 混淆**：Writer prompt 中包含了 Planner 的输出示例
2. **模型理解错误**：模型误解了要求，把 Planner 的内容当作写作内容
3. **上下文污染**：Planner 的输出在 Writer 的上下文中，模型复制了它
4. **Prompt 中缺少明确的格式约束**

---

## ✅ 修复方案

### 方案1：加强 Writer 输出验证（立即生效）

在 `ai_orchestrator_helper.py:1779` 后面，**将警告改为抛出异常**：

```python
if suspicious_count >= 2:
    logger.error(
        f"❌ Writer返回的full_content包含planner格式内容（检测到{suspicious_count}个planner关键词）\n"
        f"  前200字: {full_content[:200]}"
    )
    if round_num == 0:
        logger.warning("⚠️  第一轮检测到Planner格式，将进入第二轮重新生成")
        continue  # 进入第二轮
    else:
        # ✅ 第二轮还是Planner格式，抛出异常阻止保存
        raise ValueError(
            "生成失败：Writer返回的full_content是Planner格式，而不是章节正文。"
            f"检测到{suspicious_count}个planner关键词: {planner_keywords}"
        )
```

### 方案2：检测并自动提取（防御性编程）

在 `auto_generator_service.py:920` 后面，添加 Planner 格式检测：

```python
full_content = variant["full_content"]

# ✅ 检测是否是 Planner 格式的 JSON
if isinstance(full_content, str):
    content_stripped = full_content.strip()
    if content_stripped.startswith("{") and content_stripped.endswith("}"):
        try:
            parsed = json.loads(content_stripped)
            # 检查是否是 Planner 格式
            planner_fields = ['analysis', 'plan', 'queries_summary', 'notes_for_writer']
            has_planner = sum(1 for f in planner_fields if f in parsed)

            if has_planner >= 3:
                logger.error(
                    f"❌ 第 {next_chapter_number} 章版本 {idx+1}: "
                    f"full_content是Planner格式而非章节正文！"
                )
                raise ValueError(
                    f"第 {next_chapter_number} 章版本 {idx+1} 生成失败："
                    f"full_content包含Planner格式内容，拒绝保存"
                )
        except json.JSONDecodeError:
            pass  # 不是JSON，继续正常流程
```

### 方案3：优化 Writer Prompt（治本）

在 Writer 的 system prompt 中：

1. **明确要求输出格式**：
   ```
   你必须返回JSON格式，包含以下字段：
   {
     "full_content": "完整的章节正文内容（纯文本，不要包含JSON结构）",
     "writing_notes": "写作说明（可选）"
   }

   ⚠️  重要：full_content 必须是纯文本的章节内容，不要返回分析、计划等结构化内容。
   ⚠️  不要在 full_content 中包含 JSON 对象！
   ```

2. **添加反面示例**：
   ```
   ❌ 错误示例（不要这样）：
   {
     "full_content": "{\"analysis\": \"...\", \"plan\": \"...\"}"
   }

   ✅ 正确示例：
   {
     "full_content": "第一章\n\n林远站在村口..."
   }
   ```

3. **移除可能导致混淆的 Planner 示例**

### 方案4：添加重试逻辑

在检测到 Planner 格式时，自动重试：

```python
MAX_PLANNER_RETRY = 2  # 最多重试2次

for retry in range(MAX_PLANNER_RETRY):
    writer_result = await _call_writer_agent(...)

    # 检测是否是 Planner 格式
    full_content = writer_result.get("full_content", "")
    if is_planner_format(full_content):
        logger.warning(
            f"⚠️  检测到Planner格式（第{retry+1}次），重新生成..."
        )
        # 在 writer_context 中添加明确的指令
        writer_context += "\n\n⚠️  注意：请返回完整的章节正文，不要返回分析、计划等结构化内容。"
        continue

    break  # 成功生成正常内容
else:
    raise ValueError("Writer多次返回Planner格式，生成失败")
```

---

## 🚀 推荐实施顺序

1. **立即修复**（方案1）：加强验证，阻止 Planner 格式保存
2. **短期修复**（方案2）：在保存前再次检测
3. **中期优化**（方案3）：优化 Writer prompt
4. **长期完善**（方案4）：添加智能重试

---

## 📊 验证方法

修复后，测试生成新章节：

```bash
# 1. 生成测试章节
# （通过前端或API生成）

# 2. 立即检查
python3 batch_check_all_chapters.py ~/novel/backend/storage/arboris.db

# 3. 查看日志
tail -f backend/logs/app.log | grep -i "planner\|full_content"
```

如果修复成功，应该看到：
- ✅ 日志中出现"检测到Planner格式，重新生成"
- ✅ 最终生成的章节内容正常
- ✅ `batch_check_all_chapters.py` 不再检测到新的 Planner 格式章节

---

## 🔧 现有问题章节的修复

对于已经保存的7章 Planner 格式章节：

1. **如果有 `full_content` 嵌套**：
   - 使用 `extract_full_content.py` 提取

2. **如果完全是 Planner 输出**：
   - 标记为失败，重新生成
   - 或者手动编写内容

```bash
# 批量检查并修复
python3 fix_all_planner_chapters.py ~/novel/backend/storage/arboris.db
```

---

##💡 其他建议

1. **监控和报警**：
   - 在生成日志中添加 Planner 格式检测的统计
   - 如果检测率超过5%，触发报警

2. **定期审计**：
   - 每天运行 `batch_check_all_chapters.py`
   - 及时发现和修复问题

3. **模型选择**：
   - 考虑使用更强的模型（如 GPT-4）作为 Writer
   - 更强的模型更能理解复杂的格式要求

4. **Prompt 版本管理**：
   - 记录 Prompt 的修改历史
   - 出现问题时可以回滚

---

**优先级**：🔴 高 - 需要立即修复，防止继续生成错误内容
