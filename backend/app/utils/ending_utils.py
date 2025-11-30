from typing import Dict, Any


def inject_ending_outline_text(
    user_prompt: str,
    ending_outline: Dict[str, Any],
) -> str:
    """
    将收尾大纲（ending_outline）拼接到用户提示词前，供3Agent参考。

    Args:
        user_prompt: 原始用户提示（大纲/上下文）
        ending_outline: 收尾规划JSON

    Returns:
        拼接后的prompt
    """
    if not ending_outline:
        return user_prompt

    ending_text = ["# 收尾规划（请严格遵守）"]

    for chap in ending_outline.get("ending_chapters", []):
        ending_text.append(
            f"- 终章{chap.get('chapter_number')}: {chap.get('title', '')} "
            f"摘要: {chap.get('summary', '')}"
        )
        if chap.get("must_resolve"):
            ending_text.append(f"  必须解决: {', '.join(chap.get('must_resolve', []))}")
        if chap.get("character_endings"):
            ending_text.append(f"  角色结局: {', '.join(chap.get('character_endings', []))}")
        if chap.get("emotional_peak"):
            ending_text.append(f"  情感高潮: {chap.get('emotional_peak')}")

    epilogue = ending_outline.get("epilogue")
    if epilogue and epilogue.get("needed"):
        ending_text.append(f"- 尾声: {epilogue.get('content', '')}")

    ending_text.append("")
    ending_text.append(user_prompt)

    return "\n".join(ending_text)
