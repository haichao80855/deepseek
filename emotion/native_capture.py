"""原生 AVFoundation 摄像头采集（pyobjc）。

为什么需要它：
- OpenCV 5.x 的 AVFoundation 后端对 Mac 内置 FaceTime 相机不可靠
  （isOpened=True 但 read() 永远返回空，与权限/格式无关，OpenCV 4.x 同样）；
- 原生 AVFoundation（本模块走的正是它）在同样的系统状态下始终稳定出帧。

实现要点：
- AVCaptureSession + AVCaptureVideoDataOutput，强制 BGRA 像素格式输出
  （默认是 16 位 yuv2，OpenCV 不兼容）；
- 采样回调在独立 dispatch 队列线程执行，转换后存最新帧，主线程 read() 取。
"""
from __future__ import annotations

import threading

import AVFoundation
import CoreMedia
import Quartz
import dispatch
import numpy as np
import objc
from Foundation import NSObject

# BGRA 四字节像素格式（OpenCV BGR 加一个 A 通道）
_PIXEL_FORMAT_BGRA = Quartz.CoreVideo.kCVPixelFormatType_32BGRA
_PIXEL_FORMAT_KEY = Quartz.CoreVideo.kCVPixelBufferPixelFormatTypeKey


class _SampleBufferDelegate(NSObject):
    """AVCaptureVideoDataOutput 采样回调（在 dispatch 队列线程上执行）。

    注意：必须用 objc.super（不能用 super()），否则 delegate 初始化失败，
    导致永远收不到帧回调。
    """

    def initWithCallback_(self, callback):
        self = objc.super(_SampleBufferDelegate, self).init()
        if self is None:
            return None
        self._callback = callback
        return self

    def captureOutput_didOutputSampleBuffer_fromConnection_(
        self, output, sample_buffer, connection
    ):
        self._callback(sample_buffer)


def _sample_buffer_to_bgr(sample_buffer) -> np.ndarray | None:
    """把 CMSampleBuffer 转成 BGR numpy 数组；失败返回 None。"""
    try:
        pixel_buffer = CoreMedia.CMSampleBufferGetImageBuffer(sample_buffer)
        if pixel_buffer is None:
            return None
        cv = Quartz.CoreVideo
        w = cv.CVPixelBufferGetWidth(pixel_buffer)
        h = cv.CVPixelBufferGetHeight(pixel_buffer)
        row_bytes = cv.CVPixelBufferGetBytesPerRow(pixel_buffer)
        if w <= 0 or h <= 0:
            return None
        cv.CVPixelBufferLockBaseAddress(pixel_buffer, 0)
        try:
            base = cv.CVPixelBufferGetBaseAddress(pixel_buffer)
            data = base.as_buffer(h * row_bytes)
            arr = np.frombuffer(data, dtype=np.uint8).reshape(h, row_bytes)
            if row_bytes == w * 4:      # BGRA
                return arr[:, : w * 4].reshape(h, w, 4)[:, :, :3].copy()
            if row_bytes == w * 3:      # RGB24 -> BGR
                return arr[:, : w * 3].reshape(h, w, 3)[:, :, ::-1].copy()
            return None                # 其他格式（如 yuv2）暂不支持
        finally:
            cv.CVPixelBufferUnlockBaseAddress(pixel_buffer, 0)
    except Exception:
        return None


class NativeCameraCapture:
    """原生 AVFoundation 摄像头，接口与 OpenCV CameraCapture 兼容（read/release/with）。"""

    def __init__(
        self,
        device: int = 0,
        width: int = 640,
        height: int = 480,
        first_frame_timeout: float = 8.0,
    ) -> None:
        self._queue = dispatch.dispatch_queue_create(b"cam.capture", None)
        self._lock = threading.Lock()
        self._latest: np.ndarray | None = None
        self._first_frame = threading.Event()
        self._session = None
        self._running = False

        devices = AVFoundation.AVCaptureDevice.devicesWithMediaType_(
            AVFoundation.AVMediaTypeVideo
        )
        if device >= len(devices):
            raise RuntimeError(
                f"设备索引 {device} 超出范围（共 {len(devices)} 个摄像头设备）"
            )
        dev = devices[device]

        dev_input, err = AVFoundation.AVCaptureDeviceInput.deviceInputWithDevice_error_(
            dev, None
        )
        if dev_input is None:
            raise RuntimeError(f"无法创建摄像头输入: {err}")

        session = AVFoundation.AVCaptureSession.alloc().init()
        # 限制分辨率，减少 CPU 占用（不设置时 FaceTime 相机默认给 1080p）
        session.setSessionPreset_(AVFoundation.AVCaptureSessionPreset640x480)
        session.addInput_(dev_input)

        output = AVFoundation.AVCaptureVideoDataOutput()
        # 强制 BGRA 输出（默认 yuv2 无法直接转 OpenCV BGR）
        output.setVideoSettings_(
            {_PIXEL_FORMAT_KEY: _PIXEL_FORMAT_BGRA}
        )
        self._delegate = _SampleBufferDelegate.alloc().initWithCallback_(
            self._on_sample_buffer
        )
        output.setSampleBufferDelegate_queue_(self._delegate, self._queue)
        session.addOutput_(output)

        self._session = session
        session.startRunning()
        self._running = True

        # 等待首帧，确认摄像头真的能出帧（原生路径也验证，避免静默失败）
        if not self._first_frame.wait(timeout=first_frame_timeout):
            self.release()
            raise RuntimeError(
                "原生摄像头 8 秒内未产出帧，摄像头可能被占用或硬件异常"
            )

    # ---------- 内部 ----------
    def _on_sample_buffer(self, sample_buffer) -> None:
        frame = _sample_buffer_to_bgr(sample_buffer)
        if frame is None:
            return
        with self._lock:
            self._latest = frame
        self._first_frame.set()

    # ---------- 对外接口（与 OpenCV CameraCapture 一致） ----------
    def read(self):
        with self._lock:
            return self._latest

    def release(self) -> None:
        if self._running and self._session is not None:
            self._session.stopRunning()
            self._running = False

    def __enter__(self) -> "NativeCameraCapture":
        return self

    def __exit__(self, *exc) -> None:
        self.release()
