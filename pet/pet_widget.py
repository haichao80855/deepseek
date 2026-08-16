"""宠物绘制组件 —— 还原参考图的 Q 版企鹅。

配色与比例完全参照参考图：
- 纯黑头背 + 白色大圆眼睛 + 黄色嘴喙 + 红围巾 + 白肚皮 + 黄色脚丫
- 大圆头、小身体，翅膀在身体两侧

6 种行为各有专属表情与动作：
    idle      呼吸起伏 + 眨眼
    happy     蹦跳 + 翅膀扇动 + ^^ 眯眯眼 + 星星
    sad       垂眉 + 眼泪 + 撇嘴 + 身体下沉
    angry     皱眉倒竖 + 冒蒸汽
    surprised 瞪大眼 + 张嘴 + 感叹号 + 一颤
    sleepy    闭眼 + 点头打盹 + 飘 zzz
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from pet.pet_engine import PetEngine

# ---------- 参考图配色 ----------
C_BODY = QColor(22, 24, 30)            # 纯黑（略带蓝调柔和）
C_BODY_HI = QColor(70, 76, 90)         # 高光
C_BELLY = QColor(252, 252, 254)        # 白肚皮
C_BEAK = QColor(248, 180, 20)          # 黄色嘴喙
C_BEAK_DARK = QColor(225, 150, 10)
C_SCARF = QColor(228, 46, 52)          # 红围巾
C_SCARF_DARK = QColor(190, 32, 38)
C_BLUSH = QColor(255, 140, 140, 170)
C_OUTLINE = QColor(15, 17, 22)
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
        self._draw_extras(painter, behavior, t)   # 星星/蒸汽/zzz/感叹号/眼泪
        self._draw_feet(painter, behavior, t)
        self._draw_body(painter, behavior, t)
        self._draw_scarf(painter, behavior, t)
        self._draw_wings(painter, behavior, t)
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

    # ---------- 脚丫（黄色，走路摇摆） ----------
    def _draw_feet(self, p: QPainter, behavior: str, t: float) -> None:
        if behavior == "happy":
            w = math.sin(t * 8.0) * 5.0
        elif behavior == "sleepy":
            w = math.sin(t * 1.5) * 2.0
        else:
            w = math.sin(t * 3.0) * 2.0
        p.setPen(QPen(C_OUTLINE, 2))
        p.setBrush(C_BEAK)
        p.drawEllipse(QRectF(96 + w, 222, 26, 13))
        p.drawEllipse(QRectF(136 - w, 222, 26, 13))

    # ---------- 翅膀（黑色，扇动） ----------
    def _draw_wings(self, p: QPainter, behavior: str, t: float) -> None:
        if behavior == "happy":
            angle = math.sin(t * 8.0) * 30.0
        elif behavior == "surprised":
            angle = -20.0
        elif behavior == "sad":
            angle = 34.0
        elif behavior == "sleepy":
            angle = 18.0
        else:
            angle = math.sin(t * 2.5) * 6.0
        for side in (1, -1):
            p.save()
            p.translate(120 + side * 74, 150)
            p.rotate(side * (16.0 + angle))
            p.setPen(QPen(C_OUTLINE, 2.5))
            p.setBrush(C_BODY)
            p.drawEllipse(QRectF(-11, -22, 22, 44))
            p.restore()

    # ---------- 身体（大圆头 + 小身体的整体轮廓） ----------
    def _body_path(self) -> QPainterPath:
        path = QPainterPath()
        # 从头顶开始，右侧向下（头部宽、身体渐窄）
        path.moveTo(120, 12)
        path.cubicTo(120 + 66, 12, 186, 56, 186, 108)      # 头右侧
        path.cubicTo(186, 150, 180, 186, 178, 200)         # 肩
        path.cubicTo(172, 222, 148, 232, 120, 232)         # 右下收尾
        path.cubicTo(92, 232, 68, 222, 62, 200)            # 左下
        path.cubicTo(60, 186, 54, 150, 54, 108)            # 肩
        path.cubicTo(54, 56, 120 - 66, 12, 120, 12)        # 头左侧
        path.closeSubpath()
        return path

    def _draw_body(self, p: QPainter, behavior: str, t: float) -> None:
        p.setPen(QPen(C_OUTLINE, 3))
        p.setBrush(C_BODY)
        p.drawPath(self._body_path())

        # 头顶高光
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(70, 76, 90, 150))
        p.drawEllipse(QRectF(88, 34, 16, 40))

        # 白肚皮（下半部）
        p.setBrush(C_BELLY)
        p.setPen(QPen(C_OUTLINE, 2))
        p.drawEllipse(QRectF(98, 162, 44, 56))
        # 肚皮高光
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 120))
        p.drawEllipse(QRectF(108, 176, 14, 26))

    # ---------- 红围巾 ----------
    def _draw_scarf(self, p: QPainter, behavior: str, t: float) -> None:
        # 脖间围巾带
        p.setPen(QPen(C_SCARF_DARK, 2))
        p.setBrush(C_SCARF)
        p.drawRoundedRect(QRectF(66, 108, 108, 18), 8, 8)
        # 胸前垂尾（开心时摆动）
        sway = math.sin(t * 5.0) * 4.0 if behavior == "happy" else math.sin(t * 2.0) * 1.5
        tail = QPainterPath(QPointF(118, 126))
        tail.lineTo(124 + sway, 162)
        tail.lineTo(112 + sway, 162)
        tail.closeSubpath()
        p.drawPath(tail)
        # 穗
        p.drawLine(QPointF(124 + sway, 162), QPointF(127 + sway, 169))
        p.drawLine(QPointF(118, 162), QPointF(117 + sway, 169))
        p.drawLine(QPointF(112 + sway, 162), QPointF(109 + sway, 169))

    # ---------- 面部（黑头 + 白色大眼 + 黄色嘴喙） ----------
    def _draw_face(self, p: QPainter, behavior: str, t: float) -> None:
        blink = self._is_blinking(behavior, t)

        # 腮红
        p.setBrush(C_BLUSH)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(70, 78, 20, 12))
        p.drawEllipse(QRectF(150, 78, 20, 12))

        # 眼睛：大白圆 + 黑瞳孔
        eye_r = 16 if behavior == "surprised" else 14
        left_c = QPointF(82, 56)
        right_c = QPointF(121, 56)
        p.setPen(QPen(C_OUTLINE, 2))
        p.setBrush(C_WHITE)
        p.drawEllipse(left_c, eye_r, eye_r)
        p.drawEllipse(right_c, eye_r, eye_r)

        if behavior == "happy":
            # ^ ^ 眯眯眼
            p.setPen(QPen(C_OUTLINE, 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(70, 44, 24, 16), 180 * 16, 180 * 16)
            p.drawArc(QRectF(109, 44, 24, 16), 180 * 16, 180 * 16)
        elif blink:
            p.setPen(QPen(C_OUTLINE, 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(68, 52, 28, 12), 0, 180 * 16)
            p.drawArc(QRectF(107, 52, 28, 12), 0, 180 * 16)
        else:
            # 瞳孔（惊愕时缩小）
            pr = 4 if behavior == "surprised" else 6
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(C_OUTLINE)
            p.drawEllipse(left_c, pr, pr)
            p.drawEllipse(right_c, pr, pr)
            # 高光
            p.setBrush(C_WHITE)
            p.drawEllipse(QPointF(left_c.x() - 3, left_c.y() - 3), 2.5, 2.5)
            p.drawEllipse(QPointF(right_c.x() - 3, right_c.y() - 3), 2.5, 2.5)

        # 眉毛（angry 倒竖 / sad 微垂）
        if behavior == "angry":
            p.setPen(QPen(C_OUTLINE, 4))
            p.drawLine(QPointF(64, 30), QPointF(92, 42))
            p.drawLine(QPointF(108, 42), QPointF(136, 30))
        elif behavior == "sad":
            p.setPen(QPen(C_OUTLINE, 3))
            p.drawLine(QPointF(68, 32), QPointF(92, 40))
            p.drawLine(QPointF(136, 32), QPointF(108, 40))

        # 黄色嘴喙（菱形）
        p.setPen(QPen(C_BEAK_DARK, 2))
        p.setBrush(C_BEAK)
        beak = QPainterPath()
        beak.moveTo(120, 76)
        beak.lineTo(130, 88)
        beak.lineTo(120, 100)
        beak.lineTo(110, 88)
        beak.closeSubpath()
        p.drawPath(beak)

        # 嘴巴（喙下）
        p.setPen(QPen(C_OUTLINE, 2.5))
        if behavior == "happy":
            p.drawArc(QRectF(104, 100, 32, 16), 0, 180 * 16)           # 微笑
        elif behavior == "sad":
            p.drawArc(QRectF(106, 110, 28, 14), 180 * 16, 180 * 16)    # 撇嘴
        elif behavior == "surprised":
            p.setBrush(QColor(60, 50, 50))
            p.drawEllipse(QRectF(110, 104, 20, 15))                    # 张嘴
        elif behavior == "angry":
            p.drawArc(QRectF(108, 110, 24, 12), 180 * 16, 180 * 16)
        elif behavior == "sleepy":
            p.drawEllipse(QRectF(114, 110, 12, 8))                     # 小 o
        else:
            p.drawArc(QRectF(106, 104, 28, 14), 0, 180 * 16)

    # ---------- 装饰元素 ----------
    def _draw_extras(self, p: QPainter, behavior: str, t: float) -> None:
        if behavior == "happy":
            for i in range(3):
                x = 20 + i * 16
                y = 34 + math.sin(t * 5 + i) * 7
                self._star(p, x, y, 6)
        elif behavior == "angry":
            for i in range(3):
                x = 110 + i * 16
                y = 26 + (t * 40) % 16 - i * 2
                p.setPen(QPen(QColor(165, 165, 170), 2))
                p.setBrush(QColor(232, 232, 235, 180))
                p.drawEllipse(QRectF(x, y, 11, 11))
        elif behavior == "sleepy":
            for i in range(3):
                x = 172 - (t * 28) % 46 + i * 12
                y = 16 + i * 17
                p.setFont(QFont("PingFang SC", 13, QFont.Weight.Bold))
                p.setPen(QPen(C_OUTLINE, 1))
                p.drawText(QPointF(x, y), "z")
        elif behavior == "surprised":
            p.setFont(QFont("PingFang SC", 22, QFont.Weight.Bold))
            p.setPen(QPen(QColor(235, 130, 45), 2))
            p.drawText(QPointF(152, 36), "!")
        elif behavior == "sad":
            p.setPen(QPen(QColor(120, 170, 255), 3))
            p.setBrush(QColor(170, 210, 255))
            y = 66 + (t * 22) % 28
            p.drawEllipse(QRectF(160, y, 9, 13))   # 泪滴滑落

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
