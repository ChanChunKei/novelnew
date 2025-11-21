# Scripts Directory

本目录包含项目的所有辅助脚本，按功能分类组织。

## 目录结构

```
scripts/
├── diagnostics/    # 诊断工具 - 用于排查问题
├── testing/        # 测试工具 - 用于验证功能
├── fixes/          # 修复工具 - 用于修复数据问题
├── utilities/      # 工具脚本 - 各种实用工具
└── deploy/         # 部署脚本 - 部署相关
```

## 使用说明

所有脚本需要在项目根目录运行：

```bash
cd /path/to/novelnew
python scripts/diagnostics/diagnose_3agent.py
```

---

## diagnostics/ - 诊断工具

### 3Agent模式诊断

| 脚本 | 用途 | 示例 |
|------|------|------|
| `diagnose_3agent.py` | 综合诊断3Agent生成问题 | `python scripts/diagnostics/diagnose_3agent.py` |
| `diagnose_planner_issue.py` | 诊断Planner内容被错误保存 | `python scripts/diagnostics/diagnose_planner_issue.py` |
| `diagnose_saved_content.py` | 检查保存的内容格式 | `python scripts/diagnostics/diagnose_saved_content.py` |
| `diagnose_writer_output.py` | 诊断Writer输出问题 | `python scripts/diagnostics/diagnose_writer_output.py` |

### 系统状态检查

| 脚本 | 用途 | 示例 |
|------|------|------|
| `check_config.py` | 检查配置是否正确 | `python scripts/diagnostics/check_config.py` |
| `check_db_status.py` | 检查数据库状态 | `python scripts/diagnostics/check_db_status.py` |
| `check_gemini_status.py` | 检查Gemini API状态 | `python scripts/diagnostics/check_gemini_status.py` |
| `full_diagnostic.py` | 完整系统诊断 | `python scripts/diagnostics/full_diagnostic.py` |

### 章节内容检查

| 脚本 | 用途 | 示例 |
|------|------|------|
| `batch_check_all_chapters.py` | 批量检查所有章节 | `python scripts/diagnostics/batch_check_all_chapters.py` |
| `quick_check_full_content.py` | 快速检查章节完整内容 | `python scripts/diagnostics/quick_check_full_content.py` |
| `preview_chapters.py` | 预览章节内容 | `python scripts/diagnostics/preview_chapters.py` |
| `show_latest_generation_flow.py` | 查看最新生成流程 | `python scripts/diagnostics/show_latest_generation_flow.py` |

### 任务检查

| 脚本 | 用途 | 示例 |
|------|------|------|
| `check_invalid_tasks.py` | 检查无效任务 | `python scripts/diagnostics/check_invalid_tasks.py` |
| `check_task_performance.py` | 检查任务性能 | `python scripts/diagnostics/check_task_performance.py` |

---

## testing/ - 测试工具

### 3Agent模式测试

| 脚本 | 用途 | 示例 |
|------|------|------|
| `test_3agent_full_content_save.py` | 综合测试full_content保存 | `python scripts/testing/test_3agent_full_content_save.py --all` |
| `test_3agent_tools.py` | 测试3Agent工具调用 | `python scripts/testing/test_3agent_tools.py` |
| `test_planner_detection.py` | 测试Planner格式检测 | `python scripts/testing/test_planner_detection.py` |
| `test_fix_validation.py` | 验证修复效果 | `python scripts/testing/test_fix_validation.py` |
| `simulate_3agent_flow.py` | 模拟3Agent流程 | `python scripts/testing/simulate_3agent_flow.py` |

### API测试

| 脚本 | 用途 | 示例 |
|------|------|------|
| `test_gemini_key.py` | 测试Gemini API密钥 | `python scripts/testing/test_gemini_key.py` |

### 验证工具

| 脚本 | 用途 | 示例 |
|------|------|------|
| `verify_fix.py` | 验证修复是否生效 | `python scripts/testing/verify_fix.py` |
| `prove_root_cause.py` | 证明问题根因 | `python scripts/testing/prove_root_cause.py` |

