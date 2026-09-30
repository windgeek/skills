#!/bin/bash
# 安装 Code Cinema 的运行环境到 ~/.code-cinema（已装过会跳过）
set -e
HOME_DIR="$HOME/.code-cinema"
mkdir -p "$HOME_DIR/node"
for t in ffmpeg node python3; do command -v $t >/dev/null || { echo "缺少 $t，请先安装"; exit 1; }; done
[ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ] || echo "注意：没找到 Google Chrome，可用环境变量 CHROME 指定路径"
if [ ! -x "$HOME_DIR/venv/bin/python" ]; then
  python3 -m venv "$HOME_DIR/venv"
  "$HOME_DIR/venv/bin/pip" install -q librosa soundfile numpy mlx-whisper
fi
if [ ! -d "$HOME_DIR/node/node_modules/puppeteer-core" ]; then
  (cd "$HOME_DIR/node" && [ -f package.json ] || echo '{"private":true}' > package.json; npm install -s puppeteer-core)
fi
echo "PY=$HOME_DIR/venv/bin/python"
echo "ready"
