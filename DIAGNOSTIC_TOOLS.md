# 3Agent 诊断工具集

完整的诊断工具集，用于检查和修复 3Agent 章节生成问题。

## 📋 工具列表

### 1. 快速预览工具

#### `preview_chapters.py` - 预览最近章节
快速查看最近生成的章节，检测常见格式问题。

```bash
# 预览最近3章（默认）
python3 preview_chapters.py

# 预览最近5章
python3 preview_chapters.py 5

# 指定数据库
python3 preview_chapters.py /path/to/arboris.db 3
```

**检测项目：**
- ✅ 纯 JSON 格式
- ✅ Planner 格式关键词
- ✅ Markdown 代码块标记
- ✅ 字数异常
- ✅ 迭代次数和评分

---

### 2. 详细诊断工具

#### `diagnose_3agent.py` - 详细诊断单个章节
深度分析章节生成过程，查看所有 Agent 的交互历史。

```bash
# 诊断最新章节
python3 diagnose_3agent.py

# 诊断指定章节
python3 diagnose_3agent.py /path/to/db.db 1
```

**分析内容：**
- 📋 内容格式检查（JSON/Planner/Markdown）
- 📊 生成过程分析（迭代次数、评分、耗时）
- 🔍 Agent 调用统计（Planner/Writer/Reviewer/Summarizer）
- 📝 关键步骤展示（每次 Agent 交互的详情）
- 💡 修复建议

---

#### `analyze_writer_output.py` - 分析 Writer 输出格式
查看 Writer Agent 实际返回的内容，定位格式问题根源。

```bash
# 分析最新章节的 Writer 输出
python3 analyze_writer_output.py

# 分析指定章节
python3 analyze_writer_output.py /path/to/db.db 1
```

**检查项目：**
- 🔍 Writer 返回的数据类型（dict/string）
- 🔍 是否包含 `full_content` 字段
- 🔍 `full_content` 的内容格式
- 🔍 所有返回字段的结构
- 🔍 最终存储内容与 Writer 输出的一致性

**用途：**
- 确定 Writer 是否正确返回了 `full_content`
- 发现内容提取逻辑的问题
- 定位是 Writer 问题还是存储问题

---

### 3. 批量检查工具

#### `batch_check_all_chapters.py` - 批量检查所有章节
扫描数据库中所有章节，统计格式问题。

```bash
# 检查所有章节
python3 batch_check_all_chapters.py

# 指定数据库
python3 batch_check_all_chapters.py /path/to/arboris.db
```

**输出：**
- 📊 问题统计（JSON格式、Planner格式、字数过少等）
- 📋 问题章节详情列表
- 💡 针对性的修复建议
- 🔧 批量修复命令

---

#### `compare_chapters.py` - 对比多个章节质量
对比不同章节的生成质量，发现规律和问题。

```bash
# 对比第1,2,3章
python3 compare_chapters.py 1 2 3

# 指定数据库
python3 compare_chapters.py /path/to/arboris.db 1 2 3
```

**对比维度：**
- 字数
- 迭代次数
- 评分
- 生成耗时
- Writer 输出格式
- 问题类型

**统计分析：**
- 平均迭代次数
- 平均评分
- Writer 格式分布
- 问题章节占比

---

### 4. 自动修复工具

#### `fix_broken_chapters.py` - 自动修复格式错误
尝试自动修复常见的格式问题。

```bash
# 预览模式（不实际修改）
python3 fix_broken_chapters.py --dry-run

# 自动修复所有问题章节
python3 fix_broken_chapters.py

# 修复指定章节ID
python3 fix_broken_chapters.py /path/to/db.db 1 2 3
```

**支持修复：**
- ✅ 纯 JSON 格式 → 提取 `full_content`
- ✅ Markdown 代码块 → 移除包裹标记
- ✅ 嵌套 JSON → 递归提取
- ❌ Planner 格式 → 标记为需重新生成
- ❌ 字数过少 → 标记为需重新生成

---

#### `extract_full_content.py` - 手动提取内容
交互式工具，从 JSON 章节中提取 `full_content`。

