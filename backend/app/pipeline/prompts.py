"""各创作阶段的 Prompt 模板。

约定：
- 设定 / 大纲 / 章节规划：要求 LLM 输出 JSON，便于解析入库。
- 章节正文：输出纯文本。
"""

import json
from typing import Any

SETTING_SYSTEM = (
    "你是一位资深小说设定师，擅长世界构建、人物塑造与风格设计。"
    "你只输出一个合法的 JSON 对象，不要包含任何解释、注释或 Markdown 代码块标记。"
)

OUTLINE_SYSTEM = (
    "你是一位资深小说策划师，擅长设计故事结构与情节大纲。"
    "你只输出一个合法的 JSON 对象，不要包含任何解释、注释或 Markdown 代码块标记。"
)

PLAN_SYSTEM = (
    "你是一位资深小说策划师，擅长将故事大纲拆解为逐章写作计划。"
    "你只输出一个合法的 JSON 对象，不要包含任何解释、注释或 Markdown 代码块标记。"
)

WRITING_SYSTEM = (
    "你是一位专业中文小说作家。请根据给定的故事设定、章节规划与上下文，"
    "写出该章节的完整正文。直接输出小说正文，不要输出章节标题、不要使用 JSON、"
    "不要做任何解释或说明。"
)


def build_setting_messages(premise: str) -> tuple[str, str]:
    user = (
        f"创意：{premise}\n\n"
        "请基于以上创意生成完整的故事设定，严格输出如下 JSON 结构：\n"
        '{"worldview": "世界观（时代/地点/规则/背景）", '
        '"characters": [{"name": "角色名", "role": "主角/配角", "description": "性格、目标与背景"}], '
        '"style": "文风（叙事视角、语言风格、节奏）"}'
    )
    return SETTING_SYSTEM, user


def build_outline_messages(premise: str, setting: dict[str, Any]) -> tuple[str, str]:
    user = (
        f"创意：{premise}\n"
        f"故事设定：{json.dumps(setting, ensure_ascii=False)}\n\n"
        "请基于以上信息生成故事大纲，严格输出如下 JSON 结构：\n"
        '{"summary": "全书故事梗概", '
        '"acts": [{"title": "幕/篇章标题", "summary": "该部分主要情节"}]}'
    )
    return OUTLINE_SYSTEM, user


def build_chapter_plan_messages(
    premise: str,
    setting: dict[str, Any],
    outline: dict[str, Any],
    chapter_count: int = 10,
) -> tuple[str, str]:
    user = (
        f"创意：{premise}\n"
        f"故事设定：{json.dumps(setting, ensure_ascii=False)}\n"
        f"故事大纲：{json.dumps(outline, ensure_ascii=False)}\n\n"
        f"请将故事拆解为约 {chapter_count} 章的写作计划，严格输出如下 JSON 结构：\n"
        '{"chapters": [{"number": 1, "title": "章节标题", "summary": "本章情节要点"}]}'
    )
    return PLAN_SYSTEM, user


def build_chapter_messages(
    premise: str,
    setting: dict[str, Any],
    chapters: list[dict[str, Any]],
    chapter_number: int,
    prev_tail: str,
) -> tuple[str, str]:
    target = next(
        (c for c in chapters if int(c.get("number", 0)) == chapter_number),
        None,
    )
    target_text = json.dumps(target, ensure_ascii=False) if target else f"第 {chapter_number} 章"

    user = (
        f"创意：{premise}\n"
        f"故事设定：{json.dumps(setting, ensure_ascii=False)}\n"
        f"章节规划：{json.dumps(chapters, ensure_ascii=False)}\n\n"
        f"现在请撰写第 {chapter_number} 章，本章要点：{target_text}\n"
    )
    if prev_tail:
        user += f"\n上一章结尾（用于衔接文风与剧情）：\n{prev_tail}\n"
    user += "\n请直接输出本章小说正文。"
    return WRITING_SYSTEM, user
