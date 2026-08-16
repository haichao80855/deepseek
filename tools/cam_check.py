#!/usr/bin/env python3
"""相机诊断 + 自动授权修复工具。

在你的终端里运行:
    .venv/bin/python tools/cam_check.py

它会:
1. 用原生 AVFoundation 检查当前 App 的摄像头授权状态(未授权则弹窗请求)
2. 列出系统摄像头
3. 用 OpenCV(MJPG 修复版)实测取帧
把完整输出发给我即可。
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWIFT_SRC = os.path.join(ROOT, "tools", "cam_status.swift")


def run_native(request: bool) -> None:
    """用 swift script 模式运行原生检测(反映当前 App 的 TCC 权限)。"""
    print("[1/3] 原生授权状态检查...")
    cmd = ["swift", SWIFT_SRC] + (["request"] if request else [])
    env = dict(os.environ)
    # 让 clang 模块缓存写到可写位置，避免权限问题
    env["CLANG_MODULE_CACHE_PATH"] = os.path.join(ROOT, ".clang-modcache")
    os.makedirs(env["CLANG_MODULE_CACHE_PATH"], exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=90, env=env)
    print(r.stdout)
    if r.stderr.strip():
        print("stderr:", r.stderr.strip()[:500])


def run_opencv() -> None:
    print("[2/3] OpenCV 实测取帧 (MJPG 修复版)...")
    import cv2

    MJPG = cv2.VideoWriter_fourcc(*"MJPG")
    for dev in (0, 1):
        cap = cv2.VideoCapture(dev, cv2.CAP_AVFOUNDATION)
        cap.set(cv2.CAP_PROP_FOURCC, MJPG)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        opened = cap.isOpened()
        got = False
        shape = None
        if opened:
            for _ in range(8):
                ok, f = cap.read()
                if ok and f is not None and f.size > 0:
                    got, shape = True, f.shape
                    break
        print(f"  OpenCV device={dev}: isOpened={opened} read={'OK ' + str(shape) if got else 'FAIL'}")
        cap.release()


if __name__ == "__main__":
    print("=" * 52)
    print(" 相机诊断工具 (cam_check)")
    print("=" * 52)
    run_native(request=True)
    run_opencv()
    print("[3/3] 诊断完成。把以上完整输出发给我。")