```bash
# 自动查找所有 JSON 章节
python3 extract_full_content.py

# 提取指定章节
python3 extract_full_content.py /path/to/db.db 123
```

**工作流程：**
1. 自动识别 JSON 格式章节
2. 尝试提取 `full_content` 等字段
3. 显示提取预览
4. 询问是否更新（交互式确认）

---

### 5. 配置和状态检查

#### `check_gemini_status.py` - 检查 Gemini RAG 状态
全面检查 Gemini RAG 配置和使用情况。

```bash
python3 check_gemini_status.py
```

**检查内容：**
- 📋 数据库配置（API Key、Provider）
- 📚 项目列表和 Corpus 信息
- 📄 最近章节生成情况
- 🧪 测试方法说明

---

#### `check_config.py` - 查看数据库配置
快速查看系统配置。

```bash
python3 check_config.py
```

---

#### `insert_config.py` - 更新配置
插入或更新 Gemini 配置。

```bash
# 使用默认值
python3 insert_config.py

# 指定 API Key
python3 insert_config.py /path/to/db.db AIzaSy... gemini
```

---

#### `monitor_gemini_rag.py` - 实时监控日志
实时监控 Gemini RAG 的调用情况。

```bash
python3 monitor_gemini_rag.py
```

---

## 🔍 常见问题诊断流程

### 问题1: 章节内容是纯 JSON 格式

**症状：**
```json
{
  "full_content": "实际的章节内容...",
  "word_count": 2000
}
```

**诊断流程：**
```bash
# 1. 确认问题
python3 preview_chapters.py

# 2. 分析 Writer 输出
python3 analyze_writer_output.py

# 3. 自动修复
python3 fix_broken_chapters.py --dry-run  # 预览
python3 fix_broken_chapters.py            # 执行
```

**原因：**
- 内容提取逻辑未正确处理 `full_content` 字段
- Writer 返回了完整 JSON 对象而非纯文本

---

### 问题2: 章节包含 Planner 格式

**症状：**
```
analysis: 本章需要...
plan:
  - 场景1：...
  - 场景2：...
queries_summary: ...
```

**诊断流程：**
```bash
# 1. 确认问题
python3 diagnose_3agent.py

# 2. 查看 Writer 原始输出
python3 analyze_writer_output.py

# 3. 批量检查是否普遍问题
python3 batch_check_all_chapters.py
```

**原因：**
- Writer 错误地返回了 Planner 的输出格式
- Writer 的 prompt 设置不当
- 模型质量不够好

**解决方案：**
- ❌ 无法自动修复，必须重新生成
- 检查 Writer 的 system prompt
- 考虑使用更好的模型

---

### 问题3: 多章节质量不稳定

**诊断流程：**
```bash
# 1. 对比多个章节
python3 compare_chapters.py 1 2 3 4 5

# 2. 查看统计分布
python3 batch_check_all_chapters.py

# 3. 分析具体章节
python3 diagnose_3agent.py 2  # 分析有问题的章节
```

**常见模式：**
- Writer 格式分布不一致 → Prompt 不够明确
- 迭代次数差异大 → Reviewer 标准不稳定
- 评分差异大 → 模型输出质量波动

---

### 问题4: 字数过少

**诊断流程：**
```bash
# 1. 检查是否普遍问题
python3 batch_check_all_chapters.py

# 2. 查看生成过程
python3 diagnose_3agent.py

# 3. 检查是否被截断
python3 analyze_writer_output.py
```

**可能原因：**
- 生成过程被中断
- 模型 token 限制
- Writer prompt 中的字数要求不明确

---

## 🔧 批量修复工作流

### 完整修复流程

```bash
# Step 1: 全面检查
python3 batch_check_all_chapters.py > chapter_report.txt

# Step 2: 预览修复
python3 fix_broken_chapters.py --dry-run

# Step 3: 执行自动修复
python3 fix_broken_chapters.py

# Step 4: 处理无法自动修复的章节
# 对于 Planner 格式或字数过少的章节，需要：
#   - 删除章节
#   - 重新生成

# Step 5: 验证修复结果
python3 batch_check_all_chapters.py
python3 compare_chapters.py 1 2 3 4 5
```

