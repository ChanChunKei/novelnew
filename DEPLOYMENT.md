# Arboris Novel 一键部署指南

本文档提供在全新服务器上一键部署 Arboris Novel 小说生成系统的完整步骤。

## 📋 系统要求

### 硬件要求
- **CPU**: 2核及以上
- **内存**: 4GB 及以上（推荐 8GB）
- **磁盘**: 20GB 可用空间

### 软件要求
- **操作系统**: Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- **Python**: 3.9+
- **Node.js**: 20.19.0+ 或 22.12.0+
- **Git**: 用于克隆代码

## 🚀 一键部署

### 方式一：使用自动化脚本（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/siyutaosiyutao/arboris-novel.git
cd arboris-novel

# 2. 运行一键部署脚本
chmod +x deploy.sh
./deploy.sh
```

脚本将自动完成：
- ✅ 检查系统依赖（Python、Node.js、npm）
- ✅ 安装后端 Python 依赖
- ✅ 配置环境变量（.env）
- ✅ 初始化数据库
- ✅ 安装前端依赖
- ✅ 构建前端
- ✅ 配置并启动系统服务

### 方式二：手动部署

如果需要手动控制每个步骤，请按以下流程操作。

---

## 📦 手动部署步骤

### 步骤 1: 安装系统依赖

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nodejs npm git
```

#### CentOS/RHEL
```bash
sudo yum install -y python3 python3-pip nodejs npm git
```

#### 验证安装
```bash
python3 --version  # 应该 >= 3.9
node --version     # 应该 >= 20.19.0
npm --version      # 应该 >= 9.0.0
```

### 步骤 2: 克隆项目代码

```bash
# 克隆项目到指定目录
git clone https://github.com/siyutaosiyutao/arboris-novel.git
cd arboris-novel
```

### 步骤 3: 配置后端

```bash
cd backend

# 创建 Python 虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装 Python 依赖
pip install --upgrade pip
pip install -r requirements.txt

# 配置环境变量
# .env 文件已经创建，需要修改以下关键配置：
nano .env
```

**必须修改的配置项**：
```bash
# 至少需要配置一个 LLM API Key
OPENAI_API_KEY=sk-your-actual-api-key-here
# 或者
GEMINI_API_KEY=your-gemini-api-key-here
# 或者
DEEPSEEK_API_KEY=your-deepseek-api-key-here

# 如果使用 MySQL（可选，默认使用 SQLite）
DB_PROVIDER=mysql
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=arboris
```

**创建必要的目录**：
```bash
mkdir -p storage logs
```

**初始化数据库**：
```bash
# SQLite 模式（默认）- 无需额外配置
# MySQL 模式 - 需要先创建数据库
# mysql -u root -p -e "CREATE DATABASE arboris CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 数据库会在首次启动时自动初始化
```

### 步骤 4: 配置前端

```bash
cd ../frontend

# 安装 Node.js 依赖
npm install

# 构建前端（生产环境）
npm run build

# 或者运行开发服务器（开发环境）
# npm run dev
```

### 步骤 5: 测试运行

#### 测试后端
```bash
cd ../backend
source venv/bin/activate

# 启动后端服务
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 在另一个终端测试健康检查
curl http://localhost:8000/health
# 预期输出: {"status":"healthy","app":"AI Novel Generator API","version":"1.0.0"}
```

#### 测试前端（开发模式）
```bash
cd ../frontend
npm run dev
# 访问 http://localhost:5173
```

### 步骤 6: 生产部署（使用 systemd）

#### 6.1 配置服务文件

```bash
cd backend/deployment

# 编辑服务文件，替换路径占位符
export PROJECT_DIR=$(pwd | sed 's|/backend/deployment||')
export USER=$(whoami)

# 替换占位符
sed "s|{{PROJECT_DIR}}|$PROJECT_DIR|g; s|{{USER}}|$USER|g" arboris-api.service > /tmp/arboris-api.service
sed "s|{{PROJECT_DIR}}|$PROJECT_DIR|g; s|{{USER}}|$USER|g" arboris-async-processor.service > /tmp/arboris-async-processor.service

# 复制服务文件
sudo cp /tmp/arboris-api.service /etc/systemd/system/
sudo cp /tmp/arboris-async-processor.service /etc/systemd/system/

# 创建日志目录
sudo mkdir -p /var/log/arboris
sudo chown $USER:$USER /var/log/arboris
```

#### 6.2 启动服务

