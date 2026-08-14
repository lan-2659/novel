"""创作流水线阶段定义。

阶段顺序：
IDEA -> SETTING -> OUTLINE -> CHAPTER_PLAN -> WRITING -> COMPLETED

每个阶段完成后状态入库；「继续写作」= 读取项目当前阶段恢复进度。
"""

STAGE_IDEA = "idea"
STAGE_SETTING = "setting"
STAGE_OUTLINE = "outline"
STAGE_CHAPTER_PLAN = "chapter_plan"
STAGE_WRITING = "writing"
STAGE_COMPLETED = "completed"

STAGE_ORDER = [
    STAGE_IDEA,
    STAGE_SETTING,
    STAGE_OUTLINE,
    STAGE_CHAPTER_PLAN,
    STAGE_WRITING,
    STAGE_COMPLETED,
]


def advance_stage(current: str, target: str) -> str:
    """仅允许阶段向前推进，防止编辑旧内容导致阶段回退。"""
    try:
        cur_idx = STAGE_ORDER.index(current)
        tgt_idx = STAGE_ORDER.index(target)
    except ValueError:
        return target
    return STAGE_ORDER[max(cur_idx, tgt_idx)]
