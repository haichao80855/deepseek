"""摄像头采集模块（OpenCV）。

负责打开 Mac 内置摄像头并逐帧读取画面。
macOS 首次运行会弹出「摄像头权限」系统授权框，需在
「系统设置 → 隐私与安全性 → 摄像头」中允许（权限挂在运行本程序的 App 上）。
"""
from __future__ import annotations

import sys

import cv2

# macOS 显式指定 AVFoundation 后端，避免默认后端兼容问题
_BACKEND = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else None


class CameraCapture:
    """OpenCV 摄像头封装，支持 with 语法自动释放。"""

    def __init__(self, device: int = 0, width: int = 640, height: int = 480) -> None:
        if _BACKEND is not None:
            self._cap = cv2.VideoCapture(device, _BACKEND)
        else:
            self._cap = cv2.VideoCapture(device)
        if not self._cap.isOpened():
            raise RuntimeError(
                "无法打开摄像头（权限未授予或设备不可用）。\n"
                "请检查：系统设置 → 隐私与安全性 → 摄像头\n"
                "  1. 找到你运行本程序的 App（终端 / Terminal / iTerm2 / VS Code）并打开开关；\n"
                "  2. 如果列表里没有，先运行一次本程序触发授权弹窗，再回来打开；\n"
                "  3. 授权后【完全退出并重新打开】该 App（权限改动需重启才生效），再运行本程序。"
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def read(self):
        """读取一帧 BGR 图像；失败返回 None。

        说明：macOS 上即使未授权，isOpened 也可能为 True，
        但 read 会持续返回 None —— 此时多半是权限问题或摄像头被占用。
        """
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "CameraCapture":
        return self

    def __exit__(self, *exc) -> None:
        self.release()
