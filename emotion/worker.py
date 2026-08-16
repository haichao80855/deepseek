"""后台情绪识别线程（QThread + 信号桥接）。

摄像头采集、人脸检测、表情识别、情绪平滑全部在独立线程执行，
避免阻塞 Qt UI 主线程；结果通过 Qt 信号发回主线程。
"""
from __future__ import annotations

import threading
import time

import cv2
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from emotion.capture import create_camera


class EmotionWorker(QObject):
    """运行在 QThread 里的情绪识别循环。"""

    emotion_changed = pyqtSignal(str)   # 平滑后的情绪键（如 "happiness"）
    face_status = pyqtSignal(bool)      # 是否检测到人脸
    error = pyqtSignal(str)             # 错误消息

    def __init__(self, detector, smoother, device: int = 0,
                 detect_fps: float = 8.0, no_face_timeout: float = 10.0) -> None:
        super().__init__()
        self._detector = detector
        self._smoother = smoother
        self._device = device
        self._interval = 1.0 / detect_fps
        self._no_face_timeout = no_face_timeout
        self._stop = threading.Event()
        self._face_reported = False

    def stop(self) -> None:
        self._stop.set()

    @pyqtSlot()
    def run(self) -> None:
        try:
            with create_camera(self._device) as cam:
                last_face_seen = time.monotonic()
                next_t = 0.0
                while not self._stop.is_set():
                    now = time.monotonic()
                    if now < next_t:
                        time.sleep(0.01)
                        continue
                    next_t = now + self._interval

                    frame = cam.read()
                    if frame is None:
                        time.sleep(0.1)
                        continue

                    # 降采样后再识别，省 CPU（原生采集是 1080p）
                    h, w = frame.shape[:2]
                    if w > 480:
                        scale = 480.0 / w
                        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

                    result = self._detector.analyze(frame)

                    # 人脸存在性（用于"看不到你"提示）
                    if result is not None:
                        last_face_seen = now
                        if not self._face_reported:
                            self._face_reported = True
                            self.face_status.emit(True)
                    elif self._face_reported and now - last_face_seen > self._no_face_timeout:
                        self._face_reported = False
                        self.face_status.emit(False)

                    emotion = self._smoother.update(result)
                    if emotion is not None:
                        self.emotion_changed.emit(emotion)
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))
        finally:
            self._stop.set()
