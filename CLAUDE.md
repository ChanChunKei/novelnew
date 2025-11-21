# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**Arboris Novel** 是一个基于AI的智能小说创作平台，支持：
- 🎨 AI自动生成小说蓝图、大纲和章节内容
- 🤖 多AI模型智能路由（Claude、Gemini、DeepSeek等）
- 📚 分卷管理和版本控制
- 🚀 番茄小说自动上传
- 🔄 3Agent协作模式（Planner → Writer → Reviewer）

**技术栈**:
- 后端: FastAPI + SQLAlchemy + Python 3.11+
- 前端: Vue 3 + TypeScript + Naive UI + Pinia
- 数据库: SQLite (开发) / MySQL (生产)
- AI: OpenAI, Anthropic Claude, Google Gemini, SiliconFlow

## 开发命令

### 后端开发 (FastAPI + Python)
```bash
cd backend

# 开发环境启动
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动异步分析处理器（可选，用于增强模式）
python -m app.background_processor

# 数据库管理
python run_migration.py           # 执行数据库迁移
python reload_prompts.py          # 重新加载提示词到数据库

# 测试相关
pytest                            # 运行所有测试
pytest backend/tests/            # 运行后端测试
python test_3agent_direct.py      # 测试3Agent模式
python test_writer_output.py      # 测试Writer输出
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

> **注意**: 所有脚本已整理到 `scripts/` 目录，详见 `scripts/README.md`

```bash
# 系统状态检查
python scripts/diagnostics/check_config.py            # 检查配置
python scripts/diagnostics/check_db_status.py         # 检查数据库状态
python scripts/diagnostics/check_gemini_status.py     # 检查Gemini API状态
python backend/check_user_config.py                   # 检查用户配置

# 3Agent模式调试
python scripts/diagnostics/diagnose_3agent.py         # 诊断3Agent问题
python scripts/diagnostics/diagnose_planner_issue.py  # 诊断Planner问题
python scripts/diagnostics/diagnose_saved_content.py  # 诊断保存内容
python scripts/testing/test_3agent_full_content_save.py  # 测试内容保存
python scripts/testing/test_3agent_tools.py           # 测试3Agent工具
python scripts/testing/test_planner_detection.py      # 测试Planner检测
python scripts/testing/test_fix_validation.py         # 测试修复验证
python scripts/utilities/add_3agent_debug_logging.py  # 添加3Agent调试日志

# 章节内容相关
python scripts/diagnostics/diagnose_chapter_issue.py  # 章节问题诊断
python scripts/diagnostics/diagnose_latest_chapter.py # 诊断最新章节
python scripts/diagnostics/debug_chapter_content.py   # 调试章节内容
python scripts/diagnostics/batch_check_all_chapters.py # 批量检查所有章节
python scripts/diagnostics/quick_check_full_content.py # 快速检查完整内容
python scripts/diagnostics/show_latest_generation_flow.py # 查看最新生成流程

# 任务和性能检查
python scripts/diagnostics/check_invalid_tasks.py     # 检查无效任务
python scripts/diagnostics/check_task_performance.py  # 检查任务性能

