#!/usr/bin/env python3
"""
Insert Gemini configuration into database

使用方法：
  python3 insert_config.py [数据库路径] [API_KEY] [PROVIDER]

示例：
  python3 insert_config.py                                          # 使用默认值
  python3 insert_config.py /path/to/db.db                          # 指定数据库
  python3 insert_config.py /path/to/db.db AIzaSy... gemini        # 全部指定
"""

import sqlite3
import sys
from pathlib import Path

def find_database():
    """自动查找数据库"""
    candidates = ["backend/storage/arboris.db", "storage/arboris.db", "arboris.db"]
    for candidate in candidates:
        db_file = Path.cwd() / candidate
        if db_file.exists():
            return str(db_file)
    return None

# 解析参数
db_path = sys.argv[1] if len(sys.argv) > 1 else find_database()
API_KEY = sys.argv[2] if len(sys.argv) > 2 else "AIzaSyA5t2XnnCMsCg7SE-odHhX1o5gHIxX2kBQ"
PROVIDER = sys.argv[3] if len(sys.argv) > 3 else "gemini"

if not db_path:
    print("❌ 未找到数据库，请指定路径")
    print("使用方法：python3 insert_config.py /path/to/arboris.db")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("📝 Inserting Gemini configuration...")
print()

# Insert or update gemini.api_key
cursor.execute("""
    INSERT OR REPLACE INTO system_configs (key, value, description)
    VALUES (?, ?, ?)
""", (
    'gemini.api_key',
    API_KEY,
    'Google Gemini API Key，格式 AIzaSy...，用于 Semantic Retrieval RAG 搜索'
))

# Insert or update rag.provider
cursor.execute("""
    INSERT OR REPLACE INTO system_configs (key, value, description)
    VALUES (?, ?, ?)
""", (
    'rag.provider',
    PROVIDER,
    'RAG 检索提供方：gemini (Google 托管) 或 libsql (本地向量库)，默认 libsql'
))

conn.commit()

# Verify insertion
print("📋 Verification:")
print("=" * 60)

cursor.execute("""
    SELECT key, value, description
    FROM system_configs
    WHERE key IN ('gemini.api_key', 'rag.provider')
    ORDER BY key
""")

rows = cursor.fetchall()
for key, value, desc in rows:
    # Mask API key for display
    if key == 'gemini.api_key' and value:
        display_value = f"{value[:10]}...{value[-4:]}"
    else:
        display_value = value
    print(f"✅ {key}: {display_value}")

conn.close()

print()
print("✅ Configuration inserted successfully!")
