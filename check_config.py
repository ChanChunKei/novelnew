#!/usr/bin/env python3
"""Check Gemini configuration in database"""

import sqlite3

db_path = "/home/user/novelnew/backend/storage/arboris.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Query system_configs
print("📋 System Configurations:")
print("=" * 60)

cursor.execute("""
    SELECT key, value, description
    FROM system_configs
    WHERE key IN ('gemini.api_key', 'rag.provider')
    ORDER BY key
""")

rows = cursor.fetchall()
if rows:
    for key, value, desc in rows:
        # Mask API key for display
        if key == 'gemini.api_key' and value:
            display_value = f"{value[:10]}...{value[-4:]}"
        else:
            display_value = value
        print(f"Key: {key}")
        print(f"Value: {display_value}")
        print(f"Description: {desc}")
        print()
else:
    print("⚠️  No Gemini configurations found")

conn.close()

print("✅ Configuration check complete")
