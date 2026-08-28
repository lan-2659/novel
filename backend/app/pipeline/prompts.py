"""各创作阶段的 Prompt 模板。

约定：
- 设定 / 全书大纲 / 卷大纲 / 卷章节规划 / 追踪提取：要求 LLM 输出 JSON，便于解析入库。
- 章节正文：输出纯文本。
"""

import json
from typing import Any

SETTING_SYSTEM = (
    "你是一位资深小说设定师，擅长世界构建、人物塑造与风格设计。"
    "你只输出一个合法的 JSON 对象，不要包含任何解释、注释或 Markdown 代码块标记。"
)

OUTLINE_SYSTEM = (
    "你是一位资深小说策划师，擅长设计故事结构与全书情节大纲。"
    "你只输出一个合法的 JSON 对象，不要包含任何解释、注释或 Markdown 代码块标记。"
)

VOLUME_OUTLINE_SYSTEM = (
    "你是一位资深分卷策划师，擅长把全书大纲细化为单卷的写作蓝图，并承接前面卷的情节走向。"
    "你只输出一个合法的 JSON 对象，不要包含任何解释、注释或 Markdown 代码块标记。"
)

VOLUME_PLAN_SYSTEM = (
    "你是一位资深分卷规划师，擅长把单卷大纲拆解为 15~30 章的逐章写作计划。"
    "你只输出一个合法的 JSON 对象，不要包含任何解释、注释或 Markdown 代码块标记。"
)

TRACKING_SYSTEM = (
    "你是一位编剧助理，负责从已完成的章节中提取长篇写作所需的追踪信息。"
    "你只输出一个合法的 JSON 对象，不要包含任何解释、注释或 Markdown 代码块标记。"
)

WRITING_SYSTEM = (
    "你是一位专业中文小说作家。请根据给定的故事设定、分卷大纲、章节规划与上下文，"
    "写出该章节的完整正文。直接输出小说正文，不要输出章节标题、不要使用 JSON、"
    "不要做任何解释或说明。"
)

IDEA_SYSTEM = (
    "你是一位资深小说创意策划师，擅长构思新颖、有市场卖点的小说创意。"
    "你只输出一个合法的 JSON 对象，不要包含任何解释、注释或 Markdown 代码块标记。"
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
        "请基于以上信息生成全书故事大纲，严格输出如下 JSON 结构：\n"
        '{"summary": "全书故事梗概", '
        '"acts": [{"title": "幕/篇章标题", "summary": "该部分主要情节"}]}'
    )
    return OUTLINE_SYSTEM, user


def build_volume_outline_messages(
    premise: str,
    setting: dict[str, Any],
    global_outline_summary: str,
    volume_number: int,
    previous_volumes: list[dict[str, Any]],
) -> tuple[str, str]:
    prev_text = _previous_volumes_text(previous_volumes)
    user = (
        f"创意：{premise}\n"
        f"故事设定：{json.dumps(setting, ensure_ascii=False)}\n"
        f"全书大纲摘要：{global_outline_summary or '（暂无）'}\n"
        f"{prev_text}"
        f"请为「第{volume_number}卷」生成卷大纲，作为本卷的写作蓝图，"
        "须承接全书方向并呼应前面卷的情节，严格输出如下 JSON 结构：\n"
        '{"summary": "本卷故事梗概", '
        '"beats": [{"title": "本卷情节阶段标题", "summary": "该阶段主要情节"}]}'
    )
    return VOLUME_OUTLINE_SYSTEM, user


def build_volume_plan_messages(
    premise: str,
    setting: dict[str, Any],
    global_outline_summary: str,
    volume_outline: dict[str, Any],
    volume_number: int,
    previous_volumes: list[dict[str, Any]],
    character_state_summary: str,
    foreshadowing_items: list[str],
    global_summary: str,
    min_chapters: int = 15,
    max_chapters: int = 30,
) -> tuple[str, str]:
    prev_text = _previous_volumes_text(previous_volumes)
    user = (
        f"创意：{premise}\n"
        f"故事设定：{json.dumps(setting, ensure_ascii=False)}\n"
        f"全书大纲摘要：{global_outline_summary or '（暂无）'}\n"
        f"本卷大纲：{json.dumps(volume_outline, ensure_ascii=False) if volume_outline else '（暂无）'}\n"
        f"{prev_text}"
        "跨卷追踪信息（供规划参考，需与前面情节呼应）：\n"
        f"- 人物状态：{character_state_summary or '（暂无）'}\n"
        f"- 未解伏笔：{json.dumps(foreshadowing_items, ensure_ascii=False) if foreshadowing_items else '（暂无）'}\n"
        f"- 全局剧情摘要：{global_summary or '（暂无）'}\n\n"
        f"请为「第{volume_number}卷」生成约 {min_chapters}~{max_chapters} 章的章节写作计划，"
        "严格输出如下 JSON 结构：\n"
        '{"chapters": [{"number": 1, "title": "章节标题", "summary": "本章情节要点"}]}'
    )
    return VOLUME_PLAN_SYSTEM, user


