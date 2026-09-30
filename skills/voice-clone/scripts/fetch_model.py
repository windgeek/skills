#!/usr/bin/env python3
"""下载 Fun-CosyVoice3-0.5B 到指定目录：ModelScope（国内快）→ 断点续传 + 自动重试 + 大小校验。

用法: python3 fetch_model.py [目标目录，默认 $VOICE_CLONE_HOME/models/Fun-CosyVoice3-0.5B]

网络不稳时会出现 SSL_ERROR_SYSCALL，脚本会自动重试；已完成的文件不会重复下载，可放心重跑。
跳过的文件：TensorRT 用的 onnx 估计器、批处理版分词器（Mac 用不到），约省 2.3 GB。
"""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

REPO = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"
HOME = Path(os.environ.get("VOICE_CLONE_HOME", Path.home() / "voice-clone"))
DEST = Path(sys.argv[1]) if len(sys.argv) > 1 else HOME / "models/Fun-CosyVoice3-0.5B"
SKIP = {"flow.decoder.estimator.fp32.onnx", "speech_tokenizer_v3.batch.onnx", "asset/dingding.png", ".gitattributes", "README.md"}
API = f"https://www.modelscope.cn/api/v1/models/{REPO}/repo/files?Recursive=true"
BASE = f"https://www.modelscope.cn/models/{REPO}/resolve/master/"

files = None
for attempt in range(20):
    try:
        files = [f for f in json.load(urllib.request.urlopen(API, timeout=30))["Data"]["Files"]
                 if f["Type"] == "blob" and f["Path"] not in SKIP]
        break
    except Exception as e:
        print("list retry:", e, flush=True); time.sleep(3)
if not files:
    sys.exit("无法获取文件列表（ModelScope 不可达）。可改用 HuggingFace: hf download " + REPO)

total = sum(f["Size"] for f in files)
print(f"→ {DEST}  共 {len(files)} 个文件 {total / 1e9:.1f} GB", flush=True)
bad = []
for f in sorted(files, key=lambda f: f["Size"]):
    p = DEST / f["Path"]; p.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(60):
        have = p.stat().st_size if p.exists() else 0
        if have == f["Size"]:
            break
        if have > f["Size"]:
            p.unlink(); continue
        subprocess.run(["curl", "-sSL", "--connect-timeout", "20", "-C", "-", "-o", str(p), BASE + f["Path"]])
        time.sleep(1)
    ok = p.exists() and p.stat().st_size == f["Size"]
    if not ok:
        bad.append(f["Path"])
    print(("OK  " if ok else "BAD ") + f"{f['Size'] / 1e6:8.1f} MB  {f['Path']}", flush=True)
print("ALL_DONE" if not bad else f"未完成: {bad}（重跑本脚本即可续传）")
sys.exit(1 if bad else 0)
