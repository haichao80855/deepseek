"""宠物行为状态机。

M2：手动切换行为（按键 1~6）验证动画效果；
M3：接入情绪识别，情绪经平滑后驱动行为切换。

每个行为定义：
    key           情绪键（M3 用）
    label         中文名
    messages      气泡文案（随机取）
    min_hold      切换后至少保持的秒数（防抖）
"""
from __future__ import annotations

import random
import time

# 行为定义（顺序即按键 1~6 的顺序）
BEHAVIORS: dict[str, dict] = {
    "idle": {
        "label": "日常",
        "messages": ["呼噜呼噜～", "陪你写代码中…", "今天也要加油鸭！"],
        "min_hold": 1.5,
    },
    "happy": {
        "label": "开心",
        "messages": ["哇！好棒！", "看到你开心我也开心！", "耶耶耶！"],
        "min_hold": 2.0,
    },
    "sad": {
        "label": "难过",
        "messages": ["别难过，我一直在呀", "抱抱～", "想哭就哭吧，我陪你"],
        "min_hold": 2.0,
    },
    "angry": {
        "label": "生气",
        "messages": ["深呼吸～", "我陪你把坏情绪吐掉", "不气不气，气坏身体没人替"],
        "min_hold": 2.0,
    },
    "surprised": {
        "label": "惊讶",
        "messages": ["咦？！", "发生什么啦？", "哇哦！"],
        "min_hold": 1.5,
    },
    "sleepy": {
        "label": "困困",
        "messages": ["zzz…", "好困呀…", "想睡觉觉…"],
        "min_hold": 2.0,
    },
}


class PetEngine:
    """宠物行为状态机：记录当前行为、管理切换与防抖。"""

    def __init__(self, initial: str = "idle") -> None:
        if initial not in BEHAVIORS:
            initial = "idle"
        self._current = initial
        self._switched_at = time.monotonic()

    @property
    def current(self) -> str:
        return self._current

    def set(self, behavior: str) -> bool:
        """请求切换行为。返回是否真的切换了（防抖期内忽略）。"""
        if behavior not in BEHAVIORS or behavior == self._current:
            return False
        now = time.monotonic()
        if now - self._switched_at < BEHAVIORS[self._current]["min_hold"]:
            return False
        self._current = behavior
        self._switched_at = now
        return True

    def say(self) -> str:
        """返回当前行为下的一条随机气泡文案。"""
        return random.choice(BEHAVIORS[self._current]["messages"])
