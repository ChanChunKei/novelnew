#!/bin/bash

# Arboris Novel - GitHub推送脚本
# 使用方法: ./push_to_github.sh <your-github-repo-url>

set -e  # 遇到错误立即退出

echo "=========================================="
echo "  Arboris Novel - GitHub推送脚本"
echo "=========================================="
echo ""

# 检查是否提供了仓库URL
if [ -z "$1" ]; then
    echo "❌ 错误: 请提供GitHub仓库URL"
    echo ""
    echo "使用方法:"
    echo "  ./push_to_github.sh https://github.com/yourusername/arboris-novel.git"
    echo ""
    exit 1
fi

REPO_URL="$1"

echo "📋 步骤 1/5: 检查Git状态"
echo "----------------------------------------"
git status
echo ""

echo "⚠️  请确认以下内容:"
echo "  1. 所有敏感文件已被.gitignore忽略"
echo "  2. 没有包含真实的API密钥"
echo "  3. 数据库文件不会被上传"
echo ""
read -p "确认继续? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 已取消操作"
    exit 1
fi

echo ""
echo "📦 步骤 2/5: 添加所有文件到Git"
echo "----------------------------------------"
git add .
echo "✅ 文件已添加"
echo ""

echo "📝 步骤 3/5: 创建提交"
echo "----------------------------------------"
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

Cleanup:
- Removed 31 temporary/debug files
- Updated .gitignore with comprehensive rules
- Added README.md and deployment guides
- Protected sensitive data from being uploaded

Technical Stack:
- Backend: FastAPI + Python 3.11 + SQLite
- Frontend: Vue 3 + TypeScript + Vite
- AI: OpenAI, Anthropic, Google, SiliconFlow
- Automation: Playwright for web scraping
"
echo "✅ 提交已创建"
echo ""

echo "🔗 步骤 4/5: 添加远程仓库"
echo "----------------------------------------"
# 检查是否已存在origin
if git remote | grep -q "^origin$"; then
    echo "⚠️  远程仓库'origin'已存在，将更新URL"
    git remote set-url origin "$REPO_URL"
else
    git remote add origin "$REPO_URL"
fi
echo "✅ 远程仓库已配置: $REPO_URL"
echo ""

echo "🚀 步骤 5/5: 推送到GitHub"
echo "----------------------------------------"
echo "正在推送到远程仓库..."
echo ""

# 尝试推送到main分支
if git push -u origin main 2>/dev/null; then
    echo "✅ 成功推送到main分支"
else
    echo "⚠️  main分支推送失败，尝试master分支..."
    if git push -u origin master 2>/dev/null; then
        echo "✅ 成功推送到master分支"
    else
        echo "❌ 推送失败，请检查:"
        echo "  1. GitHub仓库是否已创建"
        echo "  2. 是否有推送权限"
        echo "  3. 网络连接是否正常"
        echo ""
        echo "手动推送命令:"
        echo "  git push -u origin main"
        echo "  或"
        echo "  git push -u origin master"
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "  ✅ 推送完成！"
echo "=========================================="
echo ""
echo "📊 仓库信息:"
echo "  URL: $REPO_URL"
echo ""
echo "🔗 下一步:"
echo "  1. 访问GitHub仓库查看代码"
echo "  2. 配置GitHub Actions（如需要）"
echo "  3. 设置仓库描述和标签"
echo "  4. 添加LICENSE文件（如需要）"
echo "  5. 开始部署到服务器"
echo ""
echo "📖 部署指南:"
echo "  查看 PRE_DEPLOYMENT_CHECKLIST.md"
echo ""

