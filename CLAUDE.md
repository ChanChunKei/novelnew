# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 开发命令

### 后端开发 (FastAPI + Python)
```bash
cd backend

# 开发环境启动
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动异步分析处理器（可选）
python -m app.background_processor

# 数据库管理
python run_migration.py           # 执行数据库迁移
python reload_prompts.py          # 重新加载提示词到数据库

# 测试相关
pytest                            # 运行所有测试
python test_3agent_direct.py      # 测试3Agent模式
python test_writer_output.py      # 测试Writer输出
python backend/tests/test_async_analysis.py  # 测试异步分析
```

### 前端开发 (Vue 3 + TypeScript)
```bash
cd frontend

# 开发
npm install
npm run dev                       # 开发服务器 (http://localhost:5173)

# 构建和部署
npm run build                     # 生产构建
npm run preview                   # 预览生产构建
npm run type-check                # TypeScript类型检查
npm run format                    # 代码格式化 (Prettier)
```

### 诊断和调试工具
```bash
# 系统状态检查
python check_config.py            # 检查配置
python check_db_status.py         # 检查数据库状态
python check_gemini_status.py     # 检查Gemini API状态
python full_diagnostic.py         # 完整系统诊断

# 3Agent模式调试
python diagnose_3agent.py         # 诊断3Agent问题
python test_3agent_full_content_save.py  # 测试内容保存
python simulate_3agent_flow.py    # 模拟3Agent流程

# 章节内容相关
python diagnose_chapter_issue.py  # 章节问题诊断
python debug_chapter_content.py   # 调试章节内容
python preview_chapters.py        # 预览章节
```

## 系统架构概览

### 核心服务架构
- **AI路由系统** (`ai_orchestrator_helper.py`): 智能分配不同AI任务到最合适的模型（Claude、Gemini、DeepSeek等）
- **3Agent协作模式**: Planner → Writer → Reviewer 三步式AI协作生成高质量章节内容
- **双模式自动生成器**: 基础模式（快速生成）+ 增强模式（异步深度分析）
- **分卷管理系统**: 支持多分卷创作，每个分卷独立的人物关系和世界观快照

### 数据流向
1. **蓝图生成**: 用户创意 → AI路由器选择Claude → 生成完整小说蓝图
2. **章节创作**: 大纲 + 上下文快照 → 3Agent模式 → 多版本章节内容
3. **异步增强**: 章节内容 → 后台分析器 → 角色追踪/世界观扩展/情节分析
4. **自动上传**: 完成章节 → 番茄小说发布系统 → 自动匹配分卷上传

### 关键组件说明

#### AI编排系统
- `ai_orchestrator_helper.py`: AI任务路由核心，根据任务类型选择最优模型
- `llm_service.py`: 统一的LLM调用接口，支持多个AI提供商
- `hybrid_agent_service.py`: 3Agent协作模式实现

#### 内容生成管道
- `auto_generator_service.py`: 自动生成器主服务，管理生成队列和状态
- `async_analysis_processor.py`: 异步分析处理器，后台执行增强分析
- `chapter_context_service.py`: 章节上下文管理，维护人物关系和世界观

#### 分卷和版本管理
- `volume_split_service.py`: 分卷切分和管理逻辑
- 分卷快照系统: 每个分卷独立的人物、关系、世界观状态快照
- 版本选择: 支持章节的多版本生成和用户选择

#### 番茄小说集成
- `fanqie_publisher_service.py`: 番茄小说自动上传服务
- `fanqie_browser_manager.py`: 浏览器自动化管理（Playwright）
- 状态机驱动的复杂上传流程处理

### 数据库模型关系
- **Novel**: 小说项目主体，包含基本信息和AI生成的蓝图数据
- **Chapter**: 章节内容，支持多版本存储，关联分卷信息
- **VolumeSnapshot**: 分卷快照，记录每个分卷的人物关系和世界观演变
- **AsyncTask**: 异步任务队列，管理后台分析任务的状态和结果

### 提示词系统
- `backend/prompts/`: 所有AI提示词模板，包括3Agent模式的专门提示词
- `reload_prompts.py`: 提示词热重载，支持动态更新不重启服务
- 支持多语言和任务特化的提示词体系

### 前端架构要点
- **组件化设计**: 基于Naive UI的组件库，工作台模式的写作界面
- **状态管理**: Pinia管理全局状态，包括小说数据、用户认证、AI生成状态
- **工作台模式**: `WritingDesk.vue`是核心写作界面，支持章节编辑、版本对比、实时生成
- **实时更新**: WebSocket连接支持AI生成过程的实时状态更新

### 配置和部署
- 环境变量配置支持多种AI提供商和数据库类型
- Docker化部署支持，包含前后端和数据库的完整容器编排
- 支持SQLite（开发）和MySQL（生产）双数据库模式
- Systemd服务文件用于生产环境的进程管理

## 重要说明

### AI模型使用策略
- **蓝图生成**: 使用Claude Sonnet 3.5（创意和逻辑推理能力强）
- **章节创作**: 使用SiliconFlow DeepSeek-V3（性价比高，适合大量文本生成）
- **摘要提取**: 使用Google Gemini Flash（快速处理，成本低）
- **增强分析**: 使用Claude Sonnet 3.5（深度分析能力）

### 3Agent模式工作流
1. **Planner**: 分析大纲和上下文，制定章节写作计划
2. **Writer**: 根据计划生成章节内容，可生成多个版本
3. **Reviewer**: 评估生成质量，提供改进建议

### 测试策略
- 单元测试：覆盖核心业务逻辑和数据访问层
- 集成测试：验证AI模式和外部服务集成
- 端到端测试：完整的内容生成和上传流程验证
- 性能测试：大量并发请求和长时间运行稳定性