```bash
# 重载 systemd
sudo systemctl daemon-reload

# 启动后端 API 服务
sudo systemctl start arboris-api
sudo systemctl enable arboris-api

# 启动异步处理器服务
sudo systemctl start arboris-async-processor
sudo systemctl enable arboris-async-processor

# 检查服务状态
sudo systemctl status arboris-api
sudo systemctl status arboris-async-processor
```

#### 6.3 配置 Nginx（可选）

如果需要通过域名访问或配置 HTTPS：

```bash
sudo apt install -y nginx

# 创建 Nginx 配置
sudo tee /etc/nginx/sites-available/arboris <<EOF
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root $PROJECT_DIR/frontend/dist;
        try_files \$uri \$uri/ /index.html;
    }

    # 后端 API 代理
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

# 启用配置
sudo ln -s /etc/nginx/sites-available/arboris /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 6.4 配置 HTTPS（可选）

```bash
# 安装 Certbot
sudo apt install -y certbot python3-certbot-nginx

# 获取 SSL 证书
sudo certbot --nginx -d your-domain.com

# 证书会自动续期
```

---

## 🔧 常用命令

### 服务管理
```bash
# 查看服务状态
sudo systemctl status arboris-api
sudo systemctl status arboris-async-processor

# 重启服务
sudo systemctl restart arboris-api
sudo systemctl restart arboris-async-processor

# 停止服务
sudo systemctl stop arboris-api
sudo systemctl stop arboris-async-processor

# 查看日志
sudo journalctl -u arboris-api -f
sudo journalctl -u arboris-async-processor -f

# 或查看日志文件
tail -f /var/log/arboris/api.log
tail -f /var/log/arboris/async-processor.log
```

### 数据库管理
```bash
cd backend

# 重置管理员密码
source venv/bin/activate
python reset_admin_password.py

# 备份数据库（SQLite）
cp storage/arboris.db storage/arboris.db.backup-$(date +%Y%m%d)

# 备份数据库（MySQL）
mysqldump -u root -p arboris > arboris-backup-$(date +%Y%m%d).sql
```

### 更新部署
```bash
# 拉取最新代码
git pull origin main

# 更新后端
cd backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart arboris-api
sudo systemctl restart arboris-async-processor

# 更新前端
cd ../frontend
npm install
npm run build
sudo systemctl restart nginx  # 如果使用 Nginx
```

---

## 🐛 故障排查

### 1. 后端无法启动

**检查日志**：
```bash
sudo journalctl -u arboris-api -n 50
```

**常见问题**：
- ❌ `ModuleNotFoundError`: Python 依赖未安装 → `pip install -r requirements.txt`
- ❌ `SECRET_KEY required`: 未配置 .env → 检查 `backend/.env` 文件
- ❌ `Can't connect to MySQL`: 数据库连接失败 → 检查 MySQL 服务和 .env 配置
- ❌ `Port 8000 already in use`: 端口被占用 → `sudo lsof -i :8000` 查找占用进程

### 2. 前端无法访问

**检查前端构建**：
```bash
cd frontend
npm run build
ls -la dist/  # 确认构建产物存在
```

**检查 Nginx 配置**：
```bash
sudo nginx -t
sudo systemctl status nginx
```

### 3. API 调用失败

**测试后端健康检查**：
```bash
curl http://localhost:8000/health
```

**检查 CORS 配置**：
- 确保 `backend/app/main.py` 中的 CORS 允许前端域名

### 4. 数据库连接失败

**SQLite 模式**：
```bash
# 检查目录权限
ls -la backend/storage/
# 确保有写入权限
```

**MySQL 模式**：
```bash
# 测试 MySQL 连接
mysql -h localhost -u root -p -e "SHOW DATABASES;"
# 检查数据库是否存在
mysql -h localhost -u root -p -e "USE arboris; SHOW TABLES;"
```

---

## 📞 获取帮助

- **GitHub Issues**: https://github.com/siyutaosiyutao/arboris-novel/issues
- **文档**: 查看项目根目录下的其他 .md 文件

---

## 📄 许可证

本项目遵循相应的开源许可证，详见 LICENSE 文件。

---

## 🎉 部署成功

如果一切正常，您现在可以：

1. **访问前端**: http://your-domain.com 或 http://your-ip
2. **使用默认管理员登录**:
   - 用户名: `admin`
   - 密码: `ChangeMe123!`（请立即修改）
3. **开始创作**: 创建小说项目，体验 AI 小说生成功能

祝您使用愉快！🎊
