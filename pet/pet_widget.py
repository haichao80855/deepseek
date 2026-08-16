"""宠物绘制组件 —— 参考图企鹅素材 + 专业动画系统。

素材：pet/assets/penguin_base_transparent.png（参考图抠白底）

动画设计（按动画原理）：
- 挤压与拉伸（squash & stretch）：下蹲、起跳拉伸、落地压扁、回稳余震
- 蓄力与回弹（anticipation / overshoot）：ease-in/out/back 缓动曲线
- 弹簧物理：旋转随垂直运动滞后摆动（摆锤感），速度产生前倾
- 随机化：呼吸频率、跳跃周期、微动作时机全部随机，循环永不机械重复
- 随机微动作：张望、小跳、歪头、叹气、鼓气、点头
- 情绪切换惊起反应：先惊跳回弹，再进入新状态的循环

每个行为：
    idle      呼吸 + 视线张望 + 随机微动作
    happy     连续蓄力小跳（下蹲→拉伸→落地→余震）+ 兴奋微摆
    sad       沉重呼吸 + 垂头 + 周期性叹气
    angry     高频颤抖 + 周期性鼓气胀大
    surprised 放大微颤 + 周期性再惊小跳
    sleepy    慢摇 + 周期性低头打盹点头
"""
from __future__ import annotations

import math
import os
import random

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QWidget

from pet.pet_engine import PetEngine

_ASSET = os.path.join(os.path.dirname(__file__), "assets", "penguin_base_transparent.png")
_SPRITE_H = 228.0
_SPRITE_W = _SPRITE_H * 754.0 / 892.0
_DT = 1.0 / 30.0

C_OUTLINE = QColor(0, 0, 0)
C_BUBBLE = QColor(255, 255, 255, 235)
C_BUBBLE_BORDER = QColor(200, 170, 130)


# ---------- 缓动函数 ----------
def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def _lerp(a: float, b: float, x: float) -> float:
    return a + (b - a) * x


def _ease_in_quad(x: float) -> float:
    return x * x


def _ease_out_quad(x: float) -> float:
    x = 1.0 - x
    return 1.0 - x * x


def _ease_in_out_quad(x: float) -> float:
    return 2 * x * x if x < 0.5 else 1 - 2 * (1 - x) ** 2


def _ease_out_back(x: float, s: float = 1.70158) -> float:
    x -= 1.0
    return x * x * ((s + 1.0) * x + s) + 1.0


def _hop_curve(p: float, amp: float, squash: float = 0.12):
    """一个完整跳跃周期（p: 0..1）。

    阶段：蓄力下蹲 → 拉伸起跳 → 空中停留 → 落地压扁 → 回稳余震
    返回 (dy, sy)。
    """
    dy = 0.0
    sy = 1.0
    if p < 0.15:                                   # 蓄力下蹲
        u = _ease_in_quad(p / 0.15)
        dy = _lerp(0.0, 3.0, u)
        sy = 1.0 - squash * u
    elif p < 0.5:                                  # 起跳上升（拉伸）
        u = (p - 0.15) / 0.35
        dy = _lerp(3.0, -amp, _ease_out_quad(u))
        sy = 1.0 + squash * 0.55 * math.sin(math.pi * u)
    elif p < 0.75:                                 # 空中
        u = (p - 0.5) / 0.25
        dy = -amp * (1.0 - 0.1 * math.sin(math.pi * u))
    elif p < 0.88:                                 # 落地压扁
        u = _ease_in_quad((p - 0.75) / 0.13)
        dy = _lerp(-amp, 0.0, u)
        sy = 1.0 - squash * 1.2 * u
    else:                                          # 回稳余震（衰减）
        u = (p - 0.88) / 0.12
        decay = 1.0 - u
        dy = 3.0 * math.sin(math.pi * u) * decay
        sy = 1.0 + squash * 0.6 * math.sin(math.pi * u) * decay
    return dy, sy


