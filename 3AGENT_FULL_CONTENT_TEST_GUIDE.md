# 3Agent Full Content 保存问题 - 测试指南

## 📋 问题概述

3Agent模式在生成章节时，有时会将**Planner Agent的分析结果**（包含`analysis`、`plan`等字段）错误地保存为章节正文，而不是Writer Agent生成的实际小说内容。

## 🎯 测试目标

通过多层次测试定位问题：
1. **确认问题存在** - 数据库中是否有错误数据
2. **定位问题环节** - 数据流在哪个环节出错
3. **追踪根本原因** - Writer返回错了还是保存用错了变量
4. **验证修复效果** - 确保修复后不再出现问题

## 🛠️ 测试工具套件

### 1. 快速检查工具（推荐首选）

**文件**: `quick_check_full_content.py`

**用途**: 快速检查特定章节或所有章节是否存在Planner格式问题

**使用方法**:
```bash
# 检查最新章节
python3 quick_check_full_content.py

# 检查第5章
python3 quick_check_full_content.py 5

# 检查所有章节
python3 quick_check_full_content.py --all

# 生成总结报告
python3 quick_check_full_content.py --summary
```

**输出示例**:
```
✅ 第 1 章 - 正常
   时间: 2025-11-14 10:30:00
   长度: 3245 字符
   Metadata: 迭代2次, 评分88

❌ 第 2 章 - 问题
   时间: 2025-11-14 11:00:00
   长度: 856 字符
   ⚠️  检测到 Planner 格式！
   关键词: analysis, plan, queries_summary
```

### 2. 综合测试工具

**文件**: `test_3agent_full_content_save.py`

**用途**: 多层次系统测试，包括数据库检查、格式检测、数据流追踪等

**使用方法**:
```bash
# 运行所有测试
python3 test_3agent_full_content_save.py --all

# 只测试数据库
python3 test_3agent_full_content_save.py --db

# 只测试格式检测逻辑
python3 test_3agent_full_content_save.py --detection

# 深入分析数据流（最重要！）
python3 test_3agent_full_content_save.py --flow --chapter 5

# 测试边界情况
python3 test_3agent_full_content_save.py --boundary

# 显示实时测试指南
python3 test_3agent_full_content_save.py --live
```

**测试层级**:
- **数据库层**: 检查实际保存的数据质量
- **格式检测层**: 验证Planner格式检测逻辑是否正确
- **数据流层**: 追踪从生成到保存的完整数据流（**最关键**）
- **边界测试**: 测试各种异常输入情况

### 3. 生成流程查看工具

**文件**: `show_latest_generation_flow.py`

**用途**: 查看完整的3Agent对话历史，了解每一步的输入输出

**使用方法**:
```bash
# 查看最新章节的生成流程
python3 show_latest_generation_flow.py

# 查看特定章节的生成流程
python3 show_latest_generation_flow.py <数据库路径> <章节号>
```

**关键信息**:
- Planner的分析和规划内容
- Writer每次迭代的输出
- Reviewer的审核反馈
- 最终保存的内容与Writer输出的对比

### 4. 调试日志插桩工具

**文件**: `add_3agent_debug_logging.py`

**用途**: 在代码关键位置自动添加调试日志，实时追踪数据流

**使用方法**:
```bash
# 预览要添加的日志位置
python3 add_3agent_debug_logging.py --preview

# 实际添加调试日志
python3 add_3agent_debug_logging.py --apply

# 移除调试日志
python3 add_3agent_debug_logging.py --remove
```

**工作流程**:
1. 添加日志: `--apply`
2. 重启后端服务
3. 生成一个测试章节
4. 查看日志: `tail -f backend/storage/logs/app.log | grep '3AGENT_DEBUG'`
5. 测试完成后移除: `--remove`

### 5. 已有诊断工具

**文件**: `diagnose_3agent.py`

**用途**: 诊断3Agent生成问题，检查Writer/Planner/Reviewer工作情况

**使用方法**:
```bash
# 诊断最新章节
python3 diagnose_3agent.py

# 诊断第1章
python3 diagnose_3agent.py /path/to/db 1
```

## 📊 测试流程（推荐步骤）

### 第一步：快速扫描
```bash
# 快速检查是否存在问题
python3 quick_check_full_content.py --summary
```

如果发现问题章节，记下章节号。

### 第二步：深入分析问题章节
```bash
# 假设第5章有问题
python3 test_3agent_full_content_save.py --flow --chapter 5
```

这会输出：
- Planner的输出内容
- Writer各次迭代的输出
- **关键对比**: Writer的full_content是否已经是Planner格式
- 最终保存的content与Writer输出的对比

### 第三步：查看完整对话历史
```bash
python3 show_latest_generation_flow.py
```

查看每一步Agent的详细输入输出。

