#!/bin/bash
# macOS .app 启动器：位于 抽卡师的魔法.app/Contents/MacOS/launcher
# 职责：定位 Resources 目录 → 启动内置 Python 运行后端 → 后端自动打开浏览器

# 定位 .app 的 Resources 目录（本脚本在 Contents/MacOS/ 下）
RES_DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
BACKEND_DIR="$RES_DIR/backend"
PYTHON="$RES_DIR/runtime/bin/python3"

# 用内置运行时启动后端（run_app.pyw 内的防拷贝校验会自动执行）
cd "$BACKEND_DIR"
exec "$PYTHON" run_app.pyw
