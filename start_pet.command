#!/bin/bash
# 双击启动"情绪感知桌面宠物"（M3）
# 用法：在 Finder 中双击本文件，或在终端执行 ./start_pet.command
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "未找到虚拟环境，请先运行: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    read -r -p "按回车退出..." _
    exit 1
fi

echo "启动情绪感知桌面宠物…（Esc 退出，Ctrl+C 关闭窗口）"
exec .venv/bin/python app.py