class PetWidget(QWidget):
    """动画宠物绘制区域（无窗口装饰，由 PetWindow 承载）。"""

    def __init__(self, engine: PetEngine, parent=None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._t = 0.0
        self._msg = ""
        self._msg_until = 0.0
        self._last_behavior = engine.current
        self.setFixedSize(240, 240)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._pixmap = QPixmap(_ASSET)
        if self._pixmap.isNull():
            raise FileNotFoundError(f"企鹅素材加载失败: {_ASSET}")

        # ---------- 随机化运动参数 ----------
        self._breathe_rate = 0.36 + random.random() * 0.12   # 呼吸频率(Hz)
        self._breathe_phase = random.random() * math.tau
        self._hop_period = 0.6 + random.random() * 0.15      # 开心跳跃周期
        # 视线(张望)弹簧
        self._glance_rot = 0.0
        self._glance_vel = 0.0
        self._glance_target = 0.0
        self._next_glance_at = 1.0 + random.random() * 2.0
        # 微动作调度
        self._micro = None          # (kind, start_t, dur)
        self._next_micro_at = 2.5 + random.random() * 3.0
        # 周期动作：叹气/鼓气/点头/再惊
        self._next_sigh_at = 4.0 + random.random() * 3.0
        self._next_puff_at = 2.0 + random.random() * 2.0
        self._next_nod_at = 2.5 + random.random() * 2.0
        self._next_rejolt_at = 1.5 + random.random() * 1.5
        # 过渡（行为切换惊起）
        self._trans_t = 99.0
        # 速度前倾
        self._prev_dy = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(int(_DT * 1000))  # ~30fps

    # ---------- 动画时钟 ----------
    def _tick(self) -> None:
        self._t += _DT
        now = self._t

        # 行为切换 → 惊起过渡 + 气泡
        if self._engine.current != self._last_behavior:
            self._last_behavior = self._engine.current
            self._trans_t = 0.0
            self._show_msg(self._engine.say(), 4.0)
        else:
            self._trans_t += _DT

        behavior = self._engine.current

        # 视线张望（idle/happy 用）：随机换目标，弹簧跟随
        if now >= self._next_glance_at:
            self._glance_target = random.uniform(-8.0, 8.0)
            self._next_glance_at = now + 2.0 + random.random() * 3.5
        k = 18.0 * _DT
        self._glance_vel += (self._glance_target - self._glance_rot) * k
        self._glance_vel *= 0.86
        self._glance_rot += self._glance_vel

        # 微动作调度（idle）
        if behavior == "idle" and now >= self._next_micro_at:
            kinds = ["hop", "tilt", "double_glance"]
            kind = random.choice(kinds)
            self._micro = (kind, now, {"hop": 1.0, "tilt": 1.6, "double_glance": 1.8}[kind])
            self._next_micro_at = now + 3.5 + random.random() * 4.0
        if self._micro:
            kind, start, dur = self._micro
            if now - start >= dur:
                self._micro = None

        self.update()

    def say(self) -> None:
        """让宠物说一句话（按键触发）。"""
        self._show_msg(self._engine.say(), 3.5)

    def _show_msg(self, text: str, seconds: float) -> None:
        from PyQt6.QtCore import QDateTime

        self._msg = text
        self._msg_until = QDateTime.currentMSecsSinceEpoch() / 1000.0 + seconds

    # ---------- 绘制入口 ----------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        t = self._t
        behavior = self._engine.current

        dy, rot, sx, sy = self._compute_motion(behavior, t)

        painter.save()
        painter.translate(120, 122 + dy)
        painter.rotate(rot)
        painter.scale(sx, sy)
        painter.drawPixmap(
            QRectF(-_SPRITE_W / 2, -_SPRITE_H / 2, _SPRITE_W, _SPRITE_H),
            self._pixmap,
            QRectF(0, 0, self._pixmap.width(), self._pixmap.height()),
        )
        painter.restore()

        self._draw_emotion_overlays(painter, behavior, t)
        self._draw_badge(painter)
        self._draw_bubble(painter)

    # ---------- 运动合成 ----------
    def _compute_motion(self, behavior: str, t: float):
        """合成 dy / rot / sx / sy：过渡 + 行为主体 + 呼吸 + 视线 + 微动作 + 速度前倾。"""
        dy = rot = 0.0
        sx = sy = 1.0

        # 1) 行为主体动作
        b_dy, b_rot, b_sx, b_sy = self._behavior_loop(behavior, t)
        dy += b_dy
        rot += b_rot
        sx *= b_sx
        sy *= b_sy

        # 2) 呼吸（所有行为叠加，生气加快）
        rate = self._breathe_rate * (1.8 if behavior == "angry" else 1.0)
        br = math.sin(math.tau * rate * t + self._breathe_phase)
        sy *= 1.0 + br * 0.012
        dy += br * 0.8
        rot += br * 0.15

        # 3) 视线张望（idle/happy/surprised 用）
        if behavior in ("idle", "happy", "surprised"):
            rot += self._glance_rot * 0.4

        # 4) 微动作（idle）
        m_dy, m_rot, m_sy = self._micro_motion(t)
        dy += m_dy
        rot += m_rot
        sy *= m_sy

        # 5) 切换惊起过渡
        if self._trans_t < 0.8:
            u = _clamp01(self._trans_t / 0.8)
            decay = 1.0 - u
            dy += -12.0 * _ease_out_back(u) * decay
            rot += math.sin(self._trans_t * 35.0) * 5.0 * decay
            sx *= 1.0 + 0.05 * decay
            sy *= 1.0 + 0.05 * decay

        # 6) 速度前倾（摆锤感：上升时前倾，下落时后仰）
        lean = (dy - self._prev_dy) / _DT * 0.006
        rot += lean
        self._prev_dy = dy

        return dy, rot, sx, sy

    # ---------- 各行为主体动作 ----------
    def _behavior_loop(self, behavior: str, t: float):
        if behavior == "happy":
            h = (t / self._hop_period) % 1.0
            amp = -20.0 - math.sin(self._breathe_phase) * 3.0
            dy, sy = _hop_curve(h, amp)
            rot = math.sin(t * 10.0) * 2.5 * (1.0 if h < 0.5 else 0.6)
            return dy, rot, 1.0, sy

        if behavior == "sad":
            dy = 6.0 + math.sin(t * 1.6) * 1.5
            rot = 2.5 + math.sin(t * 1.2) * 0.5
            sy = 0.97 + math.sin(t * 1.6) * 0.006
            # 周期性叹气（泄气下沉再回弹）
            if t >= self._next_sigh_at:
                self._next_sigh_at = t + 4.5 + random.random() * 3.0
                self._sigh_t = t
            sigh_t = getattr(self, "_sigh_t", -99.0)
            sp = _clamp01((t - sigh_t) / 1.4)
            if 0.0 < sp < 1.0:
                u = sp
                dy += 5.0 * math.sin(math.pi * u)
                sy *= 1.0 - 0.04 * math.sin(math.pi * u)
            return dy, rot, 1.0, sy

        if behavior == "angry":
            # 高频颤抖 + 小幅旋转
            jitter = math.sin(t * 26.0) * 2.2 + math.sin(t * 39.0) * 1.2
            rot = math.sin(t * 17.0) * 1.2
            sx = 1.0 + jitter * 0.004
            sy = 1.0
            # 周期性鼓气（胀大→回弹）
            if t >= self._next_puff_at:
                self._next_puff_at = t + 2.2 + random.random() * 1.8
                self._puff_t = t
            puff_t = getattr(self, "_puff_t", -99.0)
            pp = _clamp01((t - puff_t) / 0.7)
            if 0.0 < pp < 1.0:
                s = 1.0 + 0.07 * _ease_out_back(pp)
                sx *= s
                sy *= 1.0 / math.sqrt(s)
            return jitter, rot, sx, 1.0

        if behavior == "surprised":
            # 整体放大微颤
            dy = 0.0
            tremble = math.sin(t * 30.0) * 0.004
            sx = 1.06 + tremble
            sy = 1.06 + tremble
            rot = math.sin(t * 22.0) * 0.8
            # 周期性"再惊"小跳
            if t >= self._next_rejolt_at:
                self._next_rejolt_at = t + 2.0 + random.random() * 1.6
                self._rejolt_t = t
            rj_t = getattr(self, "_rejolt_t", -99.0)
            rp = _clamp01((t - rj_t) / 0.6)
            if 0.0 < rp < 1.0:
                dy = -9.0 * _ease_out_back(rp)
                sx *= 1.0 + 0.06 * math.sin(math.pi * rp)
            return dy, rot, sx, sy

        if behavior == "sleepy":
            # 慢摇
            dy = math.sin(t * 1.0) * 3.0
            rot = math.sin(t * 0.7) * 3.0
            sy = 0.98
            # 周期性点头（低头→保持→回弹）
            if t >= self._next_nod_at:
                self._next_nod_at = t + 3.0 + random.random() * 2.0
                self._nod_t = t
            nod_t = getattr(self, "_nod_t", -99.0)
            np_ = _clamp01((t - nod_t) / 1.3)
            if 0.0 < np_ < 1.0:
                if np_ < 0.45:
                    rot -= 11.0 * _ease_in_out_quad(np_ / 0.45)
                elif np_ < 0.75:
                    rot -= 11.0
                else:
                    rot -= 11.0 * (1.0 - _ease_out_back((np_ - 0.75) / 0.25))
            return dy, rot, 1.0, sy

        # idle：基本就是呼吸 + 视线 + 微动作（主体动作较轻）
        return 0.0, 0.0, 1.0, 1.0

    # ---------- idle 微动作 ----------
    def _micro_motion(self, t: float):
        if self._micro is None:
            return 0.0, 0.0, 1.0
        kind, start, dur = self._micro
        p = _clamp01((t - start) / dur)
        if kind == "hop":
            dy, sy = _hop_curve(p, 12.0, 0.08)
            return dy, 0.0, sy
        if kind == "tilt":
            if p < 0.5:
                rot = 5.0 * _ease_in_out_quad(p / 0.5)
            else:
                rot = 5.0 * (1.0 - _ease_in_out_quad((p - 0.5) / 0.5))
            return 0.0, rot, 1.0
        if kind == "double_glance":
            # 快速左右张望两次
            seq = (p * 2) % 1.0
            rot = 9.0 * math.sin(math.pi * seq)
            return 0.0, rot, 1.0
        return 0.0, 0.0, 1.0

    # ---------- 情绪装饰叠加 ----------
    def _draw_emotion_overlays(self, p: QPainter, behavior: str, t: float) -> None:
        if behavior == "happy":
            for i in range(3):
                x = 26 + i * 18
                y = 40 + math.sin(t * 5 + i) * 8
                self._star(p, x, y, 7)
            p.setFont(QFont("PingFang SC", 14))
            p.setPen(QPen(QColor(255, 90, 120), 1))
            p.drawText(QPointF(150, 44 + math.sin(t * 4) * 6), "♥")
        elif behavior == "angry":
            for i in range(3):
                x = 108 + i * 16
                y = 30 + (t * 40) % 18 - i * 2
                p.setPen(QPen(QColor(165, 165, 170), 2))
                p.setBrush(QColor(232, 232, 235, 190))
                p.drawEllipse(QRectF(x, y, 12, 12))
        elif behavior == "sleepy":
            for i in range(3):
                x = 168 - (t * 26) % 44 + i * 12
                y = 26 + i * 17
                p.setFont(QFont("PingFang SC", 14, QFont.Weight.Bold))
                p.setPen(QPen(C_OUTLINE, 1))
                p.drawText(QPointF(x, y), "z")
        elif behavior == "surprised":
            p.setFont(QFont("PingFang SC", 24, QFont.Weight.Bold))
            p.setPen(QPen(QColor(235, 130, 45), 2))
            p.drawText(QPointF(152, 42), "!")
        elif behavior == "sad":
            p.setPen(QPen(QColor(120, 170, 255), 3))
            p.setBrush(QColor(170, 210, 255))
            y = 78 + (t * 22) % 30
            p.drawEllipse(QRectF(142, y, 9, 13))

    @staticmethod
    def _star(p: QPainter, cx: float, cy: float, r: float) -> None:
        path = QPainterPath()
        for i in range(10):
            ang = math.pi / 5 * i - math.pi / 2
            rad = r if i % 2 == 0 else r * 0.45
            pt = QPointF(cx + math.cos(ang) * rad, cy + math.sin(ang) * rad)
            if i == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        path.closeSubpath()
        p.setPen(QPen(QColor(255, 200, 60), 1.5))
        p.setBrush(QColor(255, 220, 100, 220))
        p.drawPath(path)

    # ---------- 情绪徽章 ----------
    def _draw_badge(self, p: QPainter) -> None:
        label = self._engine.emotion_label
        if not label:
            return
        p.setFont(QFont("PingFang SC", 10))
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(label)
        bw, bh = tw + 18, 20
        bx = (240 - bw) / 2.0
        by = 212.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 210))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 10, 10)
        p.setPen(QPen(QColor(120, 80, 50), 1))
        p.drawText(QRectF(bx, by, bw, bh), Qt.AlignmentFlag.AlignCenter, f"心情：{label}")

    # ---------- 气泡 ----------
    def _draw_bubble(self, p: QPainter) -> None:
        from PyQt6.QtCore import QDateTime

        now = QDateTime.currentMSecsSinceEpoch() / 1000.0
        if not self._msg or now > self._msg_until:
            return
        p.setFont(QFont("PingFang SC", 12))
        fm = p.fontMetrics()
        text_w = fm.horizontalAdvance(self._msg)
        bw, bh = text_w + 28, 34
        bx = (240 - bw) / 2.0
        by = 6.0
        p.setPen(QPen(C_BUBBLE_BORDER, 2))
        p.setBrush(C_BUBBLE)
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 14, 14)
        p.drawPolygon(
            [
                QPointF(120, by + bh - 4),
                QPointF(108, by + bh + 8),
                QPointF(132, by + bh + 8),
            ]
        )
        p.setPen(QPen(C_OUTLINE, 1))
        p.drawText(
            QRectF(bx, by, bw, bh),
            Qt.AlignmentFlag.AlignCenter,
            self._msg,
        )
