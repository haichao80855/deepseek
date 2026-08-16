"""摄像头采集模块。

macOS 上优先使用原生 AVFoundation 采集（emotion/native_capture.py）：
OpenCV 5.x 的 AVFoundation 后端对内置 FaceTime 相机不可靠（isOpened=True
但 read() 永远返回空帧），原生路径经实测始终稳定。原生失败时回退 OpenCV。

权限说明：macOS 首次运行会弹出「摄像头权限」系统授权框，需在
「系统设置 → 隐私与安全性 → 摄像头」中允许（权限挂在运行本程序的 App 上）。
"""
from __future__ import annotations

import sys

import cv2

from emotion.native_capture import NativeCameraCapture


class CameraCapture:
    """OpenCV 摄像头封装，支持 with 语法自动释放。"""

    def __init__(self, device: int = 0, width: int = 640, height: int = 480) -> None:
        self._cap = cv2.VideoCapture(device, cv2.CAP_AVFOUNDATION)
        if not self._cap.isOpened():
            raise RuntimeError(
                "无法打开摄像头（权限未授予或设备不可用）。\n"
                "请检查：系统设置 → 隐私与安全性 → 摄像头\n"
                "  1. 找到你运行本程序的 App（终端 / Terminal / iTerm2 / VS Code）并打开开关；\n"
                "  2. 授权后【完全退出并重新打开】该 App（权限改动需重启才生效），再运行本程序。"
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


def create_camera(device: int = 0, width: int = 640, height: int = 480):
    """创建摄像头采集器。

    macOS：优先原生 AVFoundation（对 FaceTime 内置相机稳定），失败回退 OpenCV。
    其他平台：直接 OpenCV。
    """
    if sys.platform == "darwin":
        try:
            cam = NativeCameraCapture(device, width, height)
            print(f"📷 使用原生采集（AVFoundation），设备 {device}")
            return cam
        except Exception as e:  # noqa: BLE001 - 回退路径
            print(f"⚠️  原生采集失败（{e}），回退 OpenCV…")
    cam = CameraCapture(device, width, height)
    print(f"📷 使用 OpenCV 采集，设备 {device}")
    return cam
