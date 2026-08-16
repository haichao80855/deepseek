"""人脸检测 + 表情识别模块。

- 人脸检测：OpenCV YuNet（DNN，CPU 实时，支持侧脸/俯仰，输出 5 个关键点）
- 表情识别：FER+ ONNX 模型（emotion-ferplus-8），8 类情绪
  输入 1x1x64x64 灰度 float（0~255，不做归一化），输出 softmax 概率
"""
from __future__ import annotations

import os

import cv2
import numpy as np
import onnxruntime as ort

# FER+ 模型输出顺序（与模型 README 一致）
EMOTIONS = [
    "neutral",
    "happiness",
    "surprise",
    "sadness",
    "anger",
    "disgust",
    "fear",
    "contempt",
]

EMOTIONS_ZH = {
    "neutral": "平静",
    "happiness": "开心",
    "surprise": "惊讶",
    "sadness": "难过",
    "anger": "生气",
    "disgust": "厌恶",
    "fear": "恐惧",
    "contempt": "轻蔑",
}

DEFAULT_YUNET_PATH = os.path.join(
    os.path.dirname(__file__), "models", "face_detection_yunet_2023mar.onnx"
)


def softmax(scores: np.ndarray) -> np.ndarray:
    """数值稳定的 softmax。"""
    scores = scores - np.max(scores)
    exp = np.exp(scores)
    return exp / np.sum(exp)


class EmotionDetector:
    """人脸检测 + 表情识别一体封装。"""

    def __init__(
        self,
        model_path: str,
        yunet_path: str = DEFAULT_YUNET_PATH,
        score_threshold: float = 0.6,
    ) -> None:
        self._sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self._input_name = self._sess.get_inputs()[0].name
        self._output_name = self._sess.get_outputs()[0].name

        self._ynet = cv2.FaceDetectorYN.create(
            yunet_path,
            "",
            (320, 320),          # 初始输入尺寸，实际随帧大小自动调整
            score_threshold=score_threshold,
            nms_threshold=0.3,
            top_k=5000,
        )

    # ---------- 人脸检测 ----------
    def detect_face(self, frame_bgr: np.ndarray):
        """检测画面中置信度最高的人脸。

        返回 (人脸BGR裁剪, dict{bbox, landmarks, score})；无人脸返回 None。
        landmarks 为 5 个关键点（左眼/右眼/鼻尖/左嘴角/右嘴角），供后续里程碑使用。
        """
        h, w = frame_bgr.shape[:2]
        self._ynet.setInputSize((w, h))
        ok, faces = self._ynet.detect(frame_bgr)
        if not ok or faces is None or len(faces) == 0:
            return None

        best = int(np.argmax(faces[:, -1]))  # 取置信度最高的人脸
        x, y, fw, fh = faces[best][:4].astype(int)

        # YuNet 返回的框可能超出画面边界（人脸贴近镜头/画面边缘时），
        # 直接裁剪会得到空数组导致 cvtColor 报错，这里把框裁剪到画面内。
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(w, x + fw), min(h, y + fh)
        if x1 <= x0 or y1 <= y0:
            return None  # 人脸框完全在画面外，跳过本帧

        landmarks = faces[best][4:14].reshape(5, 2)
        score = float(faces[best][-1])
        return frame_bgr[y0:y1, x0:x1], {
            "bbox": (x, y, fw, fh),
            "landmarks": landmarks,
            "score": score,
        }

    # ---------- 表情识别 ----------
    def predict(self, face_bgr: np.ndarray):
        """对单张人脸做表情分类，返回 (情绪英文名, 置信度, 8类概率数组)。"""
        if face_bgr is None or face_bgr.size == 0:
            raise ValueError("predict 收到空的人脸图像，请检查人脸检测返回的裁剪框")
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
        blob = resized.astype(np.float32).reshape(1, 1, 64, 64)
        scores = self._sess.run([self._output_name], {self._input_name: blob})[0][0]
        probs = softmax(scores)
        top = int(np.argmax(probs))
        return EMOTIONS[top], float(probs[top]), probs

    # ---------- 一步到位 ----------
    def analyze(self, frame_bgr: np.ndarray):
        """人脸检测 + 表情识别。

        返回 dict：
            emotion     情绪英文名（EMOTIONS 之一）
            emotion_zh  情绪中文名
            confidence  置信度 (0~1)
            probs       8 类概率数组
            bbox        人脸边界框 (x, y, w, h)
            landmarks   5 个人脸关键点
            face_score  人脸检测置信度
        无人脸时返回 None。
        """
        det = self.detect_face(frame_bgr)
        if det is None:
            return None
        face, meta = det
        emotion, confidence, probs = self.predict(face)
        return {
            "emotion": emotion,
            "emotion_zh": EMOTIONS_ZH[emotion],
            "confidence": confidence,
            "probs": probs,
            "bbox": meta["bbox"],
            "landmarks": meta["landmarks"],
            "face_score": meta["score"],
        }
