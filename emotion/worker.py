"""后台情绪识别线程（QThread + 信号桥接）。

摄像头采集、人脸检测、表情识别、情绪平滑全部在独立线程执行，
避免阻塞 Qt UI 主线程；结果通过 Qt 信号发回主线程。

--debug 模式下会额外弹出 cv2 调试窗口（人脸框 + 情绪标签），
并定期在终端打印检测状态，便于排查"表情没反应"类问题。
"""
from __future__ import annotations

import threading
import time

import cv2
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from emotion.capture import create_camera
from emotion.detector import EMOTIONS, EMOTIONS_ZH


class EmotionWorker(QObject):
    """运行在 QThread 里的情绪识别循环。"""

    emotion_changed = pyqtSignal(str, float)  # (情绪键, 该情绪置信度)
    face_status = pyqtSignal(bool)      # 是否检测到人脸
    error = pyqtSignal(str)             # 错误消息
    debug_frame = pyqtSignal(object)    # 调试模式：标注后的 BGR 帧（numpy）

    def __init__(self, detector, smoother, device: int = 0,
                 detect_fps: float = 8.0, no_face_timeout: float = 8.0,
                 debug: bool = False) -> None:
        super().__init__()
        self._detector = detector
        self._smoother = smoother
        self._device = device
        self._interval = 1.0 / detect_fps
        self._no_face_timeout = no_face_timeout
        self._debug = debug
        self._stop = threading.Event()
        self._face_reported = False
        self._last_status_log = 0.0

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

                    # 摄像头帧是否还在更新（防休眠/卡死）
                    if not cam.is_fresh(2.0):
                        self._log_status("摄像头无新帧")
                        time.sleep(0.5)
                        continue

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

                    # 人脸存在性（用于"看不到你"提示 + 状态日志）
                    if result is not None:
                        last_face_seen = now
                        if not self._face_reported:
                            self._face_reported = True
                            self.face_status.emit(True)
                            self._log_status(f"检测到人脸，开始识别情绪")
                        if self._debug:
                            self._debug_draw(frame, result)
                    elif self._face_reported and now - last_face_seen > self._no_face_timeout:
                        self._face_reported = False
                        self.face_status.emit(False)
                        self._log_status("人脸离开画面")

                    emotion = self._smoother.update(result)
                    if emotion is not None:
                        # 附带该情绪的置信度，便于诊断
                        conf = 0.0
                        if result is not None:
                            try:
                                conf = float(result["probs"][EMOTIONS.index(emotion)])
                            except (ValueError, IndexError):
                                conf = result.get("confidence", 0.0)
                        self.emotion_changed.emit(emotion, conf)
                        if self._debug:
                            self._log_status(
                                f"平滑输出: {EMOTIONS_ZH.get(emotion, emotion)} ({conf:.0%})"
                            )
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))
        finally:
            self._stop.set()

    # ---------- 辅助 ----------
    def _log_status(self, msg: str) -> None:
        now = time.monotonic()
        if now - self._last_status_log < 1.0:
            return  # 至少间隔 1 秒，避免刷屏
        self._last_status_log = now
        print(f"[相机] {msg}", flush=True)

    def _debug_draw(self, frame, result) -> None:
        """调试模式：画人脸框 + 情绪标签 + top3，发信号给 UI 显示。"""
        x, y, w, h = result["bbox"]
        label = f"{result['emotion_zh']} {result['confidence']:.0%}"
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(frame, label, (x, max(10, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        # top3 情绪
        top = sorted(zip(EMOTIONS, result["probs"]), key=lambda p: -p[1])[:3]
        txt = "  ".join(f"{EMOTIONS_ZH[e]}:{p:.0%}" for e, p in top)
        cv2.putText(frame, txt, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 60), 2)
        self.debug_frame.emit(frame.copy())
