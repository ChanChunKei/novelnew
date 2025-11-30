"""
Agent工具配置

定义小说生成Agent可以使用的Function Calling工具
这些工具允许AI主动查询历史信息、角色状态等
"""

from typing import List, Dict, Any


def get_reviewer_tools() -> List[Dict[str, Any]]:
    """
    获取审批Agent专用的验证工具

    这些工具允许Reviewer主动验证Writer的输出是否符合设定：
    - verify_character_action: 验证角色行为是否符合设定
    - verify_timeline: 验证时间线是否正确
    - verify_world_rules: 验证是否违反世界观规则
    - search_chapters: 搜索历史章节验证细节

    Returns:
        工具定义列表
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "verify_character_action",
                "description": "验证角色的行为是否符合其设定和历史表现。用于检查是否OOC（Out of Character）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "character_name": {
                            "type": "string",
                            "description": "角色名称"
                        },
                        "action_description": {
                            "type": "string",
                            "description": "角色在本章中的行为描述，如'张三主动向敌人求饶'"
                        },
                        "context": {
                            "type": "string",
                            "description": "行为发生的上下文，如'被敌人包围时'"
                        }
                    },
                    "required": ["character_name", "action_description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "verify_timeline",
                "description": "验证时间线是否正确，检查事件顺序和时间跨度是否合理。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "events": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "需要验证的事件列表，如['张三昨天受伤', '张三今天参加比武']"
                        },
                        "chapter_range": {
                            "type": "string",
                            "description": "检查的章节范围，如'10-15'",
                            "default": "recent"
                        }
                    },
                    "required": ["events"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "verify_world_rules",
                "description": "验证是否违反世界观规则，如凡人不能飞、魔法需要咒语等。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "actions_to_verify": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "需要验证的动作列表，如['主角瞬间移动到敌人身后', '凡人飞上天空']"
                        }
                    },
                    "required": ["actions_to_verify"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_chapters",
                "description": "搜索历史章节验证细节一致性，如角色受伤状态、物品持有情况等。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "搜索关键词，如角色名、物品名、地点等"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回结果数量，默认3条",
                            "default": 3
                        }
                    },
                    "required": ["keyword"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_character_state",
                "description": "获取角色当前状态（位置、伤势、持有物品、情绪等）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "character_name": {
                            "type": "string",
                            "description": "角色名称"
                        },
                        "chapter_number": {
                            "type": "integer",
                            "description": "可选：截至该章节的最新状态"
                        }
                    },
                    "required": ["character_name"]
                }
            }
        }
    ]


# Reviewer专用工具
REVIEWER_TOOLS = get_reviewer_tools()


def get_novel_agent_tools() -> List[Dict[str, Any]]:
    """
    获取小说生成Agent的工具定义

    ✅ 优化说明：已移除冗余工具（get_character_state, get_world_setting, get_recent_chapters）
    因为这些信息已在上下文的 volumes_snapshot 和 previous_chapters_text 中提供。

    保留的工具：
    - search_chapters: 查找摘要中遗漏的细节和远距离内容
    - check_plot_consistency: 检查剧情前后矛盾
    - find_foreshadowing: 查找未回收的伏笔

    这些工具遵循OpenAI Function Calling格式
    也兼容Gemini、Claude等支持工具调用的模型

    Returns:
        工具定义列表
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "search_chapters",
                "description": "搜索历史章节中包含特定关键词的内容片段。用于：1) 查找摘要中遗漏的细节描写；2) 引用远早于前两章的内容；3) 保持对人物/地点/物品描写的一致性。注意：角色信息和世界观已在上下文的volumes_snapshot中提供，优先使用上下文！",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "搜索关键词，如角色名、地点、物品名、事件等"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回结果数量，默认3条",
                            "default": 3
                        }
                    },
                    "required": ["keyword"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_plot_consistency",
                "description": "检查剧情是否存在前后矛盾，如时间线错乱、人物设定冲突等。用于确保剧情逻辑严谨。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "check_items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "需要检查的项目列表，如['张三的年龄', '王朝的建立时间']"
                        }
                    },
                    "required": ["check_items"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_foreshadowing",
                "description": "查找未回收的伏笔和悬念，帮助AI决定是否在本章回收某些伏笔，增强故事连贯性。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chapter_range": {
                            "type": "string",
                            "description": "章节范围，如'1-50'表示第1到50章"
                        }
                    }
                }
            }
        }
    ]


# 为了方便使用，提供一个常量
NOVEL_AGENT_TOOLS = get_novel_agent_tools()
