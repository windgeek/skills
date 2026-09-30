#!/bin/bash
# bash new_project.sh <项目目录> [音频文件]
set -e
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$1"; AUDIO="$2"
[ -n "$DIR" ] || { echo "用法: new_project.sh <项目目录> [音频文件]"; exit 1; }
mkdir -p "$DIR/build"
for f in engine.js film.js index.html render.mjs package.json sheet.sh; do [ -e "$DIR/$f" ] || cp "$SKILL/engine/$f" "$DIR/"; done
[ -e "$DIR/node_modules" ] || ln -s "$HOME/.code-cinema/node/node_modules" "$DIR/node_modules"
if [ -n "$AUDIO" ]; then
  ffmpeg -y -loglevel error -nostdin -i "$AUDIO" -ar 44100 -ac 2 "$DIR/audio.wav"
  "$HOME/.code-cinema/venv/bin/python" "$SKILL/scripts/analyze_audio.py" "$DIR/audio.wav" "$DIR/audio.js"
else
  echo 'window.AUDIO={beats:[]};' > "$DIR/audio.js"
fi
echo "项目: $DIR"
