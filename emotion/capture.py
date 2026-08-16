"""摄像头采集模块（OpenCV）。

负责打开 Mac 内置摄像头并逐帧读取画面。

已知问题与对策：
- OpenCV 5.x 在 macOS 上打开内置 FaceTime 相机时，默认格式协商失败，
  isOpened() 为 True 但 read() 永远返回空帧。对策：显式指定 AVFoundation
  后端 + 强制 MJPG 编码格式（已验证可正常出帧）。
- macOS 首次运行会弹出「摄像头权限」授权框；若被拒绝，需在
  「系统设置 → 隐私与安全性 → 摄像头」中允许运行本程序的 App。
"""
from __future__ import annotations

import sys
import time

import cv2

_MJPG = cv2.VideoWriter_fourcc(*"MJPG")


class CameraCapture:
    """OpenCV 摄像头封装，支持 with 语法自动释放。"""

    def __init__(
        self,
        device: int = 0,
        width: int = 640,
        height: int = 480,
        warmup_frames: int = 5,
    ) -> None:
        if sys.platform == "darwin":
            self._cap = cv2.VideoCapture(device, cv2.CAP_AVFOUNDATION)
            # 强制 MJPG：规避 OpenCV 5.x 与 FaceTime 内置相机格式协商失败的问题
            self._cap.set(cv2.CAP_PROP_FOURCC, _MJPG)
        else:
            self._cap = cv2.VideoCapture(device)
        if not self._cap.isOpened():
            raise RuntimeError(
                "无法打开摄像头（权限未授予或设备不可用）。\n"
                "请检查：系统设置 → 隐私与安全性 → 摄像头\n"
                "  1. 找到你运行本程序的 App（终端 / Terminal / iTerm2 / VS Code）并打开开关；\n"
                "  2. 授权后【完全退出并重新打开】该 App（权限改动需重启才生效），再运行本程序。"
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        # 预热：AVFoundation 打开后头几帧可能为空，先读掉
        for _ in range(warmup_frames):
            if self.read() is not None:
                break
            time.sleep(0.1)

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
