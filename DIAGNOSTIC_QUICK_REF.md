# 诊断工具快速参考

## 🚀 快速开始

```bash
# 一键完整诊断（推荐首次运行）
python3 full_diagnostic.py
```

---

## 📋 常用命令速查

### 快速检查

```bash
# 查看最近3章
python3 preview_chapters.py

# 检查所有章节
python3 batch_check_all_chapters.py

# 完整诊断报告
python3 full_diagnostic.py
```

### 详细分析

```bash
# 诊断最新章节
python3 diagnose_3agent.py

# 分析 Writer 输出
python3 analyze_writer_output.py

# 对比多章质量
python3 compare_chapters.py 1 2 3
```

### 自动修复

```bash
# 预览修复（安全）
python3 fix_broken_chapters.py --dry-run

# 执行修复
python3 fix_broken_chapters.py

# 交互式提取内容
python3 extract_full_content.py
```

### 配置检查

```bash
# 查看 Gemini 状态
python3 check_gemini_status.py

# 查看配置
python3 check_config.py

# 更新配置
python3 insert_config.py
```

---

## 🔍 问题诊断速查表

| 问题症状 | 使用工具 | 命令 |
|---------|---------|------|
| 章节内容是 JSON | 自动修复 | `python3 fix_broken_chapters.py` |
| 章节包含 Planner 格式 | 分析原因 | `python3 analyze_writer_output.py` |
| 不确定哪些章节有问题 | 批量检查 | `python3 batch_check_all_chapters.py` |
| 想对比多章质量 | 对比工具 | `python3 compare_chapters.py 1 2 3` |
| 想看完整诊断 | 完整报告 | `python3 full_diagnostic.py` |

---

## 💊 问题类型和解决方案

### ✅ 可自动修复

- **纯 JSON 格式**: `python3 fix_broken_chapters.py`
- **Markdown 代码块**: `python3 fix_broken_chapters.py`

### ❌ 需要重新生成

- **Planner 格式**: 重新生成章节
- **字数过少**: 重新生成章节

### 🔍 需要深入分析

- **Writer 输出异常**: `python3 analyze_writer_output.py`
- **质量不稳定**: `python3 compare_chapters.py 1 2 3 4 5`

---

## 📊 所有工具列表

| 工具 | 功能 | 用途 |
|-----|------|------|
| `full_diagnostic.py` | 🔴 完整诊断 | 一键运行所有检查 |
| `preview_chapters.py` | 🟡 快速预览 | 查看最近章节 |
| `diagnose_3agent.py` | 🟡 详细诊断 | 深度分析单章 |
| `analyze_writer_output.py` | 🟡 分析输出 | 查看 Writer 原始输出 |
| `batch_check_all_chapters.py` | 🟢 批量检查 | 扫描所有章节 |
| `compare_chapters.py` | 🟢 对比质量 | 对比多个章节 |
| `fix_broken_chapters.py` | 🔵 自动修复 | 一键修复格式问题 |
| `extract_full_content.py` | 🔵 手动提取 | 交互式提取内容 |
| `check_gemini_status.py` | 🟣 配置检查 | Gemini RAG 状态 |
| `check_config.py` | 🟣 查看配置 | 系统配置 |
| `insert_config.py` | 🟣 更新配置 | 插入/更新配置 |
| `monitor_gemini_rag.py` | 🟣 实时监控 | 监控日志 |

---

## 🎯 典型工作流

### 场景1: 刚生成了新章节

```bash
# 1. 快速检查
python3 preview_chapters.py 1

# 2. 如果有问题，详细诊断
python3 diagnose_3agent.py
```

### 场景2: 多章节有问题

```bash
# 1. 批量检查
python3 batch_check_all_chapters.py

# 2. 对比分析
python3 compare_chapters.py 1 2 3 4 5

# 3. 尝试自动修复
python3 fix_broken_chapters.py --dry-run
python3 fix_broken_chapters.py
```

### 场景3: Writer 输出异常

```bash
# 1. 分析 Writer 输出
python3 analyze_writer_output.py

# 2. 对比正常与异常章节
python3 compare_chapters.py 1 2 3

# 3. 根据分析结果调整 prompt 或模型
```

### 场景4: 首次使用或定期检查

```bash
# 运行完整诊断
python3 full_diagnostic.py
```

---

## 🔧 命令参数说明

### 通用参数

