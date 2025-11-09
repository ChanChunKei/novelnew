#!/bin/bash

# 修复用户路由配置不生效的问题
# 这个脚本会将修复后的代码部署到服务器

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========== 部署修复补丁 ==========${NC}\n"

# 1. 检查是否在正确的目录
if [ ! -f "backend/app/services/llm_service.py" ]; then
    echo -e "${RED}❌ 错误: 请在项目根目录运行此脚本${NC}"
    exit 1
fi

# 2. 备份原文件
echo -e "${YELLOW}步骤 1/4: 备份原文件${NC}"
cp backend/app/services/llm_service.py backend/app/services/llm_service.py.backup.$(date +%Y%m%d_%H%M%S)
echo -e "${GREEN}✅ 备份完成${NC}\n"

# 3. 检查修改
echo -e "${YELLOW}步骤 2/4: 检查修改${NC}"
if grep -q "优先从用户路由配置获取" backend/app/services/llm_service.py; then
    echo -e "${GREEN}✅ 代码已包含修复${NC}\n"
else
    echo -e "${RED}❌ 代码未包含修复，请先在本地运行修复${NC}"
    exit 1
fi

# 4. 重启服务
echo -e "${YELLOW}步骤 3/4: 重启后端服务${NC}"
sudo systemctl restart arboris-api
echo -e "${GREEN}✅ 服务已重启${NC}\n"

# 5. 检查服务状态
echo -e "${YELLOW}步骤 4/4: 检查服务状态${NC}"
sleep 2
if sudo systemctl is-active --quiet arboris-api; then
    echo -e "${GREEN}✅ 服务运行正常${NC}\n"
    sudo systemctl status arboris-api --no-pager -l | head -20
else
    echo -e "${RED}❌ 服务启动失败${NC}"
    echo -e "${YELLOW}查看错误日志:${NC}"
    sudo journalctl -u arboris-api -n 50 --no-pager
    exit 1
fi

echo -e "\n${GREEN}========== 部署完成！==========${NC}"
echo -e "${GREEN}修复内容:${NC}"
echo -e "  ✅ invoke() 方法现在会优先读取用户的路由配置"
echo -e "  ✅ 查找顺序: 用户路由 → 环境变量 → ai_providers表 → 系统配置"
echo -e "\n${YELLOW}下一步:${NC}"
echo -e "  1. 在前端设置页面配置API密钥: http://$(curl -s ifconfig.me)/settings"
echo -e "  2. 或者在 .env 文件中配置系统级API密钥"
echo -e "  3. 测试AI功能是否正常\n"