# API密钥测试
python scripts/testing/test_gemini_key.py             # 测试Gemini密钥
```

## 代码库结构

```
novelnew/
├── backend/                      # Python后端服务
│   ├── app/
│   │   ├── api/                 # API路由层
│   │   │   └── routers/         # 具体路由模块
│   │   │       ├── auth.py      # 用户认证
│   │   │       ├── novels.py    # 小说CRUD
│   │   │       ├── writer.py    # 章节生成
│   │   │       ├── auto_generator.py  # 自动生成器
│   │   │       ├── ai_routing.py      # AI路由配置
│   │   │       ├── volume_management.py # 分卷管理
│   │   │       ├── async_analysis.py  # 异步分析
│   │   │       ├── llm_config.py      # LLM配置
│   │   │       ├── updates.py         # 更新日志
│   │   │       └── admin.py           # 管理后台
│   │   ├── models/              # SQLAlchemy数据模型
│   │   │   ├── novel.py         # Novel, Chapter, VolumeSnapshot
│   │   │   ├── user.py          # User
│   │   │   ├── async_task.py    # AsyncTask
│   │   │   ├── auto_generator.py # AutoGeneratorTask
│   │   │   ├── ai_routing.py    # AIRoutingConfig
│   │   │   ├── llm_config.py    # LLMConfig
│   │   │   ├── prompt.py        # Prompt
│   │   │   ├── story_metrics.py # StoryMetrics
│   │   │   └── ...
│   │   ├── services/            # 业务逻辑层
│   │   │   ├── ai_orchestrator_helper.py  # AI任务路由核心
│   │   │   ├── llm_service.py             # 统一LLM调用接口
│   │   │   ├── hybrid_agent_service.py    # 3Agent协作模式
│   │   │   ├── auto_generator_service.py  # 自动生成器
│   │   │   ├── novel_service.py           # 小说业务逻辑
│   │   │   ├── chapter_context_service.py # 章节上下文管理
│   │   │   ├── volume_split_service.py    # 分卷管理
│   │   │   ├── fanqie_publisher_service.py # 番茄上传
│   │   │   ├── fanqie_browser_manager.py  # 浏览器自动化
│   │   │   ├── async_analysis_processor.py # 异步分析处理
│   │   │   ├── gemini_rag_service.py      # Gemini RAG
│   │   │   ├── vector_store_service.py    # 向量存储
│   │   │   ├── prompt_service.py          # 提示词管理
│   │   │   ├── auth_service.py            # 认证服务
│   │   │   ├── ai_denoising_service.py    # AI去噪服务
│   │   │   ├── super_analysis_service.py  # 超级分析服务
│   │   │   ├── task_scheduler_service.py  # 任务调度服务
│   │   │   ├── chapter_ingest_service.py  # 章节导入服务
│   │   │   ├── story_metrics_service.py   # 故事指标服务
│   │   │   ├── admin_setting_service.py   # 管理设置服务
│   │   │   ├── usage_service.py           # 使用统计服务
│   │   │   ├── user_service.py            # 用户服务
│   │   │   ├── update_log_service.py      # 更新日志服务
│   │   │   ├── config_service.py          # 配置服务
│   │   │   └── ai_orchestrator.py         # AI编排器
│   │   ├── repositories/        # 数据访问层
│   │   ├── schemas/             # Pydantic数据验证模型
│   │   ├── core/                # 核心配置
│   │   │   └── config.py        # 环境变量配置
│   │   ├── db/                  # 数据库配置
│   │   │   ├── session.py       # 数据库会话
│   │   │   └── init_db.py       # 数据库初始化
│   │   ├── utils/               # 工具函数
│   │   ├── tasks/               # 后台任务
│   │   ├── config/              # Agent配置
│   │   │   ├── agent_prompts.py # Agent提示词
│   │   │   └── agent_tools.py   # Agent工具
│   │   ├── main.py              # FastAPI应用入口
│   │   └── background_processor.py # 异步处理器入口
│   ├── prompts/                 # AI提示词模板（Markdown）
│   │   ├── concept.md           # 蓝图生成
│   │   ├── outline.md           # 大纲生成
│   │   ├── writing.md           # 章节写作
│   │   ├── extraction.md        # 摘要提取
│   │   ├── evaluation.md        # 内容评估
│   │   ├── screenwriting.md     # 剧本创作
│   │   ├── agent_planner.md     # 3Agent: Planner
│   │   ├── agent_writer.md      # 3Agent: Writer
│   │   ├── agent_reviewer.md    # 3Agent: Reviewer
│   │   ├── agent_summarizer.md  # 3Agent: Summarizer
│   │   ├── outline_agent_planner.md   # 大纲Planner
│   │   ├── outline_agent_writer.md    # 大纲Writer
│   │   └── outline_agent_reviewer.md  # 大纲Reviewer
│   ├── tests/                   # 测试文件
│   ├── requirements.txt         # Python依赖
│   ├── run_migration.py         # 数据库迁移
│   └── reload_prompts.py        # 提示词重载
├── frontend/                     # Vue前端应用
│   ├── src/
│   │   ├── components/          # Vue组件
│   │   │   ├── WritingDesk/     # 写作台组件
│   │   │   ├── AutoGenerator.vue # 自动生成器
│   │   │   ├── BlueprintDisplay.vue # 蓝图展示
│   │   │   ├── ChapterList.vue  # 章节列表
│   │   │   ├── LLMSettings.vue  # LLM配置
│   │   │   ├── FanqieUploader.vue # 番茄上传
│   │   │   ├── BatchTaskScheduler.vue # 批量任务调度
│   │   │   └── ...
│   │   ├── views/               # 页面视图
│   │   │   ├── WorkspaceEntry.vue # 工作台入口
│   │   │   ├── WritingDesk.vue    # 核心写作界面
│   │   │   ├── InspirationMode.vue # 灵感模式
│   │   │   ├── NovelWorkspace.vue # 小说工作区
│   │   │   ├── Login.vue          # 登录
│   │   │   ├── AdminView.vue      # 管理后台
│   │   │   └── ...
│   │   ├── stores/              # Pinia状态管理
│   │   ├── api/                 # API调用封装
│   │   ├── router/              # Vue Router配置
│   │   ├── utils/               # 工具函数
│   │   └── main.ts              # 应用入口
│   ├── package.json             # Node依赖
│   └── tsconfig.json            # TypeScript配置
├── docs/                        # 项目文档
│   ├── guides/                  # 功能指南
│   ├── reports/                 # 项目报告
│   ├── archives/                # 历史文档
│   ├── fanqie_upload_guide.md   # 番茄上传指南
│   ├── fanqie_security_fixes.md # 番茄安全修复
│   ├── 动态分卷命名系统.md      # 分卷系统文档
│   ├── 番茄小说自动上传流程.md  # 上传流程文档
│   ├── 番茄登录优化方案.md      # 登录优化文档
│   └── 项目清理报告-2025-11-01.md # 项目清理报告
├── scripts/                     # 脚本工具（已整理分类）
│   ├── diagnostics/             # 诊断工具（20个）
│   ├── testing/                 # 测试工具（8个）
│   ├── fixes/                   # 修复工具（6个）
│   ├── utilities/               # 实用工具（5个）
│   └── deploy/                  # 部署脚本（7个）
├── tests/                       # 集成测试
├── CLAUDE.md                    # AI助手指南（本文件）
├── README.md                    # 项目说明
└── DEPLOYMENT.md                # 部署指南
```

## 系统架构概览

### 核心服务架构
- **AI路由+3Agent系统** (`ai_orchestrator_helper.py`): 智能分配AI任务 + Planner → Writer → Reviewer 三步式协作生成
- **双模式自动生成器** (`auto_generator_service.py`): 基础模式（快速生成）+ 增强模式（异步深度分析）
- **分卷管理系统** (`volume_split_service.py`): 支持多分卷创作，每个分卷独立的人物关系和世界观快照
- **LLM统一接口** (`llm_service.py`): 统一的LLM调用接口，支持多个AI提供商

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

#### Novel (backend/app/models/novel.py)
小说项目主表，核心字段：
- `id`: 主键
- `title`: 标题
- `user_id`: 所属用户
- `idea`: 用户创意描述
- `blueprint_data`: AI生成的蓝图（JSON：世界观、人物、关系、情节等）
- `outline_data`: 大纲数据
- `tags`: 分类标签

#### Chapter (backend/app/models/novel.py)
章节内容表，支持多版本：
- `id`: 主键
- `novel_id`: 所属小说
- `chapter_number`: 章节号
- `title`: 章节标题
- `content`: 内容（JSON数组，支持多版本）
- `selected_version`: 用户选择的版本索引
- `summary`: 摘要
- `volume_id`: 所属分卷
- `volume_snapshot_id`: 分卷快照ID（关联创作时的上下文）
- `upload_status`: 番茄上传状态

#### VolumeSnapshot (backend/app/models/novel.py)
分卷快照，记录每个分卷的状态：
- `id`: 主键
- `novel_id`: 所属小说
- `volume_number`: 分卷号
- `characters`: 人物列表（JSON）
- `relationships`: 人物关系（JSON）
- `factions`: 势力（JSON）
- `key_locations`: 关键地点（JSON）
- `world_building`: 世界观设定（JSON）
- `chapter_count`: 已生成章节数

#### AsyncTask (backend/app/models/async_task.py)
异步任务队列：
- `id`: 主键
- `task_type`: 任务类型（character_tracking, worldbuilding等）
- `task_data`: 任务数据（JSON）
- `status`: 状态（pending, running, completed, failed）
- `result_data`: 结果数据（JSON）
- `novel_id`, `chapter_id`: 关联对象

#### AutoGeneratorTask (backend/app/models/auto_generator.py)
自动生成器任务：
- `id`: 主键
- `novel_id`: 所属小说
- `status`: 状态（pending, running, paused, completed, failed）
- `current_chapter`: 当前处理章节
- `total_chapters`: 总章节数
- `enable_enhanced_mode`: 是否启用增强模式
- `auto_upload`: 是否自动上传
- `upload_interval_seconds`: 上传间隔

#### 其他模型
- **User**: 用户账户
- **AIRoutingConfig**: AI路由配置
- **LLMConfig**: LLM模型配置
- **Prompt**: 提示词模板
- **StoryMetrics**: 故事指标分析
- **UsageMetric**: API使用统计
- **SystemConfig**: 系统配置
- **UserDailyRequest**: 用户每日请求统计
- **UpdateLog**: 更新日志
- **AdminSetting**: 管理设置

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

## API端点概览

所有API端点都在 `/api` 前缀下。主要路由：

### 认证 (`/api/auth`)
- `POST /register` - 用户注册
- `POST /login` - 用户登录
- `POST /send-email-code` - 发送邮箱验证码
- `GET /me` - 获取当前用户信息

### 小说管理 (`/api/novels`)
- `GET /` - 获取小说列表
- `POST /` - 创建新小说
- `GET /{novel_id}` - 获取小说详情
- `PUT /{novel_id}` - 更新小说
- `DELETE /{novel_id}` - 删除小说
- `POST /{novel_id}/blueprint` - 生成蓝图
- `POST /{novel_id}/outline` - 生成大纲

### 章节写作 (`/api/writer`)
- `POST /generate-chapter` - 生成章节（支持3Agent模式）
- `POST /extract-summary` - 提取章节摘要
- `PUT /chapters/{chapter_id}` - 更新章节
- `POST /chapters/{chapter_id}/select-version` - 选择章节版本

### 自动生成器 (`/api/auto-generator`)
- `POST /tasks` - 创建自动生成任务
- `GET /tasks/{task_id}` - 获取任务状态
- `POST /tasks/{task_id}/pause` - 暂停任务
- `POST /tasks/{task_id}/resume` - 恢复任务
- `DELETE /tasks/{task_id}` - 删除任务

### 分卷管理 (`/api/volume-management`)
- `POST /novels/{novel_id}/split-volumes` - 分卷切分
- `GET /novels/{novel_id}/volumes` - 获取分卷列表
- `POST /volumes/{volume_id}/snapshot` - 创建分卷快照

### AI路由配置 (`/api/ai-routing`)
- `GET /configs` - 获取AI路由配置
- `PUT /configs/{config_id}` - 更新配置
- `GET /providers` - 获取可用的AI提供商

### 异步分析 (`/api/async-analysis`)
- `POST /tasks` - 创建异步分析任务
- `GET /tasks/{task_id}` - 获取任务结果

### LLM配置 (`/api/llm-config`)
- `GET /` - 获取LLM配置
- `PUT /` - 更新LLM配置

### 管理后台 (`/api/admin`)
- `GET /users` - 用户列表
- `GET /system-stats` - 系统统计
- `GET /usage-metrics` - 使用指标

## 代码规范和最佳实践

### Python后端

#### 架构模式
- **分层架构**: API层 → Service层 → Repository层 → Model层
- **依赖注入**: 使用FastAPI的依赖注入系统
- **异步优先**: 所有IO操作使用 `async/await`

#### 命名规范
- **文件名**: 小写+下划线 (`novel_service.py`)
- **类名**: 大驼峰 (`NovelService`)
- **函数名**: 小写+下划线 (`generate_chapter()`)
- **常量**: 全大写+下划线 (`MAX_CHAPTERS`)

#### Service层规范
```python
class NovelService:
    """服务类使用类方法，不依赖实例状态"""

    @classmethod
    async def create_novel(cls, session: AsyncSession, data: dict) -> Novel:
        """所有数据库操作接收session参数"""
        # 业务逻辑
        pass
