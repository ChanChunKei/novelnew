"""
蓝图自动生成服务

支持两种模式：
1. Creative Expansion: 基于简短创意扩展生成完整蓝图
2. Reference Learning: 基于参考书提取元特征并生成原创蓝图
"""

import json
import logging
import re
from typing import Dict, Optional, Any
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ..services.llm_service import LLMService
from ..core.config import settings

logger = logging.getLogger(__name__)


class BlueprintGeneratorService:
    """蓝图自动生成服务"""

    def __init__(self, session: AsyncSession, llm_service: Optional[LLMService] = None):
        self._llm_service = llm_service or LLMService(session)
        self._prompts_dir = Path(__file__).parent.parent.parent / "prompts"

    async def generate_blueprint(
        self,
        mode: str,
        user_id: int,
        creative_input: Optional[Dict] = None,
        reference_input: Optional[Dict] = None,
    ) -> Dict:
        """
        生成蓝图

        Args:
            mode: "creative" 或 "reference"
            user_id: 用户ID
            creative_input: 创意扩展模式的输入
            reference_input: 参考学习模式的输入

        Returns:
            Dict: {
                "mode": str,
                "blueprint": Dict,
                "plagiarism_check": Dict (仅reference模式)
            }
        """
        if mode == "creative":
            if not creative_input:
                raise ValueError("creative_input is required for creative mode")
            blueprint = await self._generate_creative(creative_input, user_id)
            return {
                "mode": "creative",
                "blueprint": blueprint
            }
        elif mode == "reference":
            if not reference_input:
                raise ValueError("reference_input is required for reference mode")
            result = await self._generate_reference(reference_input, user_id)
            return {
                "mode": "reference",
                "blueprint": result["generated_blueprint"],
                "meta_features": result["meta_features_extracted"],
                "plagiarism_check": result["plagiarism_check"]
            }
        elif mode == "agent":
            if not creative_input:
                raise ValueError("creative_input is required for agent mode")
            blueprint = await self._generate_agent_mode(
                creative_input=creative_input,
                reference_input=reference_input,
                user_id=user_id,
            )
            return {
                "mode": "agent",
                "blueprint": blueprint,
            }
        else:
            raise ValueError(f"Unknown mode: {mode}")

    async def _generate_creative(self, input_data: Dict, user_id: int) -> Dict:
        """
        创意扩展模式：基于简短创意生成完整蓝图

        Args:
            input_data: {
                "idea": str,  # 核心创意
                "genre": str,  # 题材
                "style": str,  # 风格
                "target_length": str  # 目标长度
            }
        """
        logger.info(f"[BlueprintGenerator] 创意扩展模式，创意：{input_data.get('idea', '')[:100]}")

        # 读取提示词模板
        prompt_path = self._prompts_dir / "blueprint_creative.md"
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()

        # 替换模板变量
        prompt = prompt_template.format(
            idea=input_data.get("idea", ""),
            genre=input_data.get("genre", "未指定"),
            style=input_data.get("style", "未指定"),
            target_length=input_data.get("target_length", "未指定")
        )

        # 调用LLM生成
        response = await self._llm_service.get_llm_response(
            system_prompt="你是一位资深的网络小说编辑和创意策划师。",
            conversation_history=[{"role": "user", "content": prompt}],
            temperature=0.8,
            user_id=user_id,
            timeout=120.0
        )

        # 解析JSON响应
        blueprint = self._parse_blueprint_response(response)
        return blueprint

    async def _generate_agent_mode(
        self,
        creative_input: Dict,
        reference_input: Optional[Dict],
        user_id: int,
    ) -> Dict:
        """
        讨论式（agent）模式：Brainstormer → Synthesizer 两轮生成蓝图
        """
        idea = creative_input.get("idea", "")
        genre = creative_input.get("genre", "未指定")
        style = creative_input.get("style", "未指定")
        target_length = creative_input.get("target_length", "未指定")

        # 准备参考文本（可选）
        reference_context = ""
        if reference_input and reference_input.get("reference_book"):
            ref_book = reference_input["reference_book"]
            if ref_book.get("type") == "book_name":
                reference_context = await self._get_reference_book_by_name(ref_book.get("content", ""))
            else:
                reference_context = ref_book.get("content", "")
            reference_context = (reference_context or "")[:5000]

        # 1) Brainstormer
        brainstorm_prompt_path = self._prompts_dir / "blueprint_brainstormer.md"
        with open(brainstorm_prompt_path, "r", encoding="utf-8") as f:
            brainstorm_template = f.read()

        brainstorm_prompt = brainstorm_template.format(
            idea=idea,
            genre=genre,
            style=style,
            target_length=target_length,
            reference_context=reference_context or "无",
        )

        brainstorm_resp = await self._llm_service.get_llm_response(
            system_prompt="你是网文策划Brainstormer，提供多套原创蓝图思路。",
            conversation_history=[{"role": "user", "content": brainstorm_prompt}],
            temperature=0.85,
            user_id=user_id,
            timeout=120.0,
        )
        brainstorm_data = self._parse_json_response(brainstorm_resp)

        # 2) Synthesizer
        synth_prompt_path = self._prompts_dir / "blueprint_synthesizer.md"
        with open(synth_prompt_path, "r", encoding="utf-8") as f:
            synth_template = f.read()

        synth_prompt = synth_template.format(
            idea=idea,
            genre=genre,
            style=style,
            target_length=target_length,
            reference_context=reference_context or "无",
            brainstorm_options=json.dumps(brainstorm_data, ensure_ascii=False),
        )

        synth_resp = await self._llm_service.get_llm_response(
            system_prompt="你是蓝图整合者，负责选取/混合方案并输出完整蓝图。",
            conversation_history=[{"role": "user", "content": synth_prompt}],
            temperature=0.65,
            user_id=user_id,
            timeout=180.0,
        )

        blueprint_raw = self._parse_json_response(synth_resp)
        blueprint = self._normalize_blueprint(blueprint_raw)
        return blueprint

    async def _generate_reference(self, input_data: Dict, user_id: int) -> Dict:
        """
        参考学习模式：基于参考书生成原创蓝图

        Args:
            input_data: {
                "reference_book": {
                    "type": "book_name" | "upload",
                    "content": str  # 书名或文本内容
                },
                "custom_requirements": str  # 自定义要求
            }
        """
        logger.info(f"[BlueprintGenerator] 参考学习模式")

        reference_book = input_data.get("reference_book", {})
        book_type = reference_book.get("type", "book_name")
        book_content = reference_book.get("content", "")
        custom_requirements = input_data.get("custom_requirements", "")

        # 获取参考书文本
        if book_type == "book_name":
            # 使用预设的参考书库
            reference_text = await self._get_reference_book_by_name(book_content)
        else:
            # 用户上传的文本
            reference_text = book_content

        if not reference_text:
            raise ValueError(f"无法获取参考书内容: {book_content}")

        # 读取提示词模板
        prompt_path = self._prompts_dir / "blueprint_reference.md"
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()

        # 替换模板变量
        prompt = prompt_template.format(
            reference_content=reference_text[:5000],  # 限制长度避免超token
            custom_requirements=custom_requirements or "无特殊要求"
        )

        # 调用LLM生成
        response = await self._llm_service.get_llm_response(
            system_prompt="你是一位资深的网络小说编辑和创意策划师。",
            conversation_history=[{"role": "user", "content": prompt}],
            temperature=0.8,
            user_id=user_id,
            timeout=180.0
        )

        # 解析JSON响应
        result = self._parse_reference_response(response)

        # 进行抄袭检测
        plagiarism_check = await self._check_plagiarism(
            result["generated_blueprint"],
            reference_text
        )

        result["plagiarism_check"] = plagiarism_check
        return result

    async def _get_reference_book_by_name(self, book_name: str) -> str:
        """
        根据书名获取参考书简介/大纲

        目前使用硬编码的经典网文简介，后续可扩展为从数据库或API获取
        """
        reference_books = {
            "斗破苍穹": """
                《斗破苍穹》是一部东方玄幻小说，主要讲述了天才少年萧炎因家族变故跌入谷底，后凭借神秘戒指中的药老指导重新崛起的故事。
                
                世界观：斗气大陆，修炼斗气，分为斗之气、斗者、斗师、大斗师、斗灵、斗王、斗皇、斗宗、斗尊、斗圣、斗帝共11个大境界。
                
                主要角色：萧炎（主角，废材逆袭）、药老（导师，灵魂状态）、萧薰儿（红颜，古族天才）、纳兰嫣然（退婚对象）、萧炎父亲（萧战，家族族长）
                
                主线：萧炎幼时天赋异禀，12岁时修为突然停滞被视为废材。后发现母亲遗物戒指中藏有药尊者灵魂，获得炼药术和异火知识。萧炎立志三年之约击败纳兰嫣然，之后踏上寻找异火、提升实力、复兴家族、探寻身世之谜的道路。
                
                风格：热血爽文，主角不断突破，打脸反派，收服异火，炼制丹药，最终成为斗帝。
                
                节奏：前30章家族变故+立志，30-100章加玛帝国历练，100-300章云岚宗三年之约+迦南学院，300-500章中州大陆+丹塔,500-1000章古族+魂族+最终决战。
                
                伏笔密度：约每10-15章埋设一个伏笔，如异火榜单、药老身份、萧炎母亲身世、魂族阴谋等。
            """,
            "遮天": """
                《遮天》是一部东方玄幻小说，讲述地球青年叶凡意外来到修行世界，以凡体踏上成帝之路的故事。
                
                世界观：宇宙星空，修行境界包括轮海、道宫、四极、化龙、仙台（共五大秘境），每个秘境又分多个小境界。
                
                主要角色：叶凡（主角，荒古圣体）、黑皇（狗，前主人为大帝）、庞博（兄弟，妖族血脉）、紫霞（红颜，摇光圣女）
                
                主线：叶凡等九人被九龙拉棺带到北斗星域，发现自己拥有荒古圣体体质。在修行路上不断探索古代秘密，寻找回家之路，对抗禁区至尊，最终证道成仙。
                
                风格：史诗宏大，伏笔众多，世界观庞大，涉及多个宇宙时代。
                
                节奏：前50章北斗初探，50-200章圣体崛起，200-500章各大圣地争霸，500-1000章宇宙星空+成帝之路。
                
                伏笔密度：极高，几乎每5-10章有一个伏笔，如九龙拉棺真相、荒古时代秘密、不死天皇、成仙路等。
            """,
            "凡人修仙传": """
                《凡人修仙传》是一部仙侠修真小说，讲述普通山村少年韩立凭借坚韧意志和谨慎性格在修仙界一步步成长的故事。
                
                世界观：修仙世界，境界包括炼气、筑基、结丹、元婴、化神、炼虚、合体、大乘、渡劫、真仙。
                
                主要角色：韩立（主角，谨慎型）、南宫婉（红颜，早期）、紫灵（红颜，中期）、银月（器灵，陪伴）
                
                主线：韩立因家贫被送入七玄门，拜入墨大夫门下学医。发现墨大夫修仙后被迫服下毒药控制，误打误撞获得小绿瓶（催熟灵药）。韩立凭借小绿瓶和谨慎性格在修仙界步步为营，最终飞升仙界。
                
                风格：谨慎流，主角不莽撞，善于布局，重视机缘和资源积累。
                
                节奏：前100章炼气期打基础，100-300章筑基结丹，300-600章元婴化神，600-1000章炼虚合体，1000+渡劫飞升。
                
                伏笔密度：中等，约每20-30章一个伏笔，如小绿瓶来历、掌天瓶真相、真仙界等。
            """
        }

        return reference_books.get(book_name, "")

    async def _check_plagiarism(self, generated_blueprint: Dict, reference_text: str) -> Dict:
        """
        抄袭检测

        检测维度：
        1. 角色名相似度
        2. 文本相似度（简单的关键词重合检测）

        Returns:
            {
                "passed": bool,
                "overall_similarity": float,
                "name_similarity": float,
                "details": str
            }
        """
        # 1. 提取生成蓝图中的角色名
        generated_names = set()
        for char in generated_blueprint.get("characters", []):
            generated_names.add(char.get("name", ""))

        # 2. 提取参考文本中的可能角色名（简单的正则匹配）
        # 匹配2-4个中文字符，用作角色名
        reference_names = set(re.findall(r'[\u4e00-\u9fa5]{2,4}', reference_text))

        # 3. 计算角色名相似度（编辑距离）
        name_similarity = self._calculate_name_similarity(generated_names, reference_names)

        # 4. 提取关键文本计算相似度
        generated_text = self._extract_blueprint_text(generated_blueprint)
        text_similarity = self._calculate_text_similarity(generated_text, reference_text)

        # 5. 综合判断
        overall_similarity = (name_similarity * 0.5 + text_similarity * 0.5)
        passed = overall_similarity < 0.3 and name_similarity < 0.5

        return {
            "passed": passed,
            "overall_similarity": round(overall_similarity, 2),
            "name_similarity": round(name_similarity, 2),
            "text_similarity": round(text_similarity, 2),
            "details": f"综合相似度{overall_similarity:.1%}（角色名{name_similarity:.1%}，文本{text_similarity:.1%}）"
        }

    def _calculate_name_similarity(self, names1: set, names2: set) -> float:
        """计算两组名字的相似度（简单的交集比例）"""
        if not names1 or not names2:
            return 0.0
        intersection = names1 & names2
        union = names1 | names2
        return len(intersection) / len(union) if union else 0.0

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        简单的文本相似度计算（基于关键词重合）

        注：生产环境建议使用 TF-IDF + Cosine Similarity
        """
        # 提取中文词汇（简单分词）
        words1 = set(re.findall(r'[\u4e00-\u9fa5]{2,}', text1))
        words2 = set(re.findall(r'[\u4e00-\u9fa5]{2,}', text2))

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union) if union else 0.0

    def _extract_blueprint_text(self, blueprint: Dict) -> str:
        """从蓝图中提取关键文本"""
        texts = []
        texts.append(blueprint.get("one_sentence_summary", ""))
        
        world_setting = blueprint.get("world_setting", {})
        texts.append(world_setting.get("background", ""))
        texts.append(world_setting.get("power_system", ""))
        
        for char in blueprint.get("characters", []):
            texts.append(char.get("identity", ""))
            texts.append(char.get("personality", ""))
        
        for phase in blueprint.get("plot_timeline", []):
            texts.append(phase.get("core_conflict", ""))
        
        return " ".join(texts)

    def _parse_blueprint_response(self, response: str) -> Dict:
        """解析创意扩展模式的响应"""
        # 尝试提取JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                blueprint = json.loads(json_match.group(0))
                return blueprint
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {e}")
                raise ValueError(f"生成的蓝图格式不正确: {e}")
        else:
            raise ValueError("响应中未找到有效的JSON")

    def _parse_reference_response(self, response: str) -> Dict:
        """解析参考学习模式的响应"""
        # 提取JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                # 验证必要字段
                if "meta_features_extracted" not in result or "generated_blueprint" not in result:
                    raise ValueError("响应缺少必要字段")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {e}")
                raise ValueError(f"生成的结果格式不正确: {e}")
        else:
            raise ValueError("响应中未找到有效的JSON")

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """从任意文本中提取JSON，失败则抛错"""
        stripped = text.strip()
        if stripped.startswith("{"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError as e:
                logger.error(f"解析JSON失败: {e}")
        raise ValueError("未能从模型输出中解析有效的JSON")

    def _normalize_blueprint(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """填充必需字段，确保结构完整"""

        def ensure_list(val):
            return val if isinstance(val, list) else []

        def ensure_dict(val):
            return val if isinstance(val, dict) else {}

        blueprint = {
            "one_sentence_summary": data.get("one_sentence_summary", ""),
            "innovation": data.get("innovation", ""),
            "world_setting": ensure_dict(data.get("world_setting")),
            "characters": ensure_list(data.get("characters")),
            "plot_timeline": ensure_list(data.get("plot_timeline")),
            "foreshadowing_plan": ensure_list(data.get("foreshadowing_plan")),
            "emotional_arcs": ensure_list(data.get("emotional_arcs")),
        }

        ws = blueprint["world_setting"]
        ws.setdefault("background", "")
        ws.setdefault("power_system", "")
        ws.setdefault("rules", ensure_list(ws.get("rules")))
        ws.setdefault("factions", ensure_list(ws.get("factions")))

        return blueprint