---

## 📊 输出示例

### batch_check_all_chapters.py 输出

```
================================================================================
🔍 批量检查所有章节（共 5 章）
================================================================================

📊 检查统计
--------------------------------------------------------------------------------
总章节数:        5
有问题的章节:    2
  - 纯JSON格式:   1
  - Planner格式:  1
  - Markdown标记: 0
  - 字数过少:     0
正常章节:        3

================================================================================
🚨 问题章节详情
================================================================================

第 2 章 - 我的小说
  ID: 2
  创建时间: 2024-01-15 10:30:00
  字数: 2345
  ❌ 严重问题:
     • 纯JSON格式

第 3 章 - 我的小说
  ID: 3
  创建时间: 2024-01-15 11:00:00
  字数: 1567
  ❌ 严重问题:
     • 包含Planner格式 (analysis:, plan:)
```

### compare_chapters.py 输出

```
====================================================================================================
章节   字数     迭代   评分   耗时(s)    Writer格式                问题
====================================================================================================
✅ 第1   2345     2      8.5    45.2       dict_with_full_content    ✅
❌ 第2   2134     3      7.0    67.8       dict_without_full_content 纯JSON格式
❌ 第3   1567     4      6.5    89.1       string                    Planner格式
✅ 第4   2456     2      8.0    43.5       dict_with_full_content    ✅
====================================================================================================

📈 统计分析
--------------------------------------------------------------------------------
总章节数:      4
有问题章节:    2 (50.0%)
正常章节:      2 (50.0%)

平均迭代次数:  2.8
平均评分:      7.5
平均耗时:      61.4 秒

Writer 格式分布:
  dict_with_full_content: 2 (50.0%)
  dict_without_full_content: 1 (25.0%)
  string: 1 (25.0%)
```

---

## 💡 最佳实践

### 1. 生成新章节后立即检查

```bash
# 生成章节后
python3 preview_chapters.py 1
```

### 2. 发现问题时深度诊断

```bash
# 详细诊断
python3 diagnose_3agent.py

# 查看 Writer 输出
python3 analyze_writer_output.py
```

### 3. 定期批量检查

```bash
# 每周检查一次
python3 batch_check_all_chapters.py
python3 compare_chapters.py 1 2 3 4 5
```

### 4. 自动化修复

```bash
# 先预览
python3 fix_broken_chapters.py --dry-run

# 再执行
python3 fix_broken_chapters.py
```

---

## 🎯 工具选择指南

| 需求 | 推荐工具 | 原因 |
|------|---------|------|
| 快速查看最近章节 | `preview_chapters.py` | 最快速，信息精简 |
| 深度分析单章 | `diagnose_3agent.py` | 最详细，包含完整历史 |
| 找出 Writer 问题 | `analyze_writer_output.py` | 直接查看原始输出 |
| 检查所有章节 | `batch_check_all_chapters.py` | 全局视角，统计完整 |
| 对比章节质量 | `compare_chapters.py` | 发现规律和模式 |
| 自动修复 | `fix_broken_chapters.py` | 一键修复常见问题 |
| 手动提取内容 | `extract_full_content.py` | 交互式，更安全 |

---

## 🚨 注意事项

1. **备份数据库**：修复前建议备份数据库
   ```bash
   cp backend/storage/arboris.db backend/storage/arboris.db.backup
   ```

2. **先预览再修复**：使用 `--dry-run` 查看修复效果

3. **无法自动修复的问题**：
   - Planner 格式 → 必须重新生成
   - 字数过少 → 建议重新生成

4. **数据库路径**：所有工具都支持自动检测和手动指定

---

## 📚 相关文档

- [3Agent 架构说明](docs/3agent.md)
- [Gemini RAG 配置指南](docs/gemini-rag.md)
- [Writer Agent Prompt](backend/app/prompts/writer.py)

---

## 🔄 更新日志

- **2024-01-15**: 创建初始版本
  - 添加 9 个诊断工具
  - 支持自动修复 JSON 格式问题
  - 完整的批量检查和对比功能