```

#### 错误处理
```python
from fastapi import HTTPException

# 使用HTTPException返回错误
raise HTTPException(status_code=404, detail="Novel not found")
```

#### 日志记录
```python
import logging

logger = logging.getLogger(__name__)
logger.info("生成蓝图成功")
logger.error(f"生成失败: {error}")
```

### Vue前端

#### 组件规范
- **单文件组件**: 使用 `<script setup>` + TypeScript
- **Props类型**: 使用 `defineProps<T>()` 定义类型
- **Emits**: 使用 `defineEmits<T>()` 定义事件

#### 状态管理
- **Pinia Store**: 用于全局状态（用户、小说数据等）
- **组件状态**: 使用 `ref()` 和 `reactive()`
- **持久化**: 重要状态使用 `localStorage`

#### API调用
```typescript
// 使用封装的API函数
import { novelApi } from '@/api/novels'

const novels = await novelApi.getAll()
```

#### 样式规范
- **Tailwind CSS**: 优先使用工具类
- **Naive UI**: UI组件库
- **Scoped CSS**: 组件私有样式使用 `<style scoped>`

## 重要注意事项

### 3Agent模式关键修复
项目经历了多次3Agent模式的bug修复，重点关注：

1. **Planner格式检测** (`hybrid_agent_service.py`):
   - Planner响应必须包含结构化的JSON块
   - 使用正则表达式检测JSON格式
   - 自动去除Markdown代码块标记

2. **Full Content保存** (`writer.py`):
   - 章节内容必须保存 `full_content` 字段
   - 版本结构: `{"version": 1, "content": "...", "full_content": "..."}`
   - 3Agent模式生成的内容包含完整场景

3. **元数据提取** (`hybrid_agent_service.py`):
   - Writer响应解析支持多种格式
   - 自动提取 `title`, `summary`, `key_events`
   - 容错处理：缺失字段不中断流程

### 并发和性能优化

1. **SQLite WAL模式** (`main.py:73`):
   - 启动时自动启用WAL模式提升并发性能
   - 支持读写并发

2. **任务恢复** (`main.py:83`):
   - 服务器重启自动恢复运行中的任务
   - 使用 `AutoGeneratorService.recover_running_tasks()`

3. **异步处理**:
   - 增强模式分析使用独立进程 (`background_processor.py`)
   - 避免阻塞主服务

### 番茄小说上传

1. **Cookie管理** (`fanqie_browser_manager.py`):
   - Cookie持久化到本地文件
   - 自动检测登录状态
   - 支持手动登录和cookie导入

2. **状态机** (`fanqie_publisher_service.py`):
   - 使用优先级状态机处理复杂上传流程
   - 自动处理验证码、分卷选择等场景

3. **错误处理**:
   - 重试机制：网络错误自动重试
   - 断点续传：记录上传位置

### 提示词管理

1. **热重载** (`reload_prompts.py`):
   - 修改提示词后运行脚本立即生效
   - 无需重启服务

2. **提示词结构** (`backend/prompts/`):
   - Markdown格式，支持变量替换
   - 使用 `{variable}` 语法
   - 每个功能独立文件

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
- **单元测试**: 覆盖核心业务逻辑和数据访问层
  - 使用 `pytest` + `pytest-asyncio`
  - Mock外部API调用

- **集成测试**: 验证AI模式和外部服务集成
  - 测试3Agent协作流程
  - 测试AI路由和模型切换
  - 位置: `backend/tests/integration/`

- **功能测试**: 专项功能验证
  - `test_3agent_direct.py`: 3Agent模式直接测试
  - `test_planner_detection.py`: Planner格式检测
  - `test_async_analysis.py`: 异步分析流程

- **诊断工具**: 问题排查
  - `diagnose_3agent.py`: 3Agent问题诊断
  - `full_diagnostic.py`: 完整系统诊断
  - `batch_check_all_chapters.py`: 批量检查章节

## 开发工作流

### 新功能开发流程

1. **需求分析**
   - 确定功能所在层次（API、Service、Model）
   - 评估是否需要数据库变更

2. **数据库迁移**（如需要）
   ```bash
   # 修改 models/ 中的模型定义
   # 创建迁移脚本
   alembic revision -m "描述变更"
   # 执行迁移
   python run_migration.py
   ```

3. **实现Service层**
   ```python
   # backend/app/services/your_service.py
   class YourService:
       @classmethod
       async def your_method(cls, session: AsyncSession, ...):
           # 实现业务逻辑
           pass
   ```

4. **实现API层**
   ```python
   # backend/app/api/routers/your_router.py
   @router.post("/endpoint")
   async def endpoint(
       data: YourSchema,
       session: AsyncSession = Depends(get_session),
       current_user: User = Depends(get_current_user)
   ):
       result = await YourService.your_method(session, ...)
       return result
   ```

5. **前端实现**
   ```typescript
   // frontend/src/api/your-api.ts
   export const yourApi = {
       async yourMethod(data: any) {
           return await api.post('/api/endpoint', data)
       }
   }

   // frontend/src/components/YourComponent.vue
   const handleAction = async () => {
       const result = await yourApi.yourMethod(data)
   }
   ```

6. **测试**
   ```bash
   # 后端测试
   pytest backend/tests/

   # 前端类型检查
   npm run type-check
   ```

### Bug修复流程

1. **重现问题**
   - 使用诊断工具定位问题
   - 查看日志：`uvicorn` 输出或浏览器控制台

2. **定位代码**
   - 根据错误堆栈找到出错位置
   - 检查相关Service和API

3. **修复和测试**
   - 修改代码
   - 编写或更新测试用例
   - 验证修复效果

4. **回归测试**
   - 运行全部测试确保没有破坏其他功能

### 提示词调优流程

1. **修改提示词**
   ```bash
   # 编辑 backend/prompts/ 中的.md文件
   vim backend/prompts/agent_writer.md
   ```

2. **重载到数据库**
   ```bash
   python backend/reload_prompts.py
   ```

3. **测试效果**
   ```bash
   # 使用测试脚本验证
   python test_3agent_direct.py
   ```

4. **迭代优化**
   - 根据生成结果调整提示词
   - 重复步骤1-3

## 环境配置

### 必需的环境变量

```bash
# .env 文件示例

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./storage/arboris.db
# 或 MySQL: mysql+asyncmy://user:password@localhost/dbname

