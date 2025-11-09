"""
混合模型Agent服务
使用阿里云模型做Agent决策（便宜、RPM高）+ 高质量模型做最终生成
"""
from typing import List, Dict, Any, Optional
import asyncio
from openai import AsyncOpenAI
from http import HTTPStatus
import dashscope
from dashscope import Generation

from app.core.config import settings


class HybridAgentService:
    """混合模型Agent：阿里云做决策 + OpenAI/Claude做生成"""

    def __init__(
        self,
        agent_model: str = "qwen-turbo",  # 阿里云模型做决策
        final_model: str = "gpt-4o",      # 高质量模型做生成
        max_agent_rounds: int = 5          # 最多5轮Agent决策
    ):
        self.agent_model = agent_model
        self.final_model = final_model
        self.max_agent_rounds = max_agent_rounds

        # 阿里云API
        dashscope.api_key = settings.DASHSCOPE_API_KEY

        # OpenAI/Claude API
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    def _get_tools_definition(self) -> List[Dict]:
        """定义Agent可以使用的工具"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_character_info",
                    "description": "获取角色的当前状态、性格特点、关系网络等详细信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "角色名字"
                            },
                            "chapter_num": {
                                "type": "integer",
                                "description": "截止到第几章（获取该章节时角色的状态）"
                            }
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_chapters",
                    "description": "搜索包含特定关键词、情节或角色的历史章节内容",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keyword": {
                                "type": "string",
                                "description": "搜索关键词（可以是情节、地点、事件等）"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回结果数量",
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
                    "name": "get_world_setting",
                    "description": "查询世界观设定、魔法体系、势力关系、地理信息等",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tag": {
                                "type": "string",
                                "description": "设定标签（如：魔法体系、势力关系、地理等）"
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
                    "description": "获取最近N章的完整内容，用于保持剧情连贯性",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "current_chapter": {
                                "type": "integer",
                                "description": "当前章节号"
                            },
                            "count": {
                                "type": "integer",
                                "description": "获取最近几章",
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
                    "name": "check_foreshadowing",
                    "description": "检查是否有未回收的伏笔或悬念",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chapter_range": {
                                "type": "string",
                                "description": "章节范围，如'1-50'"
                            }
                        }
                    }
                }
            }
        ]

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        project_id: str
    ) -> str:
        """执行工具调用"""
        from app.services.novel_service import NovelService

        try:
            if tool_name == "get_character_info":
                # TODO: 实现从数据库查询角色信息
                name = arguments.get("name")
                chapter_num = arguments.get("chapter_num")
                return f"角色【{name}】信息：[暂未实现，需要查询character_states表]"

            elif tool_name == "search_chapters":
                # TODO: 实现章节搜索
                keyword = arguments.get("keyword")
                limit = arguments.get("limit", 3)
                return f"搜索关键词【{keyword}】的章节：[暂未实现，需要实现全文搜索]"

            elif tool_name == "get_world_setting":
                # TODO: 实现世界设定查询
                tag = arguments.get("tag")
                return f"世界设定【{tag}】：[暂未实现，需要查询world_settings表]"

            elif tool_name == "get_recent_chapters":
                # 这个可以直接实现
                current_chapter = arguments.get("current_chapter")
                count = arguments.get("count", 3)

                novel_service = NovelService()
                # TODO: 获取最近N章的内容
                return f"最近{count}章内容：[需要调用NovelService获取]"

            elif tool_name == "check_foreshadowing":
                # TODO: 实现伏笔检查
                chapter_range = arguments.get("chapter_range")
                return f"章节范围【{chapter_range}】的伏笔：[暂未实现]"

            else:
                return f"未知工具：{tool_name}"

        except Exception as e:
            return f"工具执行失败：{str(e)}"

    async def _agent_decision_round(
        self,
        messages: List[Dict],
        tools: List[Dict],
        project_id: str
    ) -> tuple[List[Dict], bool]:
        """
        使用阿里云模型进行一轮Agent决策

        Returns:
            (updated_messages, should_continue)
        """
        try:
            # 使用阿里云通义千问做决策
            response = Generation.call(
                model=self.agent_model,
                messages=messages,
                tools=tools,
                result_format='message'
            )

            if response.status_code != HTTPStatus.OK:
                raise Exception(f"阿里云API调用失败: {response.message}")

            assistant_message = response.output.choices[0].message

            # 检查是否有工具调用
            if hasattr(assistant_message, 'tool_calls') and assistant_message.tool_calls:
                # AI决定要调用工具
                tool_calls = assistant_message.tool_calls

                # 添加assistant消息
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.function.name,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in tool_calls
                    ]
                })

                # 并行执行所有工具调用
                tool_results = await asyncio.gather(*[
                    self._execute_tool(
                        tc.function.name,
                        eval(tc.function.arguments),  # 将JSON字符串转为dict
                        project_id
                    )
                    for tc in tool_calls
                ])

                # 添加工具结果
                for tc, result in zip(tool_calls, tool_results):
                    messages.append({
                        "role": "tool",
                        "name": tc.function.name,
                        "content": result
                    })

                return messages, True  # 继续下一轮

            else:
                # AI认为信息已经足够，不需要更多工具
                return messages, False  # 结束Agent循环

        except Exception as e:
            print(f"Agent决策轮出错: {str(e)}")
            return messages, False

    async def generate_chapter_with_agent(
        self,
        project_id: str,
        chapter_num: int,
        outline: str,
        user_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        使用混合Agent生成章节

        流程：
        1. 使用阿里云模型做多轮Agent决策（查询需要的信息）
        2. 使用高质量模型做最终生成
        """
        tools = self._get_tools_definition()

        # 初始消息
        messages = [{
            "role": "system",
            "content": """你是一个小说创作AI助手。你的任务分为两个阶段：

【阶段1：信息收集】
- 仔细分析用户提供的章节大纲
- 识别需要查询的信息（角色状态、历史情节、世界设定等）
- 使用提供的工具查询必要的信息
- 当你觉得信息足够时，说"信息收集完成"

【阶段2：内容生成】
- 基于收集的信息生成章节内容
- 保持角色性格一致
- 确保情节连贯
- 注意伏笔和细节

现在你处于阶段1，请开始分析大纲并收集信息。"""
        }, {
            "role": "user",
            "content": f"""请为第{chapter_num}章收集必要的信息。

【章节大纲】
{outline}

{f'【用户补充要求】{user_prompt}' if user_prompt else ''}

请分析这个大纲，使用工具查询你需要的信息。当信息足够时，告诉我"信息收集完成"。"""
        }]

        # Agent决策循环（使用阿里云模型）
        agent_logs = []
        for round_num in range(self.max_agent_rounds):
            print(f"\n=== Agent决策第{round_num + 1}轮 (使用{self.agent_model}) ===")

            messages, should_continue = await self._agent_decision_round(
                messages, tools, project_id
            )

            agent_logs.append({
                "round": round_num + 1,
                "model": self.agent_model,
                "message_count": len(messages)
            })

            if not should_continue:
                print(f"Agent在第{round_num + 1}轮决定信息已足够")
                break

        # 构建最终生成的上下文
        context_parts = []
        for msg in messages:
            if msg["role"] == "tool":
                context_parts.append(f"【{msg.get('name', '工具')}查询结果】\n{msg['content']}")

        final_context = "\n\n".join(context_parts)

        # 使用高质量模型生成最终内容
        print(f"\n=== 最终生成 (使用{self.final_model}) ===")

        final_response = await self.openai_client.chat.completions.create(
            model=self.final_model,
            messages=[{
                "role": "system",
                "content": """你是一个专业的小说作家。请基于提供的信息和大纲，创作引人入胜的章节内容。

要求：
- 字数3000-5000字
- 情节紧凑，节奏合理
- 人物性格鲜明，对话自然
- 环境描写生动
- 保持前后一致性"""
            }, {
                "role": "user",
                "content": f"""请创作第{chapter_num}章的内容。

【收集到的信息】
{final_context}

【章节大纲】
{outline}

{f'【用户要求】{user_prompt}' if user_prompt else ''}

请开始创作："""
            }],
            temperature=0.8,
            max_tokens=8000
        )

        chapter_content = final_response.choices[0].message.content

        return {
            "content": chapter_content,
            "agent_logs": agent_logs,
            "agent_rounds": len(agent_logs),
            "agent_model": self.agent_model,
            "final_model": self.final_model,
            "total_api_calls": len(agent_logs) + 1  # Agent轮次 + 最终生成
        }


# 使用示例
async def example_usage():
    """使用示例"""
    service = HybridAgentService(
        agent_model="qwen-turbo",  # 阿里云便宜模型做决策
        final_model="gpt-4o",       # OpenAI好模型做生成
        max_agent_rounds=5          # 最多5轮决策
    )

    result = await service.generate_chapter_with_agent(
        project_id="test_project",
        chapter_num=120,
        outline="张三在决战前夕，回忆起李四的遗言，决定使用禁术",
        user_prompt="重点描写张三的内心挣扎"
    )

    print(f"生成完成！")
    print(f"Agent决策轮次: {result['agent_rounds']}")
    print(f"总API调用: {result['total_api_calls']}")
    print(f"内容长度: {len(result['content'])}字")
    print(f"\n内容预览:\n{result['content'][:200]}...")
