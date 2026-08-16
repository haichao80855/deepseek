"""桌面宠物 M2：透明置顶宠物窗口。

用法：
    .venv/bin/python -m pet

按键：
    1~6   切换行为（日常/开心/难过/生气/惊讶/困困）
    空格  让宠物说话
    双击  让宠物说话
    Esc   退出
"""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from pet.main_window import PetWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    win = PetWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
