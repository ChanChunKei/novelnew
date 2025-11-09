# 部署前检查清单

在将项目推送到GitHub和部署到服务器之前，请确保完成以下检查：

## ✅ 代码清理

- [x] 删除所有调试HTML文件
- [x] 删除所有临时测试脚本
- [x] 删除所有临时工具脚本
- [x] 删除根目录的临时文件
- [x] 删除验证脚本
- [x] 更新.gitignore文件

## ✅ 敏感信息检查

- [ ] 确认所有API密钥已从代码中移除
- [ ] 确认数据库密码已从代码中移除
- [ ] 确认.env文件不会被上传（已在.gitignore中）
- [ ] 确认env.example文件中没有真实密钥
- [ ] 确认storage/目录中的数据库不会被上传

## ✅ 文档完整性

- [x] README.md已创建并包含完整信息
- [x] DEPLOYMENT.md部署指南已存在
- [x] 提示词文件（prompts/）已包含
- [x] 数据库迁移脚本（migrations/）已包含

## ✅ 配置文件

- [x] backend/env.example已完整
- [ ] frontend环境变量配置已检查
- [x] requirements.txt已更新
- [x] package.json已更新

## ✅ 数据库

- [x] 数据库迁移脚本已准备
- [x] reload_prompts.py脚本已保留
- [x] run_migration.py脚本已保留
- [ ] 确认生产环境数据库配置

## ✅ 服务配置

- [x] systemd服务文件已准备（deployment/）
- [x] 包含API服务配置
- [x] 包含异步处理器服务配置
- [ ] Nginx配置已准备（如需要）

## ✅ Git准备

- [x] .gitignore已更新
- [ ] 初始化git仓库（如未初始化）
- [ ] 添加所有文件到git
- [ ] 创建初始提交
- [ ] 设置远程仓库地址
- [ ] 推送到GitHub

## 📝 Git操作命令

```bash
# 1. 检查当前状态
git status

# 2. 添加所有文件
git add .

# 3. 创建初始提交
git commit -m "Initial commit: AI Novel Writing System

Features:
- AI-powered novel blueprint generation
- Automatic outline and chapter generation
- Multi-volume management with snapshot system
- AI routing system with multiple providers
- Auto-generator with dual modes (basic/enhanced)
- Fanqie Novel platform auto-upload
- Async analysis processor
- Vue 3 + FastAPI architecture
"

# 4. 添加远程仓库（替换为你的仓库地址）
git remote add origin https://github.com/yourusername/arboris-novel.git

# 5. 推送到GitHub
git push -u origin main
# 或者如果默认分支是master
git push -u origin master
```

## 🚀 服务器部署步骤

### 1. 准备服务器环境

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip -y

# 安装Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs -y

# 安装Nginx（如需要）
sudo apt install nginx -y

# 安装Git
sudo apt install git -y
```

### 2. 克隆项目

```bash
cd /opt
sudo git clone https://github.com/yourusername/arboris-novel.git
sudo chown -R $USER:$USER arboris-novel
cd arboris-novel
```

### 3. 后端部署

```bash
cd backend

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp env.example .env
nano .env  # 编辑配置

# 运行数据库迁移
python run_migration.py

# 加载提示词
python reload_prompts.py

# 安装systemd服务
sudo cp deployment/arboris-api.service /etc/systemd/system/
sudo cp deployment/arboris-async-processor.service /etc/systemd/system/

# 编辑服务文件，修改路径和用户
sudo nano /etc/systemd/system/arboris-api.service
sudo nano /etc/systemd/system/arboris-async-processor.service

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable arboris-api
sudo systemctl enable arboris-async-processor
sudo systemctl start arboris-api
sudo systemctl start arboris-async-processor

# 检查状态
sudo systemctl status arboris-api
sudo systemctl status arboris-async-processor
```

### 4. 前端部署

```bash
cd frontend

# 安装依赖
npm install

# 构建生产版本
npm run build

# 配置Nginx（如需要）
sudo nano /etc/nginx/sites-available/arboris-novel
# 添加配置后
sudo ln -s /etc/nginx/sites-available/arboris-novel /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5. 配置防火墙

```bash
# 允许HTTP和HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 如果直接暴露后端端口
sudo ufw allow 8000/tcp

# 启用防火墙
sudo ufw enable
```

## 🔍 部署后检查

- [ ] API服务正常运行（http://your-server:8000/docs）
- [ ] 异步处理器正常运行
- [ ] 前端页面可访问
- [ ] 数据库连接正常
- [ ] AI API调用正常
- [ ] 日志记录正常
- [ ] 番茄小说上传功能正常（如使用）

## 📊 监控和维护

### 查看日志

```bash
# API服务日志
sudo journalctl -u arboris-api -f

# 异步处理器日志
sudo journalctl -u arboris-async-processor -f

# Nginx日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 重启服务

```bash
# 重启API服务
sudo systemctl restart arboris-api

# 重启异步处理器
sudo systemctl restart arboris-async-processor

# 重启Nginx
sudo systemctl restart nginx
```

### 更新代码

```bash
cd /opt/arboris-novel

# 拉取最新代码
git pull origin main

# 更新后端
cd backend
source venv/bin/activate
pip install -r requirements.txt
python run_migration.py  # 如有新的迁移
sudo systemctl restart arboris-api
sudo systemctl restart arboris-async-processor

# 更新前端
cd ../frontend
npm install
npm run build
```

## ⚠️ 注意事项

1. **备份数据**：部署前备份现有数据库
2. **环境变量**：确保所有API密钥正确配置
3. **权限设置**：确保服务有权限访问storage目录
4. **HTTPS配置**：生产环境建议配置SSL证书
5. **定期备份**：设置定时任务备份数据库
6. **监控告警**：配置服务监控和告警机制

## 📞 问题排查

如遇到问题，请检查：
1. 服务日志：`sudo journalctl -u arboris-api -n 100`
2. 环境变量配置
3. 数据库连接
4. API密钥有效性
5. 端口占用情况：`sudo netstat -tlnp | grep 8000`
6. 磁盘空间：`df -h`
7. 内存使用：`free -h`

