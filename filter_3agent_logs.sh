#!/bin/bash
# 3Agent 日志过滤器
# 用法: ./filter_3agent_logs.sh [日志文件路径]
# 如果不提供文件路径，则从标准输入读取（可用于实时过滤）

# 3Agent 相关的关键词
KEYWORDS=(
    "_build_writer_context"
    "Writer 收到的上下文"
    "写作Agent"
    "思考Agent"
    "审批Agent"
    "总结Agent"
    "Planner"
    "Writer"
    "Reviewer"
    "Summarizer"
    "三Agent"
    "3Agent"
    "agent_dialogue"
    "planner_result"
    "writer_context"
    "full_content"
    "Agent输出"
    "Agent完成"
    "🔧"
    "📤"
    "✍️"
    "🤔"
    "👀"
    "📝"
)

# 构建 grep 模式
PATTERN=$(IFS="|"; echo "${KEYWORDS[*]}")

if [ -z "$1" ]; then
    # 从标准输入读取（实时过滤）
    grep --line-buffered -E "$PATTERN"
else
    # 从文件读取
    grep -E "$PATTERN" "$1"
fi
