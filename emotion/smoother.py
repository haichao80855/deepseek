"""情绪平滑模块。

问题：单帧表情识别抖动大（眨眼、光线变化都会让 argmax 跳来跳去）。
方案：对每帧概率做指数移动平均（EMA），每 N 秒取窗口内的主导情绪；
只有主导情绪发生变化时才对外报告，避免宠物行为反复横跳。
"""
from __future__ import annotations

import time

import numpy as np

from emotion.detector import EMOTIONS


class EmotionSmoother:
    """EMA 情绪平滑器。"""

    def __init__(
        self,
        ema_alpha: float = 0.6,       # EMA 平滑系数（越大跟随越快，越小越稳）
        window_seconds: float = 1.0,  # 输出主导情绪的时间窗口
        min_confidence: float = 0.15, # 置信度低于此值的帧直接忽略
        min_hold_seconds: float = 1.0,# 新情绪需连续保持多久才切换
    ) -> None:
        self.alpha = ema_alpha
        self.window_seconds = window_seconds
        self.min_confidence = min_confidence
        self.min_hold_seconds = min_hold_seconds

        self._ema: np.ndarray | None = None  # 8 类情绪的 EMA 概率
        self._last_report_time = 0.0
        self._current: str | None = None     # 当前对外报告的情绪
        self._candidate: str | None = None   # 候选切换情绪
        self._candidate_since = 0.0

    def update(self, result: dict | None) -> str | None:
        """喂入一帧分析结果，返回需要对外报告的情绪（无变化或无人脸返回 None）。"""
        now = time.monotonic()

        if result is None or result["confidence"] < self.min_confidence:
            return None

        probs = result["probs"].astype(np.float64)
        if self._ema is None:
            self._ema = probs
        else:
            self._ema = self.alpha * probs + (1 - self.alpha) * self._ema

        # 时间窗口内才输出
        if now - self._last_report_time < self.window_seconds:
            return None

        dominant = EMOTIONS[int(np.argmax(self._ema))]

        if dominant != self._current:
            if dominant == self._candidate:
                # 候选情绪持续保持中，够久则切换
                if now - self._candidate_since >= self.min_hold_seconds:
                    self._current = dominant
                    self._last_report_time = now
                    self._candidate = None
                    return dominant
            else:
                self._candidate = dominant
                self._candidate_since = now

        self._last_report_time = now
        return None

    def reset(self) -> None:
        self._ema = None
        self._current = None
        self._candidate = None
