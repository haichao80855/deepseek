"""宠物主窗口。

- 无边框 + 透明背景 + 置顶 + 不出现在 Dock/任务栏（Qt.Tool）
- 鼠标拖拽移动
- 按键：1~6 切换行为，空格 让宠物说话，Esc 退出
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QWidget

from pet.pet_engine import BEHAVIORS, EMOTION_ZH, PetEngine
from pet.pet_widget import PetWidget


class PetWindow(QWidget):
    """桌面宠物窗口。"""

    def __init__(self, engine: PetEngine | None = None) -> None:
        super().__init__()
        self._engine = engine or PetEngine()
        self._drag_offset: QPoint | None = None

        # 无边框 / 置顶 / 工具窗口（不进 Dock）
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._pet = PetWidget(self._engine, self)
        self._pet.move(0, 0)

        self.setFixedSize(self._pet.size())
        self._place_default()

        # 初始打个招呼
        self._pet.say()

    def _place_default(self) -> None:
        """默认放屏幕右下角。"""
        from PyQt6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(geo.right() - self.width() - 40, geo.bottom() - self.height() - 60)

    # ---------- 拖拽 ----------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setFocus()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = None

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        # 双击让宠物说话
        self._pet.say()
        super().mouseDoubleClickEvent(event)

    # ---------- M3: 情绪驱动 ----------
    def apply_emotion(self, emotion: str) -> None:
        """收到平滑后的情绪键，切换宠物行为。"""
        behavior = self._engine.apply_emotion(emotion)
        if behavior:
            zh = EMOTION_ZH.get(emotion, emotion)
            print(f"😊 情绪: {zh} → 行为: {behavior}")
            # 切换后由 PetWidget._tick 自动弹气泡文案
        self._pet.update()

    def on_face_status(self, visible: bool) -> None:
        """人脸离开/回来提示。"""
        if not visible:
            self._pet._show_msg("咦？你去哪啦？", 3.0)

    # ---------- 键盘 ----------
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
            return
        if key == Qt.Key.Key_Space:
            self._pet.say()
            return
        # 1~6 切换行为
        idx = key - Qt.Key.Key_1
        if 0 <= idx < len(BEHAVIORS):
            behavior = list(BEHAVIORS.keys())[idx]
            if self._engine.set(behavior):
                self._pet.say()
            return
        super().keyPressEvent(event)
