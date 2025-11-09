"""
文本处理工具函数
"""
import re
from typing import Optional


def remove_think_tags(text: str) -> str:
    """
    移除文本中的 <thinking>...</thinking> 标签及其内容

    某些LLM（如Claude）会在响应中包含思考过程标签，这些标签需要在
    保存或展示给用户前移除。

    Args:
        text: 原始文本

    Returns:
        移除思考标签后的文本

    Examples:
        >>> text = "这是内容<thinking>这是思考</thinking>继续内容"
        >>> remove_think_tags(text)
        '这是内容继续内容'

        >>> text = "<thinking>思考1</thinking>内容<thinking>思考2</thinking>"
        >>> remove_think_tags(text)
        '内容'
    """
    if not text:
        return text

    # 使用正则表达式移除 <thinking>...</thinking> 标签及其内容
    # re.DOTALL 让 . 可以匹配换行符，这样可以处理多行的思考内容
    # re.IGNORECASE 让匹配不区分大小写
    pattern = r'<thinking>.*?</thinking>'
    cleaned_text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)

    # 移除可能产生的多余空白
    cleaned_text = cleaned_text.strip()

    return cleaned_text


def remove_xml_tags(text: str, tag_name: str) -> str:
    """
    移除文本中指定的XML标签及其内容

    Args:
        text: 原始文本
        tag_name: 标签名称（不含尖括号）

    Returns:
        移除指定标签后的文本

    Examples:
        >>> text = "内容<draft>草稿</draft>继续"
        >>> remove_xml_tags(text, "draft")
        '内容继续'
    """
    if not text or not tag_name:
        return text

    # 转义标签名中的特殊字符
    tag_escaped = re.escape(tag_name)
    pattern = f'<{tag_escaped}>.*?</{tag_escaped}>'
    cleaned_text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)

    return cleaned_text.strip()


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    截断文本到指定长度

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断时添加的后缀

    Returns:
        截断后的文本

    Examples:
        >>> truncate_text("这是一段很长的文本", 6)
        '这是一段很...'
    """
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def count_words(text: str) -> int:
    """
    统计文本字数（中英文混合）

    中文按字符数计算，英文按单词数计算

    Args:
        text: 文本内容

    Returns:
        字数统计
    """
    if not text:
        return 0

    # 简化版本：统计所有非空白字符
    # 更精确的实现可以区分中英文
    return len(text.replace(' ', '').replace('\n', '').replace('\t', ''))


def extract_json_from_markdown(text: str) -> Optional[str]:
    """
    从markdown格式的文本中提取JSON代码块

    Args:
        text: 包含markdown格式的文本

    Returns:
        提取的JSON字符串，如果未找到则返回None

    Examples:
        >>> text = "这是说明\\n```json\\n{\"key\": \"value\"}\\n```\\n结束"
        >>> extract_json_from_markdown(text)
        '{"key": "value"}'
    """
    if not text:
        return None

    # 匹配 ```json ... ``` 或 ``` ... ``` 代码块
    patterns = [
        r'```json\s*(.*?)\s*```',
        r'```\s*(.*?)\s*```',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

    return None
