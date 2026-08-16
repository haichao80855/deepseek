"""M1 Demo：摄像头实时情绪识别（终端打印）。

用法：
    .venv/bin/python main.py                # 实时识别，带调试窗口（画人脸框+情绪标签）
    .venv/bin/python main.py --headless     # 无窗口，纯终端输出
    .venv/bin/python main.py --device 1     # 使用第二个摄像头

按 q 退出。无人脸时提示"未检测到人脸"。
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import cv2

from emotion.capture import CameraCapture
from emotion.detector import EmotionDetector
from emotion.smoother import EmotionSmoother

MODEL_PATH = os.path.join(os.path.dirname(__file__), "emotion", "models", "emotion-ferplus-8.onnx")

# 情绪 -> 终端安慰语（M4 会升级为 TTS 语音）
COMFORT = {
    "sadness": "  🫂 别难过，我一直都在呀",
    "anger": "  🧘 深呼吸，我陪你把坏情绪慢慢吐掉",
    "fear": "  🫂 别怕，有我在",
    "disgust": "  🤔 是什么让你不舒服啦？",
    "contempt": "  🙂 好啦好啦，别太当真～",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="摄像头实时情绪识别 Demo")
    parser.add_argument("--device", type=int, default=0, help="摄像头设备号")
    parser.add_argument("--headless", action="store_true", help="不显示调试窗口")
    parser.add_argument("--fps", type=float, default=15.0, help="推理帧率上限")
    args = parser.parse_args()

    if not os.path.exists(MODEL_PATH):
        print(f"[错误] 找不到模型文件: {MODEL_PATH}")
        print("请先下载 emotion-ferplus-8.onnx 到 emotion/models/ 目录。")
        return 1

    detector = EmotionDetector(MODEL_PATH)
    smoother = EmotionSmoother()
    last_hint_time = 0.0

    print("=" * 56)
    print("  情绪感知 Demo (M1)")
    print("  模型: FER+ (8 类情绪) | 按 q 退出")
    print("=" * 56)

    try:
        with CameraCapture(args.device) as cam:
            print(f"✅ 摄像头已开启 (设备 {args.device})，正在实时识别……")
            print("   请正对摄像头；窗口里出现绿色人脸框即识别中。按 q 退出。\n")
            frame_interval = 1.0 / args.fps
            next_frame_time = time.monotonic()
            face_seen = False
            last_noface_hint = 0.0

            while True:
                # 限帧，避免每帧都跑模型浪费 CPU
                now = time.monotonic()
                if now < next_frame_time:
                    time.sleep(0.005)
                    continue
                next_frame_time = now + frame_interval

                frame = cam.read()
                if frame is None:
                    now_t = time.monotonic()
                    if now_t - last_hint_time >= 5.0:
                        last_hint_time = now_t
                        print("[提示] 未获取到画面。常见原因：")
                        print("  1. 摄像头权限未授予：系统设置 → 隐私与安全性 → 摄像头，"
                              "打开你运行本程序的 App（终端/iTerm/VS Code）的开关，并重启该 App；")
                        print("  2. 摄像头正被其他 App 占用（如 FaceTime、Zoom），请先关闭；")
                        print("  3. 若你用的是 iPhone 连续互通相机，可先在系统设置 → 通用 → "
                              "AirDrop 与隔空播放 → 连续互通相机 里关闭。")
                    time.sleep(0.5)
                    continue

                result = detector.analyze(frame)
                if result is not None and not face_seen:
                    face_seen = True
                    print("👤 检测到人脸，开始识别情绪……")
                elif result is None and face_seen:
                    face_seen = False
                    print("👤 人脸离开画面……")

                emotion = smoother.update(result)

                if emotion is not None:
                    zh = {"sadness": "难过", "anger": "生气", "fear": "恐惧",
                          "disgust": "厌恶", "contempt": "轻蔑", "happiness": "开心",
                          "surprise": "惊讶", "neutral": "平静"}[emotion]
                    msg = f"[{time.strftime('%H:%M:%S')}] 检测到情绪: {zh} ({emotion})"
                    msg += COMFORT.get(emotion, "")
                    print(msg)

                # 调试窗口：画人脸框 + 情绪标签
                if not args.headless and result is not None:
                    x, y, w, h = result["bbox"]
                    label = f"{result['emotion_zh']} {result['confidence']:.0%}"
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, label, (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    try:
                        cv2.imshow("EmotionCam (按 q 退出)", frame)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break
                    except cv2.error as e:
                        # 当前环境无法创建 GUI 窗口（如无图形会话），自动退化为终端模式
                        print(f"[提示] 无法显示调试窗口（{e}），已切换为终端输出模式。")
                        args.headless = True
    except RuntimeError as e:
        print(f"[错误] {e}")
        return 1
    finally:
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())
