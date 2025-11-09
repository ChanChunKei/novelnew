"""
AI去味服务

功能：将AI生成的文本改写得更像人类作家的手笔
- 去除AI痕迹（工整的排比句、重复的修辞手法、刻意的对称结构）
- 增加人性化（口语化表达、不完美的细节、适度的随意性）
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..config.ai_function_config import AIFunctionType
from .ai_orchestrator import AIOrchestrator

logger = logging.getLogger(__name__)


# AI去味提示词（参考MuMuAINovel）
AI_DENOISING_PROMPT = """你是一位追求自然写作风格的编辑。
你的任务是将AI生成的文本改写得更像人类作家的手笔。

原文：
{original_text}

修改要求：
1. 去除AI痕迹：
   - 删除过于工整的排比句
   - 减少重复的修辞手法
   - 去掉刻意的对称结构
   - 避免机械式的总结陈词
   - 减少"仿佛"、"似乎"、"宛如"等AI常用词

2. 增加人性化：
   - 使用更口语化的表达
   - 添加不完美的细节
   - 保留适度的随意性
   - 增加真实的情感波动
   - 使用更多短句和碎片化表达

3. 保持原意：
   - 不改变核心剧情
   - 不改变人物性格
   - 不改变场景设定
   - 保持原文长度（±10%）

4. 输出格式：
   - 直接输出改写后的文本
   - 不要添加任何说明或注释
   - 不要使用markdown格式
   - 保持原文的段落结构

请开始改写："""


class AIDenoisingService:
    """AI去味服务"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.orchestrator = AIOrchestrator(session)

    async def denoise_text(
        self,
        original_text: str,
        user_id: int,
        timeout: Optional[float] = None,
    ) -> str:
        """
        对AI生成的文本进行去味处理
        
        Args:
            original_text: 原始文本
            user_id: 用户ID
            timeout: 超时时间（秒）
        
        Returns:
            去味后的文本（如果失败则返回原文）
        """
        if not original_text or not original_text.strip():
            logger.warning("AI去味：原文为空，返回原文")
            return original_text

        try:
            logger.info(f"AI去味：开始处理，原文长度={len(original_text)}")
            
            # 构建提示词
            prompt = AI_DENOISING_PROMPT.format(original_text=original_text)
            
            # 调用AI路由
            response = await self.orchestrator.route_request(
                function_type=AIFunctionType.AI_DENOISING,
                system_prompt="你是一位追求自然写作风格的编辑。",
                user_prompt=prompt,
                user_id=user_id,
                timeout=timeout or 60.0,
            )
            
            if not response or not response.strip():
                logger.warning("AI去味：返回内容为空，使用原文")
                return original_text
            
            denoised_text = response.strip()
            
            # 检查长度变化
            original_len = len(original_text)
            denoised_len = len(denoised_text)
            length_change = abs(denoised_len - original_len) / original_len * 100
            
            logger.info(
                f"AI去味：完成，原文长度={original_len}，"
                f"去味后长度={denoised_len}，"
                f"长度变化={length_change:.1f}%"
            )
            
            # 如果长度变化过大（超过50%），可能是AI理解错误，返回原文
            if length_change > 50:
                logger.warning(
                    f"AI去味：长度变化过大（{length_change:.1f}%），"
                    f"可能是AI理解错误，返回原文"
                )
                return original_text
            
            return denoised_text
            
        except Exception as e:
            logger.error(f"AI去味失败: {e}", exc_info=True)
            return original_text

    async def denoise_chapter(
        self,
        chapter_content: str,
        user_id: int,
        timeout: Optional[float] = None,
    ) -> str:
        """
        对章节内容进行去味处理（便捷方法）
        
        Args:
            chapter_content: 章节内容
            user_id: 用户ID
            timeout: 超时时间（秒）
        
        Returns:
            去味后的章节内容
        """
        return await self.denoise_text(
            original_text=chapter_content,
            user_id=user_id,
            timeout=timeout,
        )

    async def batch_denoise(
        self,
        texts: list[str],
        user_id: int,
        timeout: Optional[float] = None,
    ) -> list[str]:
        """
        批量去味处理
        
        Args:
            texts: 文本列表
            user_id: 用户ID
            timeout: 超时时间（秒）
        
        Returns:
            去味后的文本列表
        """
        results = []
        for i, text in enumerate(texts):
            logger.info(f"批量去味：处理第 {i+1}/{len(texts)} 个文本")
            denoised = await self.denoise_text(text, user_id, timeout)
            results.append(denoised)
        
        return results

