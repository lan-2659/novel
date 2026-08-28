"""创作流水线双层阶段定义。

全书阶段：idea -> setting -> outline -> writing -> completed
每卷阶段：volume_outline -> volume_plan -> writing -> volume_completed

规则：
- 全书阶段仅向前推进（advance_stage），编辑旧内容不会回退。
- 每卷阶段同理（advance_volume_stage）。
- 全书 completed 的条件：所有卷都 completed。
"""

STAGE_IDEA = "idea"
STAGE_SETTING = "setting"
STAGE_OUTLINE = "outline"
STAGE_WRITING = "writing"
STAGE_COMPLETED = "completed"

STAGE_ORDER = [
    STAGE_IDEA,
    STAGE_SETTING,
    STAGE_OUTLINE,
    STAGE_WRITING,
    STAGE_COMPLETED,
]

VOLUME_STAGE_OUTLINE = "volume_outline"
VOLUME_STAGE_PLAN = "volume_plan"
VOLUME_STAGE_WRITING = "writing"
VOLUME_STAGE_COMPLETED = "volume_completed"

VOLUME_STAGE_ORDER = [
    VOLUME_STAGE_OUTLINE,
    VOLUME_STAGE_PLAN,
    VOLUME_STAGE_WRITING,
    VOLUME_STAGE_COMPLETED,
]

VOLUME_STATUS_DRAFT = "draft"
VOLUME_STATUS_WRITING = "writing"
VOLUME_STATUS_COMPLETED = "completed"


def advance_stage(current: str, target: str) -> str:
    """仅允许全书阶段向前推进，防止编辑旧内容导致阶段回退。"""
    try:
        cur_idx = STAGE_ORDER.index(current)
        tgt_idx = STAGE_ORDER.index(target)
    except ValueError:
        return target
    return STAGE_ORDER[max(cur_idx, tgt_idx)]


def advance_volume_stage(current: str, target: str) -> str:
    """仅允许卷内阶段向前推进，防止编辑旧内容导致卷阶段回退。"""
    try:
        cur_idx = VOLUME_STAGE_ORDER.index(current)
        tgt_idx = VOLUME_STAGE_ORDER.index(target)
    except ValueError:
        return target
    return VOLUME_STAGE_ORDER[max(cur_idx, tgt_idx)]
