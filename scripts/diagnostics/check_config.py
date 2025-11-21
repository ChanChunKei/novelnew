#!/usr/bin/env python3
"""
Check Gemini configuration in database

使用方法：
  python3 check_config.py [数据库路径]
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

db_path = sys.argv[1] if len(sys.argv) > 1 else find_database()
if not db_path:
    print("❌ 未找到数据库，请指定路径：python3 check_config.py /path/to/arboris.db")
    sys.exit(1)

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