# JWT密钥（生产环境必须修改）
SECRET_KEY=your-secret-key-here

# AI提供商API密钥（至少配置一个）
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...
SILICONFLOW_API_KEY=sk-...

# 应用配置
ALLOW_USER_REGISTRATION=true
DEBUG=true
LOGGING_LEVEL=INFO

# 可选：向量存储
VECTOR_STORE_ENABLED=false
```

### 开发环境设置

1. **Python环境**
   ```bash
   python --version  # 需要 3.11+
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Node.js环境**
   ```bash
   node --version  # 需要 20+
   cd frontend
   npm install
   ```

3. **数据库初始化**
   ```bash
   cd backend
   python run_migration.py
   python reload_prompts.py
   ```

4. **启动服务**
   ```bash
   # 终端1: 后端
   cd backend
   uvicorn app.main:app --reload

   # 终端2: 前端
   cd frontend
   npm run dev

   # 终端3: 异步处理器（可选）
   cd backend
   python -m app.background_processor
   ```

### 生产环境部署

参考文档：
- `DEPLOYMENT.md`: 完整部署指南
- `SERVER_DEPLOY.sh`: 服务器部署脚本（一键部署）
- `server_deployment_guide.sh`: 服务器部署指南
- `scripts/deploy.sh`: 标准部署脚本

