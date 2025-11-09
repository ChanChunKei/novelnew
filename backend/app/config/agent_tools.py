"""
Agent工具配置

定义小说生成Agent可以使用的Function Calling工具
这些工具允许AI主动查询历史信息、角色状态等
"""

from typing import List, Dict, Any


def get_novel_agent_tools() -> List[Dict[str, Any]]:
    """
    获取小说生成Agent的工具定义

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
                "description": "搜索历史章节中包含特定关键词或情节的内容。可以查找角色、地点、事件等相关章节。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "搜索关键词，如角色名、地点、事件等"
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
                "description": "获取指定角色在某个章节时的状态信息，包括：性格特点、能力值、关系网络、心理状态等。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "角色名字"
                        },
                        "chapter_number": {
                            "type": "integer",
                            "description": "截止到第几章（获取该章节时角色的状态），不指定则获取最新状态"
                        }
                    },
                    "required": ["name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_world_setting",
                "description": "查询世界观设定、魔法体系、势力关系、地理信息等背景设定。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tag": {
                            "type": "string",
                            "description": "设定标签，如：魔法体系、势力关系、地理、历史背景等"
                        }
                    },
                    "required": ["tag"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_recent_chapters",
                "description": "获取最近N章的完整内容，用于了解最新剧情和保持连贯性。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "current_chapter": {
                            "type": "integer",
                            "description": "当前要生成的章节号"
                        },
                        "count": {
                            "type": "integer",
                            "description": "获取最近几章，默认3章",
                            "default": 3
                        }
                    },
                    "required": ["current_chapter"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_plot_consistency",
                "description": "检查剧情是否存在前后矛盾，如时间线错乱、人物设定冲突等。",
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
                "description": "查找未回收的伏笔和悬念，帮助AI决定是否在本章回收某些伏笔。",
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
