#!/usr/bin/env bash
# 在 macOS (Apple 芯片) 上安装 CosyVoice3 本地声音复刻环境。可重复运行（已完成的步骤会跳过）。
# 会下载：GitHub 代码(小) + ModelScope 模型(~7.4 GB) + PyPI 依赖(~2-3 GB)。运行前先征得用户同意。
#
#   bash setup.sh            # 安装到 $VOICE_CLONE_HOME（默认 ~/voice-clone），conda 环境名 cosyvoice
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VC_HOME="${VOICE_CLONE_HOME:-$HOME/voice-clone}"
CONDA="${CONDA_EXE:-$HOME/miniconda3/bin/conda}"
ENV_NAME="${VOICE_CLONE_ENV:-cosyvoice}"
PY="$("$CONDA" info --base)/envs/$ENV_NAME/bin/python"
mkdir -p "$VC_HOME/voices" "$VC_HOME/models"

echo "== 1/5 代码"
[ -d "$VC_HOME/CosyVoice/.git" ] || git clone --recursive --depth 1 https://github.com/FunAudioLLM/CosyVoice.git "$VC_HOME/CosyVoice"

echo "== 2/5 Python 3.10 环境 ($ENV_NAME)"
# 用 conda-forge：Anaconda 默认频道要求接受服务条款，这得由用户本人决定，不要替他接受
[ -x "$PY" ] || "$CONDA" create -y -q -n "$ENV_NAME" --override-channels -c conda-forge python=3.10
"$PY" -m pip --version >/dev/null 2>&1 || "$PY" -m ensurepip -q
"$PY" -m pip install -q -U pip

echo "== 3/5 依赖"
# openai-whisper 旧版的 setup.py 依赖 pkg_resources，新版 setuptools 已删除 → 锁旧版并关闭构建隔离
"$PY" -m pip install -q "setuptools<70" wheel cython
"$PY" -c "import whisper" 2>/dev/null || "$PY" -m pip install -q --no-build-isolation openai-whisper==20231117
# 官方 requirements 面向 Linux+CUDA：去掉 GPU/TensorRT/网页服务相关包（gdown、pyworld 要保留，推理时会被间接 import）
grep -v -E '^--extra-index-url|deepspeed|tensorrt|onnxruntime-gpu|gradio|fastapi|uvicorn|grpcio|tensorboard' \
  "$VC_HOME/CosyVoice/requirements.txt" > "$VC_HOME/requirements-mac.txt"
"$PY" -m pip install -q --retries 10 --timeout 60 -r "$VC_HOME/requirements-mac.txt"
"$PY" -m pip install -q "setuptools<70"   # 上一步可能把 setuptools 升级掉，CosyVoice 运行时需要 pkg_resources

echo "== 4/5 模型"
python3 "$HERE/fetch_model.py" "$VC_HOME/models/Fun-CosyVoice3-0.5B"

echo "== 5/5 自检"
"$PY" -c "import torch, pkg_resources, gdown, pyworld, whisper, onnxruntime; print('环境 OK · torch', torch.__version__, '· MPS', torch.backends.mps.is_available())"
echo "安装完成：$VC_HOME"
