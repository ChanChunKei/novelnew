#!/usr/bin/env python3
"""
检查 Gemini RAG 使用状态

快速查看：
- 配置是否正确
- 有哪些项目使用了 Gemini RAG
- Corpus 创建情况
"""

import sqlite3
import sys
import os

# 设置环境变量以读取配置
sys.path.insert(0, '/home/user/novelnew/backend')
os.environ.setdefault('DB_PROVIDER', 'sqlite')

db_path = "/home/user/novelnew/backend/storage/arboris.db"

def check_database_config():
    """检查数据库配置"""
    print("=" * 70)
    print("📋 步骤 1：检查数据库配置")
    print("=" * 70)

    if not os.path.exists(db_path):
        print(f"❌ 数据库不存在: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT key, value
        FROM system_configs
        WHERE key IN ('gemini.api_key', 'rag.provider')
    """)

    configs = dict(cursor.fetchall())

    api_key = configs.get('gemini.api_key', '')
    provider = configs.get('rag.provider', '')

    print(f"RAG Provider: {provider if provider else '❌ 未配置'}")
    if api_key:
        print(f"Gemini API Key: {api_key[:10]}...{api_key[-4:]} ✅")
    else:
        print("Gemini API Key: ❌ 未配置")

    conn.close()

    if provider == 'gemini' and api_key:
        print("\n✅ 配置正确！Gemini RAG 已启用")
        return True
    else:
        print("\n⚠️  配置不完整或使用其他 RAG 提供方")
        return False

def check_projects():
    """检查项目状态"""
    print("\n" + "=" * 70)
    print("📚 步骤 2：检查项目状态")
    print("=" * 70)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.id,
            p.title,
            p.status,
            COUNT(DISTINCT c.id) as chapter_count,
            p.created_at
        FROM novel_projects p
        LEFT JOIN chapters c ON p.id = c.project_id
        GROUP BY p.id
        ORDER BY p.created_at DESC
        LIMIT 10
    """)

    projects = cursor.fetchall()

    if not projects:
        print("📭 暂无项目")
        print("\n💡 创建项目后，生成章节时会自动创建 Gemini Corpus")
        conn.close()
        return

    print(f"找到 {len(projects)} 个项目：\n")

    for pid, title, status, chapter_count, created_at in projects:
        corpus_name = f"novel-project-{pid}"
        print(f"📖 {title}")
        print(f"   ID: {pid}")
        print(f"   状态: {status}")
        print(f"   章节数: {chapter_count}")
        print(f"   Corpus 名称: {corpus_name}")
        print(f"   创建时间: {created_at}")
        print()

    conn.close()

def check_chapters():
    """检查最近生成的章节"""
    print("=" * 70)
    print("📄 步骤 3：检查最近章节（最近5章）")
    print("=" * 70)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            c.chapter_number,
            p.title as project_title,
            c.status,
            c.word_count,
            c.created_at
        FROM chapters c
        JOIN novel_projects p ON c.project_id = p.id
        ORDER BY c.created_at DESC
        LIMIT 5
    """)

    chapters = cursor.fetchall()

    if not chapters:
        print("📭 暂无章节")
        print("\n💡 生成章节时会自动调用 Gemini RAG：")
        print("   1. 第一章：创建 Corpus + 入库")
        print("   2. 后续章节：搜索相关内容 + 入库")
        conn.close()
        return

    print(f"找到 {len(chapters)} 章最近章节：\n")

    for chapter_num, project_title, status, word_count, created_at in chapters:
        print(f"第 {chapter_num} 章 - {project_title}")
        print(f"   状态: {status}")
        print(f"   字数: {word_count}")
        print(f"   时间: {created_at}")
        print()

    conn.close()

def show_test_commands():
    """显示测试命令"""
    print("=" * 70)
    print("🧪 步骤 4：如何验证 Gemini RAG 工作")
    print("=" * 70)
    print()
    print("方法1：查看后端日志（推荐）")
    print("-------")
    print("启动服务：")
    print("  cd backend")
    print("  python -m uvicorn app.main:app --reload --log-level info")
    print()
    print("生成章节后，日志会显示：")
    print("  ✅ Gemini RAG 服务初始化成功")
    print("  ✅ 创建 Corpus 成功: corpora/novel-project-xxx")
    print("  ✅ 章节入库成功: 第1章 xxx")
    print("  🔍 搜索完成: 查询='xxx', 结果数=3")
    print()
    print("方法2：使用测试 API")
    print("-------")
    print("  # 1. 登录获取 Token")
    print("  TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \\")
    print("    -H \"Content-Type: application/json\" \\")
    print("    -d '{\"username\":\"admin\",\"password\":\"your-password\"}' \\")
    print("    | jq -r '.access_token')")
    print()
    print("  # 2. 测试 Gemini RAG")
    print("  curl -X POST http://localhost:8000/api/admin/test-gemini-rag \\")
    print("    -H \"Authorization: Bearer $TOKEN\" \\")
    print("    -H \"Content-Type: application/json\" \\")
    print("    -d '{}' | jq")
    print()
    print("方法3：查看 Google AI Studio")
    print("-------")
    print("  访问 https://aistudio.google.com/app/apikey")
    print("  查看 API 使用统计（如果有调用，会显示请求数）")
    print()

def main():
    print()
    print("🔍 Gemini RAG 状态检查工具")
    print()

    # 检查配置
    config_ok = check_database_config()

    # 检查项目
    check_projects()

    # 检查章节
    check_chapters()

    # 显示测试方法
    show_test_commands()

    print("=" * 70)
    if config_ok:
        print("✅ 配置完成！按照上述方法测试即可验证 Gemini RAG 是否工作")
    else:
        print("⚠️  请先完成配置，运行 python3 insert_config.py")
    print("=" * 70)
    print()

if __name__ == "__main__":
    main()
