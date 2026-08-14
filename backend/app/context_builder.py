"""上下文构建辅助函数。"""


def tail_of(text: str, n: int = 800) -> str:
    """截取文本末尾 n 个字符，用于章节衔接上下文。"""
    text = (text or "").strip()
    if len(text) <= n:
        return text
    return text[-n:]
