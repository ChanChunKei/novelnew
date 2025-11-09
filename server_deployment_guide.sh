#!/bin/bash

# ============================================
# Arboris Novel - 服务器部署脚本
# 适用于: Ubuntu 22.04 LTS
# ============================================

set -e  # 遇到错误立即退出

echo "============================================"
echo "  Arboris Novel - 服务器部署脚本"
echo "  适用于: Ubuntu 22.04 LTS"
echo "============================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为root用户
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}❌ 请不要使用root用户运行此脚本${NC}"
    echo "建议创建普通用户: sudo adduser arboris"
    exit 1
fi

echo -e "${GREEN}========== 步骤 1/10: 更新系统 ==========${NC}"
sudo apt update
sudo apt upgrade -y
echo -e "${GREEN}✅ 系统更新完成${NC}\n"

echo -e "${GREEN}========== 步骤 2/10: 安装基础工具 ==========${NC}"
sudo apt install -y git curl wget vim htop net-tools ufw
echo -e "${GREEN}✅ 基础工具安装完成${NC}\n"

echo -e "${GREEN}========== 步骤 3/10: 安装Python 3.11 ==========${NC}"
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
# 设置python3.11为默认python3
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
python3 --version
echo -e "${GREEN}✅ Python 3.11 安装完成${NC}\n"

echo -e "${GREEN}========== 步骤 4/10: 安装Node.js 20 ==========${NC}"
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version
npm --version
echo -e "${GREEN}✅ Node.js 20 安装完成${NC}\n"

echo -e "${GREEN}========== 步骤 5/10: 安装Nginx ==========${NC}"
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
echo -e "${GREEN}✅ Nginx 安装完成${NC}\n"

echo -e "${GREEN}========== 步骤 6/10: 配置防火墙 ==========${NC}"
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw --force enable
sudo ufw status
echo -e "${GREEN}✅ 防火墙配置完成${NC}\n"

echo -e "${GREEN}========== 步骤 7/10: 克隆项目 ==========${NC}"
cd ~
if [ -d "novel" ]; then
    echo -e "${YELLOW}⚠️  项目目录已存在，跳过克隆${NC}"
else
    git clone https://github.com/siyutaosiyutao/novel.git
    echo -e "${GREEN}✅ 项目克隆完成${NC}"
fi
cd novel
echo -e "${GREEN}当前目录: $(pwd)${NC}\n"

echo -e "${GREEN}========== 步骤 8/10: 配置后端 ==========${NC}"
cd backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 配置环境变量
if [ ! -f .env ]; then
    cp env.example .env
    echo -e "${YELLOW}⚠️  请编辑 backend/.env 文件，填入API密钥${NC}"
    echo -e "${YELLOW}   nano ~/novel/backend/.env${NC}"
else
    echo -e "${GREEN}✅ .env 文件已存在${NC}"
fi

# 创建storage目录
mkdir -p storage/fanqie_cookies

# 运行数据库迁移
echo "正在运行数据库迁移..."
python run_migration.py

# 加载提示词（自动确认模式）
echo "正在加载提示词..."
python reload_prompts.py --auto-confirm

echo -e "${GREEN}✅ 后端配置完成${NC}\n"

echo -e "${GREEN}========== 步骤 9/10: 配置前端 ==========${NC}"
cd ~/novel/frontend

# 安装依赖
npm install

# 构建生产版本
npm run build

echo -e "${GREEN}✅ 前端构建完成${NC}\n"

echo -e "${GREEN}========== 步骤 10/10: 配置systemd服务 ==========${NC}"
cd ~/novel

# 配置API服务
sudo tee /etc/systemd/system/arboris-api.service > /dev/null <<EOF
[Unit]
Description=Arboris Novel API Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/novel/backend
Environment="PATH=$HOME/novel/backend/venv/bin"
ExecStart=$HOME/novel/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 配置异步处理器服务
sudo tee /etc/systemd/system/arboris-async-processor.service > /dev/null <<EOF
[Unit]
Description=Arboris Novel Async Processor
After=network.target arboris-api.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/novel/backend
Environment="PATH=$HOME/novel/backend/venv/bin"
ExecStart=$HOME/novel/backend/venv/bin/python -m app.background_processor
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 配置Nginx
sudo tee /etc/nginx/sites-available/arboris-novel > /dev/null <<'EOF'
server {
    listen 80;
    server_name _;  # 替换为你的域名

    # 前端静态文件
    location / {
        root /home/USER_PLACEHOLDER/novel/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置（AI生成可能需要较长时间）
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # API文档
    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
EOF

# 替换用户名
sudo sed -i "s|USER_PLACEHOLDER|$USER|g" /etc/nginx/sites-available/arboris-novel

# 启用站点
sudo ln -sf /etc/nginx/sites-available/arboris-novel /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 测试Nginx配置
sudo nginx -t

# 重载Nginx
sudo systemctl reload nginx

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable arboris-api
sudo systemctl enable arboris-async-processor
sudo systemctl start arboris-api
sudo systemctl start arboris-async-processor

echo -e "${GREEN}✅ systemd服务配置完成${NC}\n"

echo "============================================"
echo -e "${GREEN}  ✅ 部署完成！${NC}"
echo "============================================"
echo ""
echo "📊 服务状态检查:"
echo "  sudo systemctl status arboris-api"
echo "  sudo systemctl status arboris-async-processor"
echo "  sudo systemctl status nginx"
echo ""
echo "📝 查看日志:"
echo "  sudo journalctl -u arboris-api -f"
echo "  sudo journalctl -u arboris-async-processor -f"
echo ""
echo "🌐 访问地址:"
echo "  前端: http://your-server-ip"
echo "  API文档: http://your-server-ip/docs"
echo ""
echo "⚠️  重要提醒:"
echo "  1. 编辑 ~/novel/backend/.env 文件，填入API密钥"
echo "  2. 重启服务: sudo systemctl restart arboris-api"
echo "  3. 如有域名，修改 /etc/nginx/sites-available/arboris-novel"
echo "  4. 建议配置SSL证书（使用Let's Encrypt）"
echo ""

