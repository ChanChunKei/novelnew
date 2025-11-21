#!/usr/bin/env python3
"""使用sqlite3模块检查未完成灵感项目的运行中任务"""
import sqlite3
import json
from pathlib import Path

# 数据库路径
db_path = Path(__file__).parent / "backend" / "data.db"

if not db_path.exists():
    print(f"❌ 数据库文件不存在: {db_path}")
    exit(1)

# 连接数据库
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row  # 使用字典形式访问
cursor = conn.cursor()

print("="*60)
print("🔍 检查未完成灵感项目的自动生成任务")
print("="*60)
print()

# 1. 获取所有活跃任务
cursor.execute("""
    SELECT id, project_id, status, chapters_generated, created_at
    FROM auto_generator_tasks
    WHERE status IN ('pending', 'running', 'paused')
    ORDER BY created_at DESC
""")
active_tasks = cursor.fetchall()

print(f"📊 总共有 {len(active_tasks)} 个活跃任务\n")

if not active_tasks:
    print("✅ 没有活跃任务")
    conn.close()
    exit(0)

# 2. 检查每个任务对应的项目是否有章节大纲
invalid_tasks = []

for task in active_tasks:
    task_id = task['id']
    project_id = task['project_id']
    status = task['status']
    chapters_generated = task['chapters_generated']
    created_at = task['created_at']

    # 获取项目信息
    cursor.execute("SELECT id, title FROM novel_projects WHERE id = ?", (project_id,))
    project = cursor.fetchone()

    if not project:
        print(f"⚠️  任务 #{task_id} 的项目 {project_id} 不存在")
        invalid_tasks.append({
            'task_id': task_id,
            'project_id': project_id,
            'reason': '项目不存在'
        })
        continue

    project_title = project['title']

    # 检查章节大纲数量
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM chapter_outlines
        WHERE project_id = ?
    """, (project_id,))
    outline_count = cursor.fetchone()['count']

    if outline_count == 0:
        print(f"❌ 发现无效任务！")
        print(f"   任务ID: {task_id}")
        print(f"   项目ID: {project_id}")
        print(f"   项目标题: {project_title}")
        print(f"   任务状态: {status}")
        print(f"   已生成章节: {chapters_generated}")
        print(f"   章节大纲数量: {outline_count} ❌")
        print(f"   创建时间: {created_at}")
        print()

        invalid_tasks.append({
            'task_id': task_id,
            'project_id': project_id,
            'project_title': project_title,
            'status': status,
            'chapters_generated': chapters_generated,
            'outline_count': outline_count,
            'reason': '无章节大纲'
        })
    else:
        print(f"✅ 任务 #{task_id} - 项目 '{project_title}' - 有 {outline_count} 个大纲 - 状态: {status}")

print(f"\n{'='*60}")
print(f"📈 统计结果：")
print(f"   总活跃任务数: {len(active_tasks)}")
print(f"   有效任务数: {len(active_tasks) - len(invalid_tasks)}")
print(f"   无效任务数: {len(invalid_tasks)} ❌")

if invalid_tasks:
    print(f"\n⚠️  发现 {len(invalid_tasks)} 个无效任务需要处理！")
    print(f"\n📋 无效任务列表：")
    for task in invalid_tasks:
        print(f"   - 任务 #{task['task_id']}: {task.get('project_title', task['project_id'])} ({task['reason']})")

    print(f"\n💡 建议操作：")
    print(f"   运行清理脚本停止这些无效任务：")
    print(f"   python cleanup_invalid_tasks_simple.py")
else:
    print(f"\n✅ 所有活跃任务都是有效的！")

conn.close()
