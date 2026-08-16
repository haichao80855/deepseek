"""M3 集成入口：摄像头情绪 → 桌面宠物联动。

用法：
    .venv/bin/python app.py            # 摄像头实时情绪驱动宠物
    .venv/bin/python app.py --demo     # 演示模式：循环假情绪，无需摄像头

按键（宠物窗口获得焦点时）：
    1~6   手动切换行为    空格/双击  说话
    Esc   退出
"""
from __future__ import annotations

import argparse
import os
import sys
import threading

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication

from emotion.detector import EmotionDetector
from emotion.smoother import EmotionSmoother
from emotion.worker import EmotionWorker
from pet.main_window import PetWindow

MODEL_PATH = os.path.join(os.path.dirname(__file__), "emotion", "models", "emotion-ferplus-8.onnx")

# 演示模式的情绪序列（每 3 秒切换一次）
_DEMO_SEQUENCE = ["happiness", "sadness", "anger", "surprise", "neutral", "sleepy"]


def _run_demo_worker(pet_window, stop: threading.Event) -> None:
    """演示模式：每 3 秒模拟一种情绪，验证宠物行为联动。"""
    idx = 0
    while not stop.wait(3.0):
        emo = _DEMO_SEQUENCE[idx % len(_DEMO_SEQUENCE)]
        pet_window.apply_emotion(emo)
        idx += 1


def main() -> int:
    parser = argparse.ArgumentParser(description="情绪感知桌面宠物 (M3)")
    parser.add_argument("--demo", action="store_true", help="演示模式（无摄像头）")
    parser.add_argument("--device", type=int, default=0, help="摄像头设备号")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    win = PetWindow()
    win.show()

    if args.demo:
        print("🎭 演示模式：每 3 秒切换一种情绪，验证宠物行为联动")
        stop = threading.Event()
        t = threading.Thread(
            target=_run_demo_worker, args=(win, stop), daemon=True
        )
        t.start()
        ret = app.exec()
        stop.set()
        t.join(timeout=2)
        return ret

    if not os.path.exists(MODEL_PATH):
        print(f"[错误] 找不到模型文件: {MODEL_PATH}")
        return 1

    detector = EmotionDetector(MODEL_PATH)
    smoother = EmotionSmoother()
    worker = EmotionWorker(detector, smoother, device=args.device)

    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.emotion_changed.connect(win.apply_emotion)
    worker.face_status.connect(win.on_face_status)
    worker.error.connect(lambda e: print(f"[错误] 摄像头线程: {e}"))
    thread.start()

    print("🐾 情绪感知宠物已启动（Esc 退出）")

    ret = app.exec()

    # 收尾：停线程
    worker.stop()
    thread.quit()
    thread.wait(3000)
    return ret


if __name__ == "__main__":
    sys.exit(main())