所有工具都支持：
- 自动检测数据库路径
- 手动指定数据库: `工具.py /path/to/db.db`

### 特定参数

```bash
# preview_chapters.py
python3 preview_chapters.py [db_path] [数量]
python3 preview_chapters.py 5           # 最近5章
python3 preview_chapters.py /path/db 3  # 指定数据库，查看3章

# diagnose_3agent.py
python3 diagnose_3agent.py [db_path] [章节号]
python3 diagnose_3agent.py 1            # 诊断第1章
python3 diagnose_3agent.py /path/db 2   # 指定数据库，诊断第2章

# compare_chapters.py
python3 compare_chapters.py [db_path] [章节号1] [章节号2] ...
python3 compare_chapters.py 1 2 3       # 对比第1,2,3章
python3 compare_chapters.py /path/db 1 2 3

# fix_broken_chapters.py
python3 fix_broken_chapters.py [db_path] [章节ID1] [章节ID2] ... [--dry-run]
python3 fix_broken_chapters.py --dry-run       # 预览模式
python3 fix_broken_chapters.py                 # 修复所有
python3 fix_broken_chapters.py /path/db 1 2 3  # 修复指定ID

# extract_full_content.py
python3 extract_full_content.py [db_path] [章节ID]
python3 extract_full_content.py        # 交互式修复所有JSON章节
python3 extract_full_content.py /path/db 123  # 修复指定章节
```

---

## ⚠️ 重要提示

1. **备份数据库**: 修复前先备份
   ```bash
   cp backend/storage/arboris.db backend/storage/arboris.db.backup
   ```

2. **先预览后修复**: 使用 `--dry-run` 参数

3. **查看详细文档**: `cat DIAGNOSTIC_TOOLS.md`

---

## 📞 获取帮助

```bash
# 查看工具说明
python3 工具名.py --help

# 查看完整文档
cat DIAGNOSTIC_TOOLS.md

# 查看快速参考（本文档）
cat DIAGNOSTIC_QUICK_REF.md
```

---

## 📝 示例输出

### full_diagnostic.py 输出示例

```
================================================================================
🔍 3Agent 系统完整诊断报告
================================================================================

数据库: backend/storage/arboris.db
时间: 2024-01-15 14:30:00

================================================================================
📋 1. Gemini RAG 配置检查
================================================================================

配置状态:
  RAG Provider: gemini
  Gemini API Key: AIzaSyA5t2...kBQ ✅

✅ Gemini RAG 已正确配置

================================================================================
📋 2. 项目状态检查
================================================================================

找到 2 个项目：

📖 我的小说
   ID: 1, 状态: active, 章节数: 5
   Corpus: novel-project-1

📖 测试项目
   ID: 2, 状态: active, 章节数: 3
   Corpus: novel-project-2

================================================================================
📋 3. 章节格式批量检查
================================================================================

扫描 8 个章节...

📊 统计结果:
  总章节数:    8
  正常章节:    5 (62.5%)
  问题章节:    3 (37.5%)
    - JSON格式:   1
    - Planner:    2
    - Markdown:   0
    - 字数少:     0

  平均迭代:    2.5 次
  平均评分:    7.8
  平均字数:    2134

🚨 问题章节列表:
  • 第 2 章: 纯JSON
  • 第 3 章: Planner格式
  • 第 5 章: Planner格式

================================================================================
📋 5. 诊断建议
================================================================================

发现以下问题：

🟡 中 [格式] 1 章是纯JSON格式
   解决方案: 运行: python3 fix_broken_chapters.py

🔴 高 [格式] 2 章包含Planner格式
   解决方案: 需要重新生成这些章节，检查 Writer prompt

💡 下一步操作建议

1️⃣  修复可自动修复的问题:
   python3 fix_broken_chapters.py --dry-run  # 预览
   python3 fix_broken_chapters.py            # 执行

2️⃣  分析 Planner 格式问题:
   python3 analyze_writer_output.py
   # 查看 Writer 为什么返回 Planner 格式

3️⃣  对比正常与问题章节:
   python3 compare_chapters.py 1 2 3 4 5
   # 找出规律

4️⃣  查看详细文档:
   cat DIAGNOSTIC_TOOLS.md

================================================================================
✅ 诊断完成
================================================================================

💡 提示: 查看 DIAGNOSTIC_TOOLS.md 了解所有工具的详细用法
```

---

**最后更新**: 2024-01-15
