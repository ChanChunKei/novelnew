#!/usr/bin/env python3
"""Insert Gemini configuration into database"""

import sqlite3

db_path = "/home/user/novelnew/backend/storage/arboris.db"

# Configuration values
API_KEY = "AIzaSyA5t2XnnCMsCg7SE-odHhX1o5gHIxX2kBQ"
PROVIDER = "gemini"

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
