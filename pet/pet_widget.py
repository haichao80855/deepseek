"""宠物绘制组件 —— 使用参考图企鹅素材（透明 PNG）。

素材：pet/assets/penguin_base_transparent.png（参考图抠白底后）
动画：整体变换（呼吸/蹦跳/抖动/挤压/打盹）+ 情绪装饰叠加
      （开心→星星，难过→眼泪，生气→蒸汽，惊讶→感叹号，困困→zzz）
同时保留气泡文案与情绪徽章。
"""
from __future__ import annotations

import math
import os

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QWidget

from pet.pet_engine import PetEngine

_ASSET = os.path.join(os.path.dirname(__file__), "assets", "penguin_base_transparent.png")

# 素材原始比例 754x892 → 画布内高度 228 时宽度
_SPRITE_H = 228.0
_SPRITE_W = _SPRITE_H * 754.0 / 892.0

C_OUTLINE = QColor(0, 0, 0)
C_BUBBLE = QColor(255, 255, 255, 235)
C_BUBBLE_BORDER = QColor(200, 170, 130)


class PetWidget(QWidget):
    """动画宠物绘制区域（无窗口装饰，由 PetWindow 承载）。"""

    def __init__(self, engine: PetEngine, parent=None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._t = 0.0
        self._msg = ""
        self._msg_until = 0.0
        self._last_behavior = engine.current
        self._blink_cycle = 0.0
        self.setFixedSize(240, 240)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._pixmap = QPixmap(_ASSET)
        if self._pixmap.isNull():
            raise FileNotFoundError(f"企鹅素材加载失败: {_ASSET}")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)  # 25 fps

    # ---------- 动画时钟 ----------
    def _tick(self) -> None:
        self._t += 0.04
        self._blink_cycle += 0.04
        if self._engine.current != self._last_behavior:
            self._last_behavior = self._engine.current
            self._show_msg(self._engine.say(), 4.0)
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

        # 行为变换参数
        dy, rot, sx, sy = self._behavior_transform(behavior, t)

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

    # ---------- 行为变换 ----------
    def _behavior_transform(self, behavior: str, t: float):
        """返回 (dy 垂直位移, 旋转角度, 水平缩放, 垂直缩放)。"""
        if behavior == "happy":
            b = abs(math.sin(t * 6.0))
            return -b * 22.0, math.sin(t * 8.0) * 3.0, 1 + b * 0.05, 1 - b * 0.05
        if behavior == "sleepy":
            return math.sin(t * 1.2) * 4.0, math.sin(t * 0.8) * 4.0, 1.0, 1.0
        if behavior == "surprised":
            b = abs(math.sin(t * 14.0))
            return -b * 6.0, math.sin(t * 20.0) * 2.0, 1 + b * 0.07, 1 + b * 0.07
        if behavior == "sad":
            return 6.0 + math.sin(t * 2.0) * 2.0, 2.0, 1.0, 0.97
        if behavior == "angry":
            return math.sin(t * 22.0) * 3.5, math.sin(t * 18.0) * 1.5, 1.0, 1.0
        # idle: 呼吸 + 轻摆
        return math.sin(t * 2.4) * 2.5, math.sin(t * 1.2) * 1.5, 1.0, 1.0

    # ---------- 情绪装饰叠加 ----------
    def _draw_emotion_overlays(self, p: QPainter, behavior: str, t: float) -> None:
        if behavior == "happy":
            for i in range(3):
                x = 26 + i * 18
                y = 40 + math.sin(t * 5 + i) * 8
                self._star(p, x, y, 7)
            # 小心心
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
            # 眼泪（素材右眼大致在 y≈60-75, x≈128-150 区域）
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
