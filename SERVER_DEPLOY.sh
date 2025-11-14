#!/bin/bash
# 3Agent Metadata修复 - 服务器部署脚本

echo "================================"
echo "开始部署到服务器"
echo "================================"

# 1. 切换到正确的目录
cd /home/arboris/novel || {
    echo "❌ 目录不存在，请检查项目路径"
    exit 1
}

# 2. 拉取最新代码
echo "📥 拉取最新代码..."
sudo -u arboris git pull origin main

# 3. 更新后端
echo "🔧 更新后端..."
cd backend
sudo -u arboris venv/bin/pip install -r requirements.txt

# 4. 更新前端
echo "🎨 更新前端..."
cd ../frontend
sudo -u arboris npm install
sudo -u arboris npm run build

# 5. 重启服务
echo "🔄 重启服务..."
sudo systemctl restart arboris-api
sudo systemctl restart arboris-async-processor
sudo systemctl restart nginx

# 6. 检查状态
echo "✅ 检查服务状态..."
sleep 3
sudo systemctl status arboris-api --no-pager -l | head -20

echo ""
echo "================================"
echo "部署完成！"
echo "================================"
echo ""
echo "验证步骤："
echo "1. 访问前端: http://your-server-ip"
echo "2. 用3Agent模式生成一个章节"
echo "3. 查看版本详情，应该能看到3Agent生成详情"