关键步骤：
1. 配置环境变量（禁用DEBUG、更换SECRET_KEY）
2. 使用MySQL或PostgreSQL替代SQLite
3. 配置Nginx反向代理
4. 使用Systemd管理进程
5. 配置日志轮转和监控
6. 运行 `./SERVER_DEPLOY.sh` 执行自动化部署

## 故障排查指南

### 常见问题

#### 1. 3Agent模式生成失败
```bash
# 诊断问题
python diagnose_3agent.py

# 检查Planner格式
python test_planner_detection.py

# 查看生成流程
python show_latest_generation_flow.py
```

可能原因：
- Planner响应格式不正确
- API密钥配置错误
- 提示词格式问题

#### 2. 章节内容为空
```bash
# 检查章节内容
python preview_chapters.py

# 批量检查
python batch_check_all_chapters.py
```

可能原因：
- full_content字段未保存
- 版本选择错误
- Writer生成失败

#### 3. 番茄上传失败
```bash
# 检查Cookie状态
python check_gemini_status.py
```

可能原因：
- Cookie过期
- 分卷匹配错误
- 网络问题

#### 4. 数据库锁定
```bash
# 检查数据库状态
python check_db_status.py
```

解决方案：
- 启用WAL模式（已自动启用）
- 检查是否有长时间运行的事务
- 重启服务

