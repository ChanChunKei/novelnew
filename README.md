# Arboris Novel - AI小说创作系统

一个基于AI的智能小说创作平台，支持自动生成大纲、章节内容、人物关系等，并可自动上传到番茄小说平台。

## ✨ 核心功能

### 📝 智能创作
- **蓝图生成**：根据创意自动生成完整的小说蓝图（世界观、人物、情节）
- **大纲生成**：智能生成章节大纲，支持分卷管理
- **章节创作**：自动生成多个版本的章节内容供选择
- **摘要提取**：自动提取章节核心信息，用于后续创作上下文

### 🎯 分卷管理
- **动态分卷**：支持多分卷创作，每个分卷独立管理
- **快照系统**：记录每个分卷的人物、关系、世界观演变
- **智能上下文**：生成章节时自动使用当前分卷的快照数据

### 🤖 AI路由系统
- **多模型支持**：集成OpenAI、Anthropic、Google、SiliconFlow等多个AI提供商
- **智能路由**：根据任务类型自动选择最合适的AI模型
- **成本优化**：根据任务复杂度选择性价比最优的模型
- **功能分类**：
  - 蓝图生成：Claude Sonnet 3.5
  - 大纲生成：Claude Sonnet 3.5
  - 章节创作：SiliconFlow DeepSeek-V3
  - 摘要提取：Google Gemini Flash
  - 增强分析：Claude Sonnet 3.5

### 🚀 自动生成器
- **双模式运行**：
  - **基础模式**：快速生成章节和摘要
  - **增强模式**：异步执行深度分析（角色追踪、世界观扩展等）
- **自动上传**：生成完成后自动上传到番茄小说
- **灵活配置**：可配置生成数量、上传间隔等参数

### 📤 番茄小说上传
- **自动登录**：支持Cookie持久化，自动保持登录状态
- **智能分卷**：自动匹配本地分卷到番茄小说分卷
- **状态机管理**：使用优先级状态机处理复杂的上传流程
- **错误恢复**：自动处理各种异常情况，支持断点续传

### 📊 增强分析（异步）
- **角色追踪**：分析角色在章节中的表现和变化
- **世界观扩展**：提取新的世界观设定
- **情节分析**：识别关键情节点和伏笔
- **后台处理**：不阻塞主流程，异步完成分析

## 🏗️ 技术架构

### 后端 (FastAPI + Python)
```
backend/
├── app/
│   ├── api/              # API路由
│   ├── models/           # 数据库模型
│   ├── services/         # 业务逻辑
│   │   ├── auto_generator_service.py      # 自动生成器
│   │   ├── fanqie_publisher_service.py    # 番茄小说上传
│   │   ├── ai_orchestrator_helper.py      # AI路由助手
│   │   └── async_analysis_processor.py    # 异步分析处理器
│   ├── repositories/     # 数据访问层
│   └── schemas/          # Pydantic模型
├── prompts/              # AI提示词模板
├── migrations/           # 数据库迁移脚本
└── storage/              # 数据存储目录
```

### 前端 (Vue 3 + TypeScript)
```
frontend/
├── src/
│   ├── components/       # Vue组件
│   ├── views/            # 页面视图
│   ├── stores/           # Pinia状态管理
│   └── api/              # API调用
└── public/               # 静态资源
```

## 🚀 快速开始

### 环境要求
- Python 3.11+
- Node.js 18+
- SQLite 3

### 后端安装

```bash
cd backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp env.example .env
# 编辑 .env 文件，填入API密钥

# 运行数据库迁移
python run_migration.py

# 加载提示词到数据库
python reload_prompts.py

# 启动后端服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动异步分析处理器（可选）
python -m app.background_processor
```

### 前端安装

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

## 📝 配置说明

### 环境变量 (.env)

```bash
# 数据库
DATABASE_URL=sqlite+aiosqlite:///./storage/arboris.db

# AI提供商API密钥
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
SILICONFLOW_API_KEY=your_siliconflow_key

# JWT密钥
SECRET_KEY=your_secret_key

# 向量数据库（可选）
VECTOR_STORE_ENABLED=false
```

### AI路由配置

在管理后台（`/admin/ai-routing`）可以配置：
- AI提供商的优先级和权重
- 每个功能使用的模型
- 模型参数（temperature、max_tokens等）

## 📖 使用指南

### 1. 创建项目
1. 点击"新建项目"
2. 输入创意描述
3. AI自动生成蓝图（世界观、人物、情节）

### 2. 生成大纲
1. 在项目详情页点击"生成大纲"
2. 设置分卷和章节数量
3. AI自动生成章节大纲

### 3. 创作章节
- **手动创作**：在章节列表点击"生成"，选择喜欢的版本
- **自动创作**：启用自动生成器，设置参数后自动生成所有章节

### 4. 上传到番茄小说
1. 配置番茄小说Cookie（首次需要手动登录）
2. 在项目设置中启用"自动上传"
3. 或手动选择章节上传

## 🔧 部署指南

详见 [DEPLOYMENT.md](./DEPLOYMENT.md)

## 📚 文档

- [部署指南](./DEPLOYMENT.md)
- [番茄小说上传指南](./docs/fanqie_upload_guide.md)
- [AI路由系统说明](./docs/guides/)
- [更多文档](./docs/)

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

- OpenAI GPT系列
- Anthropic Claude系列
- Google Gemini系列
- SiliconFlow DeepSeek-V3
- FastAPI
- Vue 3
- Playwright

---

**注意**：本项目仅供学习交流使用，请遵守相关平台的使用条款。

