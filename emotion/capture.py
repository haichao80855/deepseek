"""摄像头采集模块（OpenCV）。

负责打开 Mac 内置摄像头并逐帧读取画面。
macOS 首次运行会弹出「摄像头权限」系统授权框，需在
「系统设置 → 隐私与安全性 → 摄像头」中允许（权限挂在终端或 App 上）。
"""
from __future__ import annotations

import cv2


class CameraCapture:
    """OpenCV 摄像头封装，支持 with 语法自动释放。"""

    def __init__(self, device: int = 0, width: int = 640, height: int = 480) -> None:
        self._cap = cv2.VideoCapture(device)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"无法打开摄像头设备 {device}。"
                "请检查系统设置 → 隐私与安全性 → 摄像头 是否允许本终端/应用访问。"
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def read(self):
        """读取一帧 BGR 图像；失败返回 None。"""
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