### 日志查看

```bash
# 查看后端日志
# uvicorn默认输出到stdout

# 查看特定功能日志
grep "3Agent" logs.txt
grep "ERROR" logs.txt

# 使用诊断脚本
python full_diagnostic.py > diagnostic_report.txt
```

## 最近改进和修复

### 2025-11-18 最新更新
根据最近的Git提交记录，项目进行了以下重要改进：

1. **3Agent模式优化** (commits: bf60bc5, 88d98ea, 042ebf4, eeb3358)
   - 清理生成内容中的Markdown标记
   - 直接返回dict避免JSON序列化/反序列化
   - 移除JSON解析失败的fallback逻辑，防止Planner内容被错误保存
   - 添加强制类型检查，防止Planner格式被保存为章节内容

2. **诊断工具增强**
   - 添加ChapterVersion保存内容检查脚本
   - 添加3Agent工具调用测试脚本
   - 完善Planner检测和验证工具

3. **性能和稳定性**
   - SQLite WAL模式自动启用
   - 任务恢复机制（服务器重启后自动恢复）
   - 验证码缓存清理任务

### 关键修复历史
- ✅ 修复3Agent模式Planner响应格式检测问题
- ✅ 修复章节full_content字段未保存问题
- ✅ 修复Writer响应元数据提取问题
- ✅ 优化番茄小说上传状态机
- ✅ 增强并发处理能力（WAL模式）

