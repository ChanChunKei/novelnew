#!/bin/bash
# 3Agent Full Content 测试工具演示脚本

echo "================================================================================================"
echo "  3Agent Full Content 保存问题 - 测试工具演示"
echo "================================================================================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 函数：打印步骤
print_step() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  步骤 $1: $2${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# 函数：暂停等待用户
pause() {
    if [ "$AUTO_RUN" != "true" ]; then
        echo ""
        echo -e "${YELLOW}按 Enter 继续...${NC}"
        read
    else
        sleep 1
    fi
}

# 检查是否自动运行
AUTO_RUN=false
if [ "$1" == "--auto" ]; then
    AUTO_RUN=true
    echo "🤖 自动运行模式"
else
    echo "📖 交互模式（使用 --auto 参数可自动运行）"
fi

# ============================================================================
# 步骤1：快速检查
# ============================================================================

print_step 1 "快速检查所有章节"

echo ""
echo "📌 使用工具: quick_check_full_content.py"
echo "📌 目的: 快速扫描数据库，发现问题章节"
echo ""
echo "执行命令: python3 quick_check_full_content.py --summary"
echo ""

pause

python3 quick_check_full_content.py --summary

# ============================================================================
# 步骤2：格式检测测试
# ============================================================================

print_step 2 "测试Planner格式检测逻辑"

echo ""
echo "📌 使用工具: test_3agent_full_content_save.py"
echo "📌 目的: 验证检测逻辑是否正确工作"
echo ""
echo "执行命令: python3 test_3agent_full_content_save.py --detection"
echo ""

pause

python3 test_3agent_full_content_save.py --detection

# ============================================================================
# 步骤3：边界测试
# ============================================================================

print_step 3 "边界情况测试"

echo ""
echo "📌 使用工具: test_3agent_full_content_save.py"
echo "📌 目的: 测试各种异常输入情况"
echo ""
echo "执行命令: python3 test_3agent_full_content_save.py --boundary"
echo ""

pause

python3 test_3agent_full_content_save.py --boundary

# ============================================================================
# 步骤4：数据库深度检查
# ============================================================================

print_step 4 "数据库深度检查"

echo ""
echo "📌 使用工具: test_3agent_full_content_save.py"
echo "📌 目的: 检查最近5个章节的详细信息"
echo ""
echo "执行命令: python3 test_3agent_full_content_save.py --db --recent 5"
echo ""

pause

# 检查数据库是否存在
if [ -f "backend/storage/arboris.db" ]; then
    python3 test_3agent_full_content_save.py --db --recent 5
else
    echo -e "${YELLOW}⚠️  数据库文件不存在，跳过此测试${NC}"
fi

# ============================================================================
# 步骤5：调试日志工具预览
# ============================================================================

print_step 5 "调试日志工具预览"

echo ""
echo "📌 使用工具: add_3agent_debug_logging.py"
echo "📌 目的: 查看可以在哪些位置添加调试日志"
echo ""
echo "执行命令: python3 add_3agent_debug_logging.py --preview"
echo ""
echo -e "${YELLOW}注意: 这只是预览，不会修改任何文件${NC}"
echo ""

pause

python3 add_3agent_debug_logging.py --preview

# ============================================================================
# 总结
# ============================================================================

echo ""
echo "================================================================================================"
echo ""
echo -e "${GREEN}✅ 演示完成！${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  测试工具总结"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🔧 可用工具:"
echo ""
echo "  1. quick_check_full_content.py"
echo "     └─ 快速检查章节内容质量"
echo ""
echo "  2. test_3agent_full_content_save.py"
echo "     └─ 综合测试套件（格式检测、数据流、边界测试）"
echo ""
echo "  3. show_latest_generation_flow.py"
echo "     └─ 查看完整的3Agent对话历史"
echo ""
echo "  4. add_3agent_debug_logging.py"
echo "     └─ 自动添加/移除调试日志"
echo ""
echo "  5. diagnose_3agent.py"
echo "     └─ 诊断3Agent生成问题"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  推荐工作流程"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  发现问题章节："
echo "    $ python3 quick_check_full_content.py --summary"
echo ""
echo "  深入分析问题（假设第5章有问题）："
echo "    $ python3 test_3agent_full_content_save.py --flow --chapter 5"
echo ""
echo "  查看生成过程："
echo "    $ python3 show_latest_generation_flow.py"
echo ""
echo "  如需更多信息，添加实时日志："
echo "    $ python3 add_3agent_debug_logging.py --apply"
echo "    $ # 重启后端，生成测试章节，查看日志"
echo "    $ python3 add_3agent_debug_logging.py --remove"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📚 详细文档: 3AGENT_FULL_CONTENT_TEST_GUIDE.md"
echo ""
echo "================================================================================================"
echo ""