def build_chapter_messages(context: dict[str, Any]) -> tuple[str, str]:
    """基于四层上下文（ContextBuilder.build_chapter_context 的输出）组装写作消息。"""
    user = (
        f"创意：{context['premise']}\n"
        f"故事设定：{json.dumps(context['setting'], ensure_ascii=False)}\n"
        f"全书大纲摘要：{context.get('outline_summary') or '（暂无）'}\n"
        f"当前卷：{context.get('volume_title') or ''}\n"
        f"本卷大纲：{json.dumps(context.get('volume_outline'), ensure_ascii=False) if context.get('volume_outline') else '（暂无）'}\n"
        f"本章要点：{context.get('current_chapter_summary') or '（请根据本卷大纲续写）'}\n"
        f"本卷已完成剧情摘要：{context.get('volume_summary') or '（暂无）'}\n"
        "跨卷追踪信息（保持人物与伏笔一致性）：\n"
        f"- 人物状态：{context.get('character_state_summary') or '（暂无）'}\n"
        f"- 未解伏笔：{json.dumps(context.get('foreshadowing_items'), ensure_ascii=False) if context.get('foreshadowing_items') else '（暂无）'}\n"
        f"- 全局剧情摘要：{context.get('global_summary') or '（暂无）'}\n"
    )
    if context.get("prev_tail"):
        user += (
            "\n上一章结尾（用于衔接文风与剧情）：\n"
            f"{context['prev_tail']}\n"
        )
    user += "\n请直接输出本章小说正文。"
    return WRITING_SYSTEM, user


def build_tracking_messages(
    chapter_title: str,
    chapter_content: str,
    character_state_summary: str,
    foreshadowing_items: list[str],
) -> tuple[str, str]:
    user = (
        "请阅读以下章节内容，提取用于长篇写作追踪的关键信息，严格输出如下 JSON 结构：\n"
        '{"character_changes": "各主要人物在本章的状态/心理/关系变化（文本，无可为空字符串）", '
        '"new_foreshadowing": ["本章新埋的伏笔，数组，无则空数组"], '
        '"resolved_foreshadowing": ["本章已回收/解决的伏笔，数组，无则空数组"], '
        '"chapter_summary": "本章剧情摘要（1~2 句）"}\n\n'
        f"章节标题：{chapter_title}\n"
        f"章节正文：\n{chapter_content[:4000]}\n\n"
        "当前追踪状态（供参考，只更新真实发生的变化）：\n"
        f"- 人物状态：{character_state_summary or '（暂无）'}\n"
        f"- 未解伏笔：{json.dumps(foreshadowing_items, ensure_ascii=False) if foreshadowing_items else '（暂无）'}"
    )
    return TRACKING_SYSTEM, user


def build_idea_messages(
    count: int,
    genre: str | None = None,
    style: str | None = None,
) -> tuple[str, str]:
    """首页 AI 灵感创意：要求 LLM 生成多个彼此不同的小说创意。"""
    constraints = []
    if genre:
        constraints.append(f"题材：{genre}")
    if style:
        constraints.append(f"风格：{style}")
    constraint_text = "\n".join(constraints) if constraints else "（不限题材与风格）"

    user = (
        f"请构思 {count} 个彼此不同、新颖且有市场卖点的小说创意。\n"
        f"约束：{constraint_text}\n"
        "每个创意严格包含：title（标题）、idea（创意简介，1~2 句）、genre（题材）、"
        "hook（核心卖点/钩子，一句话，要有画面感与悬念）。\n"
        "严格输出如下 JSON 结构：\n"
        '{"ideas": [{"title": "...", "idea": "...", "genre": "...", "hook": "..."}]}'
    )
    return IDEA_SYSTEM, user


def _previous_volumes_text(previous_volumes: list[dict[str, Any]]) -> str:
    if not previous_volumes:
        return ""
    lines = ["前置卷剧情摘要："]
    for v in previous_volumes:
        lines.append(f"- 第{v.get('number')}卷《{v.get('title')}》：{v.get('summary') or '（暂无）'}")
    lines.append("")
    return "\n".join(lines)

