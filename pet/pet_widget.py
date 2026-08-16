"""宠物绘制组件。

用 QPainter 手绘一只圆滚滚的猫形宠物，带帧动画（QTimer 驱动）和
气泡文案。6 种行为各有不同的动画表现：

    idle      呼吸起伏 + 眨眼 + 尾巴轻摆
    happy     上下蹦跳 + 星星 + 眯眯笑眼
    sad       耷拉耳朵 + 眼泪 + 下垂嘴角
    angry     红脸 + 眉毛倒竖 + 冒蒸汽
    surprised 瞪大眼 + 头顶感叹号 + 身体一颤
    sleepy    闭眼 + 头顶飘 zzz + 打盹点头
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from pet.pet_engine import PetEngine

# 配色
C_BODY = QColor(255, 214, 165)     # 奶油橘
C_BODY_DARK = QColor(235, 180, 130)
C_OUTLINE = QColor(120, 80, 50)
C_BLUSH = QColor(255, 150, 150, 160)
C_WHITE = QColor(255, 255, 255)
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
        t = self._t
        behavior = self._engine.current

        # 宠物整体垂直偏移（蹦跳/打盹）
        offset_y = self._behavior_offset(behavior, t)

        painter.save()
        painter.translate(0, offset_y)
        self._draw_tail(painter, behavior, t)
        self._draw_extras(painter, behavior, t)  # 星星/蒸汽/zzz/感叹号/眼泪
        self._draw_body(painter, behavior, t)
        self._draw_face(painter, behavior, t)
        painter.restore()

        self._draw_bubble(painter)

    # ---------- 行为参数 ----------
    def _behavior_offset(self, behavior: str, t: float) -> float:
        if behavior == "happy":
            return -abs(math.sin(t * 6.0)) * 18.0   # 蹦跳（只向上）
        if behavior == "sleepy":
            return math.sin(t * 1.2) * 3.0           # 打盹轻晃
        if behavior == "surprised":
            return -abs(math.sin(t * 14.0)) * 5.0    # 惊吓一颤
        if behavior == "sad":
            return 4.0 + math.sin(t * 2.0) * 2.0     # 低落下沉
        return math.sin(t * 2.4) * 2.5               # 呼吸起伏

    def _is_blinking(self, behavior: str, t: float) -> bool:
        if behavior in ("sleepy",):
            return True
        if behavior == "happy":
            return True
        return (self._blink_cycle % 4.0) < 0.15      # 每 4 秒眨一次

    # ---------- 身体 ----------
    def _draw_body(self, p: QPainter, behavior: str, t: float) -> None:
        # 耳朵（sad 时耷拉）
        droop = 14.0 if behavior == "sad" else 0.0
        ear_left = QPainterPath()
        ear_left.moveTo(58, 92)
        ear_left.lineTo(82, 34 + droop)
        ear_left.lineTo(108, 78)
        ear_left.closeSubpath()
        ear_right = QPainterPath()
        ear_right.moveTo(132, 78)
        ear_right.lineTo(158, 34 + droop)
        ear_right.lineTo(182, 92)
        ear_right.closeSubpath()
        p.setPen(QPen(C_OUTLINE, 3))
        p.setBrush(C_BODY)
        p.drawPath(ear_left)
        p.drawPath(ear_right)
        # 耳内粉
        p.setBrush(QColor(255, 170, 170))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(76, 60 + droop * 0.6, 16, 16))
        p.drawEllipse(QRectF(148, 60 + droop * 0.6, 16, 16))

        # 身体/头
        p.setPen(QPen(C_OUTLINE, 3))
        p.setBrush(C_BODY)
        p.drawEllipse(QRectF(48, 52, 144, 132))

        # 肚皮高光
        p.setBrush(C_WHITE)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(86, 118, 68, 56))

        # 小爪
        p.setBrush(C_BODY)
        p.setPen(QPen(C_OUTLINE, 3))
        p.drawEllipse(QRectF(70, 158, 26, 20))
        p.drawEllipse(QRectF(144, 158, 26, 20))

    # ---------- 尾巴 ----------
    def _draw_tail(self, p: QPainter, behavior: str, t: float) -> None:
        sway = math.sin(t * (6.0 if behavior == "happy" else 3.0)) * 14.0
        if behavior == "sad":
            sway = math.sin(t * 1.5) * 6.0
        path = QPainterPath(QPointF(52, 160))
        path.quadTo(QPointF(26, 140 + sway * 0.3), QPointF(40, 110 + sway))
        p.setPen(QPen(C_OUTLINE, 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    # ---------- 表情 ----------
    def _draw_face(self, p: QPainter, behavior: str, t: float) -> None:
        blink = self._is_blinking(behavior, t)

        # 腮红
        p.setBrush(C_BLUSH)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(66, 108, 24, 13))
        p.drawEllipse(QRectF(150, 108, 24, 13))

        # 眼睛
        eye_w, eye_h = 20, 26
        left = QRectF(78, 92, eye_w, eye_h)
        right = QRectF(142, 92, eye_w, eye_h)
        p.setPen(QPen(C_OUTLINE, 3))

        if behavior == "surprised":
            p.setBrush(C_WHITE)
            p.drawEllipse(left.adjusted(-2, -2, 2, 2))
            p.drawEllipse(right.adjusted(-2, -2, 2, 2))
            p.setBrush(QColor(60, 60, 60))
            p.drawEllipse(QRectF(84, 100, 8, 8))
            p.drawEllipse(QRectF(148, 100, 8, 8))
        elif blink:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(left.adjusted(0, 8, 0, 8), 0, 180 * 16)
            p.drawArc(right.adjusted(0, 8, 0, 8), 0, 180 * 16)
        else:
            p.setBrush(QColor(60, 60, 60))
            p.drawEllipse(left)
            p.drawEllipse(right)
            # 高光
            p.setBrush(C_WHITE)
            p.drawEllipse(QRectF(84, 98, 6, 6))
            p.drawEllipse(QRectF(148, 98, 6, 6))

        # 眉毛（angry 倒竖）
        if behavior == "angry":
            p.setPen(QPen(C_OUTLINE, 4))
            p.drawLine(QPointF(76, 82), QPointF(100, 90))
            p.drawLine(QPointF(164, 82), QPointF(140, 90))

        # 嘴巴
        p.setPen(QPen(C_OUTLINE, 3))
        if behavior == "happy":
            p.drawArc(QRectF(94, 110, 52, 34), 0, 180 * 16)     # 大笑
        elif behavior == "sad":
            p.drawArc(QRectF(94, 130, 52, 30), 180 * 16, 180 * 16)  # 下弯
        elif behavior == "surprised":
            p.setBrush(C_OUTLINE)
            p.drawEllipse(QRectF(106, 122, 28, 22))             # 张嘴
        elif behavior == "angry":
            p.drawArc(QRectF(100, 124, 40, 22), 0, 180 * 16)   # 撇嘴
        elif behavior == "sleepy":
            p.drawArc(QRectF(104, 128, 32, 14), 0, 180 * 16)   # 打哈欠
        else:
            p.drawArc(QRectF(100, 124, 40, 18), 0, 180 * 16)   # 微笑

    # ---------- 装饰元素（星星/蒸汽/zzz/感叹号/眼泪） ----------
    def _draw_extras(self, p: QPainter, behavior: str, t: float) -> None:
        p.setPen(QPen(C_OUTLINE, 2.5))
        if behavior == "happy":
            for i in range(3):
                x = 24 + i * 14
                y = 40 + math.sin(t * 5 + i) * 6
                self._star(p, x, y, 5)
        elif behavior == "angry":
            for i in range(3):
                x = 118 + i * 16
                y = 26 + (t * 40) % 14 - i * 2
                p.setPen(QPen(QColor(160, 160, 160), 2))
                p.setBrush(QColor(230, 230, 230, 180))
                p.drawEllipse(QRectF(x, y, 10, 10))
        elif behavior == "sleepy":
            for i in range(3):
                x = 182 - (t * 30) % 50 + i * 12
                y = 22 + i * 16
                p.setFont(QFont("PingFang SC", 13, QFont.Weight.Bold))
                p.setPen(QPen(C_OUTLINE, 1))
                p.drawText(QPointF(x, y), "z")
        elif behavior == "surprised":
            p.setFont(QFont("PingFang SC", 20, QFont.Weight.Bold))
            p.setPen(QPen(QColor(230, 120, 40), 2))
            p.drawText(QPointF(150, 42), "!")
        elif behavior == "sad":
            p.setPen(QPen(QColor(120, 170, 255), 3))
            p.setBrush(QColor(170, 210, 255))
            y = 60 + (t * 20) % 26
            p.drawEllipse(QRectF(152, y, 8, 12))  # 泪滴滑落

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
        # 气泡本体
        p.setPen(QPen(C_BUBBLE_BORDER, 2))
        p.setBrush(C_BUBBLE)
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 14, 14)
        # 小尾巴
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
