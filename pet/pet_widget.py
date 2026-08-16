"""宠物绘制组件 —— Q 版企鹅（借鉴腾讯 QQ 企鹅风格）。

用 QPainter 手绘一只圆滚滚的企鹅：蛋形深色身体、白色圆脸和肚皮、
橙色嘴喙、红色围巾、小翅膀与脚丫，带帧动画（QTimer 驱动）和气泡。

6 种行为各有专属表情与动作：
    idle      呼吸起伏 + 眨眼 + 围巾轻摆
    happy     蹦跳 + 翅膀扇动 + 眯眯笑眼 + 星星
    sad       身体下沉 + 眼泪 + 撇嘴 + 翅膀下垂
    angry     皱眉倒竖 + 冒蒸汽 + 撇嘴
    surprised 瞪大眼 + 张嘴 + 头顶感叹号 + 一颤
    sleepy    闭眼 + 点头打盹 + 飘 zzz
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from pet.pet_engine import PetEngine

# ---------- 企鹅配色 ----------
C_BODY = QColor(56, 66, 88)            # 深蓝黑（QQ 企鹅色）
C_BODY_HI = QColor(78, 90, 116)        # 高光
C_BELLY = QColor(250, 250, 252)        # 白色肚皮
C_BEAK = QColor(255, 170, 60)          # 橙色嘴喙
C_BEAK_DARK = QColor(235, 130, 30)
C_SCARF = QColor(224, 72, 62)          # 红围巾
C_SCARF_DARK = QColor(188, 52, 46)
C_BLUSH = QColor(255, 140, 140, 170)
C_OUTLINE = QColor(38, 46, 60)
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

        offset_y = self._behavior_offset(behavior, t)

        painter.save()
        painter.translate(0, offset_y)
        self._draw_extras(painter, behavior, t)   # 星星/蒸汽/zzz/感叹号/眼泪（身后）
        self._draw_feet(painter, behavior, t)
        self._draw_wings(painter, behavior, t)
        self._draw_body(painter, behavior, t)
        self._draw_scarf(painter, behavior, t)
        self._draw_face(painter, behavior, t)
        painter.restore()

        self._draw_badge(painter)
        self._draw_bubble(painter)

    # ---------- 行为参数 ----------
    def _behavior_offset(self, behavior: str, t: float) -> float:
        if behavior == "happy":
            return -abs(math.sin(t * 6.0)) * 20.0     # 蹦跳（只向上）
        if behavior == "sleepy":
            return math.sin(t * 1.2) * 4.0            # 打盹轻晃
        if behavior == "surprised":
            return -abs(math.sin(t * 14.0)) * 5.0     # 惊吓一颤
        if behavior == "sad":
            return 5.0 + math.sin(t * 2.0) * 2.0      # 低落下沉
        return math.sin(t * 2.4) * 2.5                # 呼吸起伏

    def _is_blinking(self, behavior: str, t: float) -> bool:
        if behavior in ("sleepy",):
            return True
        if behavior == "happy":
            return True
        return (self._blink_cycle % 4.0) < 0.15       # 每 4 秒眨一次

    # ---------- 脚丫（走路摇摆） ----------
    def _draw_feet(self, p: QPainter, behavior: str, t: float) -> None:
        if behavior == "happy":
            w = math.sin(t * 8.0) * 5.0
        elif behavior == "sleepy":
            w = math.sin(t * 1.5) * 2.0
        else:
            w = math.sin(t * 3.0) * 2.0
        p.setPen(QPen(C_OUTLINE, 2))
        p.setBrush(C_BEAK)
        p.drawEllipse(QRectF(94 + w, 186, 26, 13))
        p.drawEllipse(QRectF(134 - w, 186, 26, 13))

    # ---------- 翅膀（扇动） ----------
    def _draw_wings(self, p: QPainter, behavior: str, t: float) -> None:
        if behavior == "happy":
            angle = math.sin(t * 8.0) * 28.0
        elif behavior == "surprised":
            angle = -18.0
        elif behavior == "sad":
            angle = 32.0
        elif behavior == "sleepy":
            angle = 18.0
        else:
            angle = math.sin(t * 2.5) * 6.0
        for side in (1, -1):
            p.save()
            p.translate(120 + side * 58, 128)
            p.rotate(side * (18.0 + angle))
            p.setPen(QPen(C_OUTLINE, 2.5))
            p.setBrush(C_BODY)
            p.drawEllipse(QRectF(-12, -22, 24, 44))
            p.setBrush(C_BODY_HI)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(-6, -16, 10, 22))
            p.restore()

    # ---------- 身体（蛋形） ----------
    def _egg_path(self, cx: float, cy: float, rx: float, ry: float) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(cx, cy - ry)
        path.cubicTo(cx + rx * 0.72, cy - ry, cx + rx, cy - ry * 0.35,
                     cx + rx, cy + ry * 0.18)
        path.cubicTo(cx + rx, cy + ry * 0.95, cx + rx * 0.6, cy + ry,
                     cx, cy + ry)
        path.cubicTo(cx - rx * 0.6, cy + ry, cx - rx, cy + ry * 0.95,
                     cx - rx, cy + ry * 0.18)
        path.cubicTo(cx - rx, cy - ry * 0.35, cx - rx * 0.72, cy - ry,
                     cx, cy - ry)
        path.closeSubpath()
        return path

    def _draw_body(self, p: QPainter, behavior: str, t: float) -> None:
        # 头顶呆毛
        p.setPen(QPen(C_OUTLINE, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(112, 78), QPointF(108, 64))
        p.drawLine(QPointF(120, 77), QPointF(120, 62))
        p.drawLine(QPointF(128, 78), QPointF(132, 64))

        # 蛋形身体
        p.setPen(QPen(C_OUTLINE, 3))
        p.setBrush(C_BODY)
        p.drawPath(self._egg_path(120, 138, 54, 60))

        # 高光
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(90, 104, 132, 160))
        p.drawEllipse(QRectF(82, 96, 14, 34))

        # 白色肚皮
        p.setBrush(C_BELLY)
        p.setPen(QPen(C_OUTLINE, 2))
        p.drawEllipse(QRectF(98, 152, 44, 34))

    # ---------- 红围巾 ----------
    def _draw_scarf(self, p: QPainter, behavior: str, t: float) -> None:
        # 脖间围巾带
        p.setPen(QPen(C_SCARF_DARK, 2))
        p.setBrush(C_SCARF)
        p.drawRoundedRect(QRectF(82, 146, 76, 16), 7, 7)
        # 飘带（开心时摆动）
        sway = math.sin(t * 5.0) * 4.0 if behavior == "happy" else math.sin(t * 2.0) * 1.5
        tail = QPainterPath(QPointF(146, 160))
        tail.lineTo(150 + sway, 176)
        tail.lineTo(138 + sway, 176)
        tail.closeSubpath()
        p.drawPath(tail)
        # 围巾穗
        p.drawLine(QPointF(146, 176), QPointF(148 + sway, 182))
        p.drawLine(QPointF(144, 176), QPointF(142 + sway, 182))

    # ---------- 面部 ----------
    def _draw_face(self, p: QPainter, behavior: str, t: float) -> None:
        # 白色脸盘
        p.setPen(QPen(C_OUTLINE, 2.5))
        p.setBrush(C_BELLY)
        p.drawEllipse(QRectF(88, 96, 64, 58))

        blink = self._is_blinking(behavior, t)

        # 腮红
        p.setBrush(C_BLUSH)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(84, 122, 20, 11))
        p.drawEllipse(QRectF(136, 122, 20, 11))

        # 眼睛
        eye_w, eye_h = 19, 24
        left = QRectF(96, 102, eye_w, eye_h)
        right = QRectF(126, 102, eye_w, eye_h)
        p.setPen(QPen(C_OUTLINE, 2.5))

        if behavior == "surprised":
            p.setBrush(C_WHITE)
            p.drawEllipse(left.adjusted(-2, -2, 2, 2))
            p.drawEllipse(right.adjusted(-2, -2, 2, 2))
            p.setBrush(QColor(45, 50, 60))
            p.drawEllipse(QRectF(102, 110, 8, 8))
            p.drawEllipse(QRectF(132, 110, 8, 8))
        elif behavior == "happy":
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(left.adjusted(0, 6, 0, 6), 180 * 16, 180 * 16)   # ^ ^ 眯眯眼
            p.drawArc(right.adjusted(0, 6, 0, 6), 180 * 16, 180 * 16)
        elif blink:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(left.adjusted(0, 8, 0, 8), 0, 180 * 16)
            p.drawArc(right.adjusted(0, 8, 0, 8), 0, 180 * 16)
        else:
            p.setBrush(QColor(45, 50, 60))
            p.drawEllipse(left)
            p.drawEllipse(right)
            p.setBrush(C_WHITE)
            p.drawEllipse(QRectF(102, 108, 5, 5))
            p.drawEllipse(QRectF(132, 108, 5, 5))

        # 眉毛（angry 倒竖 / sad 微垂）
        if behavior == "angry":
            p.setPen(QPen(C_OUTLINE, 4))
            p.drawLine(QPointF(94, 98), QPointF(112, 104))
            p.drawLine(QPointF(128, 104), QPointF(146, 98))
        elif behavior == "sad":
            p.setPen(QPen(C_OUTLINE, 3))
            p.drawLine(QPointF(96, 98), QPointF(112, 102))
            p.drawLine(QPointF(146, 98), QPointF(130, 102))

        # 嘴喙（橙色）
        p.setPen(QPen(C_BEAK_DARK, 2))
        p.setBrush(C_BEAK)
        beak = QPainterPath()
        beak.moveTo(120, 122)
        beak.lineTo(129, 130)
        beak.lineTo(120, 138)
        beak.lineTo(111, 130)
        beak.closeSubpath()
        p.drawPath(beak)

        # 嘴巴（喙下方）
        p.setPen(QPen(C_OUTLINE, 2.5))
        if behavior == "happy":
            p.drawArc(QRectF(104, 138, 32, 16), 0, 180 * 16)          # 微笑
        elif behavior == "sad":
            p.drawArc(QRectF(106, 146, 28, 14), 180 * 16, 180 * 16)   # 撇嘴
        elif behavior == "surprised":
            p.setBrush(QColor(60, 50, 50))
            p.drawEllipse(QRectF(110, 140, 20, 15))                   # 张嘴
        elif behavior == "angry":
            p.drawArc(QRectF(108, 146, 24, 12), 180 * 16, 180 * 16)
        elif behavior == "sleepy":
            p.drawEllipse(QRectF(114, 146, 12, 8))                    # 小 o
        else:
            p.drawArc(QRectF(106, 140, 28, 14), 0, 180 * 16)

    # ---------- 装饰元素 ----------
    def _draw_extras(self, p: QPainter, behavior: str, t: float) -> None:
        if behavior == "happy":
            for i in range(3):
                x = 22 + i * 16
                y = 36 + math.sin(t * 5 + i) * 7
                self._star(p, x, y, 6)
        elif behavior == "angry":
            for i in range(3):
                x = 112 + i * 16
                y = 30 + (t * 40) % 16 - i * 2
                p.setPen(QPen(QColor(165, 165, 170), 2))
                p.setBrush(QColor(232, 232, 235, 180))
                p.drawEllipse(QRectF(x, y, 11, 11))
        elif behavior == "sleepy":
            for i in range(3):
                x = 176 - (t * 28) % 46 + i * 12
                y = 20 + i * 17
                p.setFont(QFont("PingFang SC", 13, QFont.Weight.Bold))
                p.setPen(QPen(C_OUTLINE, 1))
                p.drawText(QPointF(x, y), "z")
        elif behavior == "surprised":
            p.setFont(QFont("PingFang SC", 22, QFont.Weight.Bold))
            p.setPen(QPen(QColor(235, 130, 45), 2))
            p.drawText(QPointF(152, 40), "!")
        elif behavior == "sad":
            p.setPen(QPen(QColor(120, 170, 255), 3))
            p.setBrush(QColor(170, 210, 255))
            y = 70 + (t * 22) % 28
            p.drawEllipse(QRectF(158, y, 9, 13))   # 泪滴滑落

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
        by = 214.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 200))
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