### 第四步：如果还需要更多信息，添加实时日志
```bash
# 添加调试日志
python3 add_3agent_debug_logging.py --apply

# 重启后端
cd backend
# ... 重启命令 ...

# 生成一个测试章节
# 在前端操作...

# 查看实时日志
tail -f backend/storage/logs/app.log | grep '3AGENT_DEBUG'

# 测试完成后移除日志
python3 add_3agent_debug_logging.py --remove
```

## 🔍 问题定位判断树

```
问题：章节内容是Planner格式

│
├─ 查看数据流测试结果
│
├─ Writer的full_content已经是Planner格式？
│  │
│  ├─ 是 → 根因：Writer Agent错误返回
│  │     │
│  │     ├─ 检查：Writer的prompt是否清晰
│  │     ├─ 检查：Writer的上下文是否被Planner输出污染
│  │     └─ 解决：优化Writer prompt，或改进上下文构建
│  │
│  └─ 否 → 根因：保存过程中变量使用错误
│        │
│        ├─ 检查：auto_generator_service.py变量传递
│        ├─ 检查：是否绕过了检测逻辑
│        └─ 解决：修正变量传递，确保检测逻辑执行
│
└─ metadata.conversation_history缺失？
   │
   └─ 是 → 无法追踪，需要添加实时日志重新生成
```

## 📈 检测逻辑验证

运行格式检测测试：
```bash
python3 test_3agent_full_content_save.py --detection
```

应该通过所有测试用例：
- ✅ 正常小说内容不被误判
- ✅ JSON格式的Planner输出被正确检测
- ✅ 文本格式的Planner输出被正确检测
- ✅ 只有1个关键词不触发
- ✅ 1000字外的关键词不触发

## 🎯 预期测试结果

### 正常情况（无问题）
```
✅ 所有章节内容格式正常
✅ Metadata包含完整的conversation_history
✅ Writer的full_content都是正常小说文本
✅ 最终保存的content与Writer输出一致
```

### 问题情况（需修复）
```
❌ 发现章节content是Planner格式
   └─ 包含字段: analysis, plan, queries_summary

数据流分析：
   Writer返回: ✅ 正常格式
   最终保存: ❌ Planner格式
   
根因：保存过程中使用了错误的变量
```

## 🔧 已实现的修复

根据文档`3AGENT_CONTENT_SAVING_BUG_FIX.md`，已经实现了以下修复：

1. **ai_orchestrator_helper.py**:
   - 在非JSON响应处理中添加Planner格式检测
   - 检测范围扩大到前1000字
   - 两轮检测机制（第一轮重试，第二轮抛异常）

2. **auto_generator_service.py**:
   - 保存前二次检测
   - 发现Planner格式立即阻止保存

这些测试工具可以验证修复是否生效。

## 📝 测试报告模板

使用测试工具后，可以生成以下格式的报告：

```markdown
# 3Agent Full Content 测试报告

## 测试时间
2025-11-14 15:30:00

## 测试范围
- 总章节数: 10
- 测试工具: quick_check_full_content.py, test_3agent_full_content_save.py

## 测试结果

### 数据库检查
- 正常章节: 8 (80%)
- 问题章节: 2 (20%)
  - 第3章: Planner格式 (analysis, plan, queries_summary)
  - 第7章: Planner格式 (analysis, plan)

### 数据流分析（第3章）
- Planner输出: ✅ 正常
- Writer第1次: ❌ 返回了Planner格式
- Writer第2次: ✅ 正常
- 最终保存: ❌ 使用了第1次的错误输出

### 根本原因
Writer Agent在第1次迭代时错误地返回了Planner的内容，
虽然第2次正常，但保存时使用了第1次的结果。

### 建议
1. 修复Writer prompt，避免返回Planner格式
2. 保存前检测逻辑需要覆盖所有迭代
3. 重新生成问题章节
```

## 🚀 快速开始

如果你是第一次使用，推荐按以下顺序：

```bash
# 1. 快速扫描，看看有没有问题
python3 quick_check_full_content.py --summary

# 2. 如果发现问题，深入分析
python3 test_3agent_full_content_save.py --flow --chapter <问题章节号>

# 3. 查看完整生成流程
python3 show_latest_generation_flow.py

# 4. 运行完整测试套件
python3 test_3agent_full_content_save.py --all
```

## 💡 提示

1. **优先使用快速检查工具** - 最直观快速
2. **数据流测试最关键** - 能定位根因
3. **实时日志是终极武器** - 如果前面都不够用
4. **测试完要清理** - 记得移除调试日志
5. **定期运行总结报告** - 监控数据质量趋势

## 📞 需要帮助？

如果测试结果不明确或需要进一步分析，可以：
1. 查看已有文档: `3AGENT_CONTENT_SAVING_BUG_FIX.md`
2. 查看模拟脚本: `simulate_3agent_flow.py`
3. 查看诊断工具: `diagnose_3agent.py`

---

**最后更新**: 2025-11-14
**工具版本**: 1.0