## 相关文档

- `README.md`: 项目介绍和快速开始
- `DEPLOYMENT.md`: 部署指南
- `docs/fanqie_upload_guide.md`: 番茄小说上传指南
- `docs/fanqie_security_fixes.md`: 番茄安全修复文档
- `docs/动态分卷命名系统.md`: 分卷系统详细文档
- `docs/番茄小说自动上传流程.md`: 上传流程详细说明
- `docs/guides/`: 功能使用指南
- `docs/reports/`: 项目报告和分析

## 贡献指南

修改代码前请：
1. 阅读本文档了解项目结构
2. 查看相关的测试文件
3. 运行诊断工具确保系统正常
4. 遵循代码规范
5. 编写测试用例
6. 更新相关文档

---

**最后更新**: 2025-11-21
**维护者**: Project Team
**版本**: v1.2.0

## 快速参考卡

### 常用命令速查
```bash
# 启动开发环境
cd backend && uvicorn app.main:app --reload           # 后端
cd frontend && npm run dev                            # 前端

# 数据库操作
python backend/run_migration.py                       # 迁移数据库
python backend/reload_prompts.py                      # 重载提示词

# 快速诊断
python scripts/diagnostics/check_config.py            # 检查配置
python scripts/diagnostics/diagnose_3agent.py         # 诊断3Agent
python scripts/diagnostics/batch_check_all_chapters.py # 检查所有章节

# 测试
pytest backend/tests/                                 # 运行测试
python scripts/testing/test_3agent_tools.py           # 测试3Agent工具
```

### 核心文件位置
- **AI路由+3Agent**: `backend/app/services/ai_orchestrator_helper.py`
- **自动生成**: `backend/app/services/auto_generator_service.py`
- **番茄上传**: `backend/app/services/fanqie_publisher_service.py`
- **LLM服务**: `backend/app/services/llm_service.py`
- **主应用**: `backend/app/main.py`
- **前端入口**: `frontend/src/main.ts`
- **脚本目录**: `scripts/` (详见 `scripts/README.md`)

### 紧急故障处理
1. 服务无法启动 → 检查 `.env` 配置和数据库连接
2. 3Agent生成失败 → 运行 `python scripts/diagnostics/diagnose_3agent.py`
3. 章节内容为空 → 运行 `python scripts/diagnostics/quick_check_full_content.py`
4. 数据库锁定 → 检查WAL模式，重启服务
5. API密钥错误 → 运行 `python scripts/testing/test_gemini_key.py` 验证密钥