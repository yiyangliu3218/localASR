#!/bin/bash
# 启动本地语音转文字菜单栏应用
cd "$(dirname "$0")"
source .venv/bin/activate
python3 app.py