---

## fixes/ - 修复工具

### 章节修复

| 脚本 | 用途 | 示例 |
|------|------|------|
| `fix_all_planner_chapters.py` | 修复所有Planner格式章节 | `python scripts/fixes/fix_all_planner_chapters.py` |
| `fix_broken_chapters.py` | 修复损坏的章节 | `python scripts/fixes/fix_broken_chapters.py` |
| `fix_planner_content.py` | 修复Planner内容 | `python scripts/fixes/fix_planner_content.py` |
| `extract_full_content.py` | 提取完整内容 | `python scripts/fixes/extract_full_content.py` |

### 数据库修复

| 脚本 | 用途 | 示例 |
|------|------|------|
| `fix_migration.py` | 修复数据库迁移问题 | `python scripts/fixes/fix_migration.py` |
| `cleanup_duplicate_tasks.py` | 清理重复任务 | `python scripts/fixes/cleanup_duplicate_tasks.py` |

---

## utilities/ - 工具脚本

| 脚本 | 用途 | 示例 |
|------|------|------|
| `add_3agent_debug_logging.py` | 添加3Agent调试日志 | `python scripts/utilities/add_3agent_debug_logging.py --preview` |
| `analyze_writer_output.py` | 分析Writer输出 | `python scripts/utilities/analyze_writer_output.py` |
| `insert_config.py` | 插入配置数据 | `python scripts/utilities/insert_config.py` |
| `monitor_gemini_rag.py` | 监控Gemini RAG | `python scripts/utilities/monitor_gemini_rag.py` |
| `apply_scheduled_start_migration.py` | 应用定时任务迁移 | `python scripts/utilities/apply_scheduled_start_migration.py` |

---

## deploy/ - 部署脚本

| 脚本 | 用途 | 示例 |
|------|------|------|
| `deploy.sh` | 标准部署脚本 | `./scripts/deploy/deploy.sh` |
| `SERVER_DEPLOY.sh` | 服务器一键部署 | `./scripts/deploy/SERVER_DEPLOY.sh` |
| `server_deployment_guide.sh` | 部署指南脚本 | `./scripts/deploy/server_deployment_guide.sh` |
| `push_to_github.sh` | 推送到GitHub | `./scripts/deploy/push_to_github.sh` |
| `filter_3agent_logs.sh` | 过滤3Agent日志 | `./scripts/deploy/filter_3agent_logs.sh` |
| `demo_3agent_testing.sh` | 3Agent测试演示 | `./scripts/deploy/demo_3agent_testing.sh` |
| `deploy_fix.sh` | 部署修复脚本 | `./scripts/deploy/deploy_fix.sh` |

---

## 常用工作流

### 排查3Agent生成问题

```bash
# 1. 先运行综合诊断
python scripts/diagnostics/diagnose_3agent.py

# 2. 检查保存的内容
python scripts/diagnostics/diagnose_saved_content.py

# 3. 测试数据流
python scripts/testing/test_3agent_full_content_save.py --flow
```

### 修复问题章节

```bash
# 1. 检查有问题的章节
python scripts/diagnostics/batch_check_all_chapters.py

# 2. 修复Planner格式问题
python scripts/fixes/fix_all_planner_chapters.py
```

### 部署前检查

```bash
# 1. 检查配置
python scripts/diagnostics/check_config.py

# 2. 检查数据库
python scripts/diagnostics/check_db_status.py

# 3. 部署
./scripts/deploy/SERVER_DEPLOY.sh
```

---

## 注意事项

1. 所有脚本需要在**项目根目录**运行
2. 大多数脚本需要**激活虚拟环境**：`source backend/venv/bin/activate`
3. 部分脚本需要**数据库连接**，确保数据库可访问
4. Shell脚本需要**执行权限**：`chmod +x scripts/deploy/*.sh`

---

**最后更新**: 2025-11-21
