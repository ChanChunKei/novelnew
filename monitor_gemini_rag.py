#!/usr/bin/env python3
"""
实时监控 Gemini RAG 调用状态

使用方法：
1. 启动后端服务：cd backend && python -m uvicorn app.main:app --reload
2. 在另一个终端运行：python3 monitor_gemini_rag.py
3. 生成章节，观察实时日志
"""

import time
import re
from pathlib import Path

# 日志文件路径（根据实际情况调整）
LOG_PATTERNS = [
    "/home/user/novelnew/backend/logs/app.log",
    "/home/user/novelnew/backend/app.log",
    "/var/log/novelnew.log",
]

# 关键日志模式
GEMINI_PATTERNS = [
    r"✅ Gemini RAG 服务初始化成功",
    r"❌ Gemini RAG 初始化失败",
    r"📚 找到已存在的 Corpus",
    r"✅ 创建 Corpus 成功",
    r"✅ 章节入库成功",
    r"❌ 章节入库失败",
    r"🔍 搜索完成",
    r"❌ 搜索失败",
    r"🗑️  删除 Corpus 成功",
    r"🗑️  删除章节成功",
]

def find_log_file():
    """查找日志文件"""
    for pattern in LOG_PATTERNS:
        log_path = Path(pattern)
        if log_path.exists():
            return log_path
    return None

def tail_log(log_file, follow=True):
    """实时跟踪日志文件"""
    print(f"📝 监控日志文件: {log_file}")
    print("=" * 70)
    print("等待 Gemini RAG 事件...")
    print("提示：启动后端服务并生成章节以查看实时日志")
    print("=" * 70)
    print()

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        # 移到文件末尾
        f.seek(0, 2)

        while follow:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue

            # 检查是否包含 Gemini RAG 相关内容
            for pattern in GEMINI_PATTERNS:
                if re.search(pattern, line):
                    timestamp = time.strftime('%H:%M:%S')
                    print(f"[{timestamp}] {line.strip()}")
                    break

def check_console_output():
    """如果没有日志文件，指导用户查看控制台输出"""
    print("=" * 70)
    print("📋 Gemini RAG 监控指南")
    print("=" * 70)
    print()
    print("未找到日志文件，请按以下步骤监控 Gemini RAG 状态：")
    print()
    print("1️⃣  启动后端服务（会输出详细日志）：")
    print("   cd backend")
    print("   python -m uvicorn app.main:app --reload --log-level info")
    print()
    print("2️⃣  观察启动日志，应该看到：")
    print("   ✅ Gemini RAG 服务初始化成功")
    print()
    print("3️⃣  生成第一章时，日志会显示：")
    print("   📚 找到已存在的 Corpus: corpora/novel-project-xxx")
    print("   或")
    print("   ✅ 创建 Corpus 成功: corpora/novel-project-xxx")
    print("   ✅ 章节入库成功: 第1章 xxx")
    print()
    print("4️⃣  生成第二章时，会先搜索：")
    print("   🔍 搜索完成: 查询='xxx', 结果数=3")
    print("   ✅ 章节入库成功: 第2章 xxx")
    print()
    print("=" * 70)
    print()
    print("🔍 关键日志说明：")
    print()
    print("✅ 成功标记：")
    print("  • ✅ Gemini RAG 服务初始化成功 - API Key 有效，服务启动")
    print("  • ✅ 创建 Corpus 成功 - 为项目创建了新的语料库")
    print("  • ✅ 章节入库成功 - 章节已存入 Gemini Corpus")
    print("  • 🔍 搜索完成 - 成功搜索到相关章节")
    print()
    print("❌ 失败标记：")
    print("  • ❌ Gemini RAG 初始化失败 - API Key 无效或网络问题")
    print("  • ❌ 章节入库失败 - 入库过程出错")
    print("  • ❌ 搜索失败 - 搜索过程出错")
    print()
    print("=" * 70)

def main():
    print()
    print("🚀 Gemini RAG 实时监控工具")
    print()

    log_file = find_log_file()

    if log_file:
        try:
            tail_log(log_file, follow=True)
        except KeyboardInterrupt:
            print("\n\n监控已停止")
    else:
        check_console_output()
        print()
        print("💡 提示：也可以使用 test API 查看状态：")
        print("   curl -X POST http://localhost:8000/api/admin/test-gemini-rag \\")
        print("     -H \"Authorization: Bearer YOUR_TOKEN\" \\")
        print("     -H \"Content-Type: application/json\" \\")
        print("     -d '{}'")
        print()

if __name__ == "__main__":
    main()
