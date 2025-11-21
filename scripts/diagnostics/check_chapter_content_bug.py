#!/usr/bin/env python3
"""
检查第9章为什么保存了Planner的analysis而不是Writer的full_content
"""

import sqlite3
import json

# 连接数据库
conn = sqlite3.connect('/Users/siyu/novelnew/backend/storage/arboris.db')  # 根据实际路径调整
cursor = conn.cursor()

# 查询第9章的版本内容
cursor.execute("""
SELECT 
    c.chapter_number,
    cv.version_label,
    substr(cv.content, 1, 500) as content_preview,
    cv.metadata
FROM chapters c
JOIN chapter_versions cv ON c.id = cv.chapter_id
WHERE c.chapter_number = 9
ORDER BY cv.created_at
""")

print("=" * 80)
print("第9章的版本内容分析")
print("=" * 80)

for row in cursor.fetchall():
    chapter_num, version_label, content_preview, metadata = row
    print(f"\n版本: {version_label}")
    print(f"内容前500字: {content_preview}")
    print(f"\nMetadata: {metadata[:200] if metadata else 'None'}...")
    
    # 分析内容
    if content_preview and content_preview.strip().startswith("{"):
        try:
            parsed = json.loads(content_preview)
            print(f"\n⚠️ 内容是JSON格式！")
            print(f"JSON的keys: {list(parsed.keys())}")
            
            if "analysis" in parsed:
                print(f"❌ BUG确认：保存了Planner的analysis！")
            if "full_content" in parsed:
                print(f"✅ 包含full_content字段")
        except:
            print(f"✅ 内容不是JSON，是正常文本")

conn.close()
