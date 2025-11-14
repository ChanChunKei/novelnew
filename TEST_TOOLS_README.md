# 3Agent Full Content 测试工具包

## 🎯 快速开始

```bash
# 1. 快速检查是否有问题
python3 quick_check_full_content.py --summary

# 2. 如果发现问题，深入分析（假设第5章有问题）
python3 test_3agent_full_content_save.py --flow --chapter 5

# 3. 查看完整生成过程
python3 show_latest_generation_flow.py

# 4. 运行演示（查看所有工具用法）
./demo_3agent_testing.sh
```

## 📦 工具清单

| 工具 | 用途 | 优先级 |
|------|------|--------|
| `quick_check_full_content.py` | 快速检查章节质量 | ⭐⭐⭐⭐⭐ |
| `test_3agent_full_content_save.py` | 综合测试套件 | ⭐⭐⭐⭐⭐ |
| `show_latest_generation_flow.py` | 查看对话历史 | ⭐⭐⭐⭐ |
| `add_3agent_debug_logging.py` | 添加调试日志 | ⭐⭐⭐ |
| `diagnose_3agent.py` | 诊断生成问题 | ⭐⭐⭐ |
| `demo_3agent_testing.sh` | 演示脚本 | ⭐⭐ |

## 🔍 核心功能

### 1. 问题检测
- ✅ 检测Planner格式内容（JSON/文本）
- ✅ 扫描所有章节或特定章节
- ✅ 生成问题总结报告

### 2. 数据流追踪
- ✅ 查看Planner输出
- ✅ 查看Writer各次迭代
- ✅ 查看Reviewer反馈
- ✅ 对比Writer输出与最终保存的内容

### 3. 实时监控
- ✅ 自动添加调试日志
- ✅ 追踪关键数据点
- ✅ 易于清理（一键移除）

### 4. 测试验证
- ✅ 格式检测逻辑测试
- ✅ 边界情况测试
- ✅ 数据库完整性检查

## 📋 使用场景

### 场景1：发现新问题
```bash
# 用户报告某章节内容异常
python3 quick_check_full_content.py 5

# 输出会告诉你：
# - 是否是Planner格式
# - 包含哪些关键词
# - metadata信息
```

### 场景2：调查根因
```bash
# 深入分析数据流
python3 test_3agent_full_content_save.py --flow --chapter 5

# 会告诉你：
# - Writer输出的是什么
# - 最终保存的是什么
# - 在哪个环节出错
```

### 场景3：定期检查
```bash
# 生成质量报告
python3 quick_check_full_content.py --summary

# 输出统计：
# - 总章节数
# - 正常/问题章节比例
# - 平均评分和迭代次数
```

### 场景4：开发调试
```bash
# 添加实时日志
python3 add_3agent_debug_logging.py --apply

# 重启后端，生成测试章节

# 查看日志
tail -f backend/storage/logs/app.log | grep '3AGENT_DEBUG'

# 测试完成后清理
python3 add_3agent_debug_logging.py --remove
```

## 🎓 测试教程

### 基础教程（5分钟）
```bash
# 1. 快速扫描
python3 quick_check_full_content.py --all

# 2. 检查最新章节
python3 quick_check_full_content.py

# 3. 查看总结
python3 quick_check_full_content.py --summary
```

### 进阶教程（15分钟）
```bash
# 1. 运行完整测试
python3 test_3agent_full_content_save.py --all

# 2. 针对性测试
python3 test_3agent_full_content_save.py --detection  # 格式检测
python3 test_3agent_full_content_save.py --boundary   # 边界测试
python3 test_3agent_full_content_save.py --flow       # 数据流

# 3. 查看生成历史
python3 show_latest_generation_flow.py
```

### 高级教程（30分钟）
```bash
# 1. 运行演示脚本（自动模式）
./demo_3agent_testing.sh --auto

# 2. 添加调试日志
python3 add_3agent_debug_logging.py --preview  # 预览
python3 add_3agent_debug_logging.py --apply    # 应用

# 3. 生成测试章节，观察日志

# 4. 清理
python3 add_3agent_debug_logging.py --remove
```

## 🔧 常见问题

### Q1: 工具显示"未找到数据库"
**A**: 确保在项目根目录运行，或数据库路径为 `backend/storage/arboris.db`

### Q2: 如何测试特定章节？
**A**: 使用 `--chapter` 参数
```bash
python3 test_3agent_full_content_save.py --flow --chapter 5
```

### Q3: 调试日志会影响性能吗？
**A**: 会略微增加日志量，建议只在调试时使用，完成后及时移除

### Q4: 如何解读数据流测试结果？
**A**: 关注两个关键点：
1. Writer的full_content是否已经是Planner格式
2. 最终保存的content与Writer输出是否一致

### Q5: 发现问题后怎么办？
**A**: 
1. 使用数据流测试定位根因
2. 如果是Writer问题，检查prompt和上下文
3. 如果是保存问题，检查变量传递
4. 重新生成问题章节

## 📊 测试输出示例

### 正常情况
```
✅ 第 1 章 - 正常
   时间: 2025-11-14 10:30:00
   长度: 3245 字符
   Metadata: 迭代2次, 评分88

Writer输出: ✅ 正常格式
最终保存: ✅ 正常格式
结论: ✅ 没有发现问题
```

### 问题情况
```
❌ 第 2 章 - 问题
   时间: 2025-11-14 11:00:00
   长度: 856 字符
   ⚠️  检测到 Planner 格式！
   关键词: analysis, plan, queries_summary

Writer输出: ❌ Planner格式
最终保存: ❌ Planner格式
根因: Writer Agent错误地返回了Planner的内容
```

## 🎯 测试检查清单

使用此清单确保完整测试：

- [ ] 运行快速检查 `quick_check_full_content.py --summary`
- [ ] 检查格式检测 `test_3agent_full_content_save.py --detection`
- [ ] 测试边界情况 `test_3agent_full_content_save.py --boundary`
- [ ] 检查数据库质量 `test_3agent_full_content_save.py --db`
- [ ] 如有问题，运行数据流分析 `--flow --chapter N`
- [ ] 查看完整对话历史 `show_latest_generation_flow.py`
- [ ] 如需更多信息，添加实时日志
- [ ] 测试完成后清理调试日志

## 📚 相关文档

- **详细指南**: `3AGENT_FULL_CONTENT_TEST_GUIDE.md`
- **问题修复**: `3AGENT_CONTENT_SAVING_BUG_FIX.md`
- **Metadata修复**: `3AGENT_METADATA_SAVE_FIX.md`
- **3Agent综述**: `3AGENT_REVIEW_REPORT.md`

## 🚀 贡献

如果需要添加新的测试功能：

1. 在 `test_3agent_full_content_save.py` 中添加新的测试类
2. 在 `3AGENT_FULL_CONTENT_TEST_GUIDE.md` 中记录用法
3. 更新本 README

## 📞 支持

遇到问题？
1. 查看详细指南 `3AGENT_FULL_CONTENT_TEST_GUIDE.md`
2. 运行演示脚本 `./demo_3agent_testing.sh`
3. 查看已有诊断工具输出

---

**最后更新**: 2025-11-14  
**工具版本**: 1.0  
**维护者**: AI Assistant
