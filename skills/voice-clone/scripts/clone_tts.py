#!/usr/bin/env python3
"""用已登记的音色生成配音（CosyVoice3，本地运行）。必须用 cosyvoice 环境的 python：

  PY=~/miniconda3/envs/cosyvoice/bin/python
  $PY clone_tts.py --voice me --text "一句话" --out line.wav
  $PY clone_tts.py --voice me --lines lines.txt --out outdir/          # 每行一句 → 001.wav, 002.wav …
  $PY clone_tts.py --voice me --segments script.json --out build/voice/ # {"segments":[{id,text,voiceText?,instruct?}]}
      → 默认按句生成 seg_<id>_01.wav… 并写 manifest.json（每句的字幕文字与结尾类型，供 build_audio 精确排时）
      → --no-split 则整段生成 seg_<id>.wav
  文案中的 ｜ 是停顿标记（不念、不上字幕），按句模式下会成为句间留白
  常用: --takes 3（同一句多版本挑选）  --only s3,s7  --speed 0.95  --llm base  --device cpu

文本里可用的控制：
  [breath] 呼吸声；拼音纠音，如 “处[ch][ǔ]死”（每个字拼成 [声母][韵母+声调]）
  instruct（segments 模式的字段或 --instruct）：自然语言语气指令，如“请用低沉、缓慢、带一点悬念的语气讲述”
"""
import argparse, json, os, re, sys, time
from pathlib import Path

VC_HOME = Path(os.environ.get("VOICE_CLONE_HOME", Path.home() / "voice-clone"))
COSY, MODEL = VC_HOME / "CosyVoice", VC_HOME / "models/Fun-CosyVoice3-0.5B"
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
sys.path[:0] = [str(COSY), str(COSY / "third_party/Matcha-TTS")]

import torch, torchaudio  # noqa: E402
from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402

SYS = "You are a helpful assistant."
BEAT = "｜"  # 文案里的“戏剧性停顿”标记：不念、不进字幕，只留白


def split_sentences(text):
    """只在句末 。！？ 切句（句末紧跟 ｜ 记为 '。+'，表示在句间停顿上再加长）。
    句中的 ｜ 不切开：整句一次生成才有自然的语调和气息；｜ 保留在返回的句子里，
    由下游（你自己的视频合成脚本）在模型自然停顿处把留白拉长。
    早期版本在句中 ｜ 处切开分别生成，拼起来有“呼吸被掐住”的感觉（EP01 用户反馈），不要再这样做。"""
    out, buf = [], ""
    for ch in text:
        if ch == BEAT and not buf.strip():
            if out:
                out[-1][1] += "+"
            continue
        buf += ch
        if ch in "。！？":
            out.append([buf, ch]); buf = ""
    if buf.strip():
        out.append([buf.rstrip(BEAT), "end"])
    return [(t.strip(), k) for t, k in out]


def beat_positions(sentence):
    """句中 ｜ 在去掉标记后的文字里的位置。"""
    pos, n = [], 0
    for ch in sentence:
        if ch == BEAT:
            pos.append(n)
        else:
            n += 1
    return pos


def load(voice_dir, llm, device):
    tts = AutoModel(model_dir=str(MODEL))
    if llm == "rl":  # RL 版官方评测中文错字率更低（CER 1.21 → 0.81），实际听感也更紧凑
        tts.model.llm.load_state_dict(torch.load(MODEL / "llm.rl.pt", map_location=tts.model.device, weights_only=True), strict=True)
    if device == "mps":
        dev = torch.device("mps")
        tts.model.device = tts.frontend.device = dev
        for m in (tts.model.llm, tts.model.flow):
            m.to(dev)
        # 声码器的 F0 预测必须 float64（MPS 不支持），留在 CPU
        hift_infer = tts.model.hift.inference
        tts.model.hift.inference = lambda speech_feat, finalize=True: hift_infer(speech_feat=speech_feat.float().cpu(), finalize=finalize)
    prompt_wav = voice_dir / "prompt.wav"
    prompt_text = f"{SYS}<|endofprompt|>" + (voice_dir / "prompt.txt").read_text().strip()
    assert tts.add_zero_shot_spk(prompt_text, str(prompt_wav), "spk"), "登记音色失败"
    return tts, str(prompt_wav)


def synth(tts, prompt_wav, text, instruct=None, speed=1.0):
    text = re.sub(r"[《》“”「」]", "", text)  # 书名号/引号会被念出怪腔调
    if instruct:
        gen = tts.inference_instruct2(text, f"{SYS} {instruct}<|endofprompt|>", prompt_wav, stream=False, speed=speed)
    else:
        gen = tts.inference_zero_shot(text, "", "", zero_shot_spk_id="spk", stream=False, speed=speed)
    return torch.cat([j["tts_speech"] for j in gen], dim=1)


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--text"); src.add_argument("--lines"); src.add_argument("--segments")
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice", default="me", help=f"{VC_HOME}/voices/<name>，或直接给目录路径")
    ap.add_argument("--instruct")
    ap.add_argument("--llm", default="rl", choices=["rl", "base"])
    ap.add_argument("--device", default="mps" if torch.backends.mps.is_available() else "cpu", choices=["cpu", "mps"])
    ap.add_argument("--takes", type=int, default=1)
    ap.add_argument("--only", default="")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--no-split", action="store_true", help="segments 模式下整段生成，不按句切分")
    args = ap.parse_args()

    voice_dir = Path(args.voice) if "/" in args.voice else VC_HOME / "voices" / args.voice
    if not (voice_dir / "prompt.wav").exists():
        sys.exit(f"找不到音色 {voice_dir}/prompt.wav —— 先用 prep_sample.py 登记")

    # 组装任务：(输出文件名前缀, 文本, 语气指令)
    manifest = None
    if args.text:
        jobs = [(Path(args.out).stem, args.text.replace(BEAT, ""), args.instruct)]
        out_dir = Path(args.out).parent
    elif args.lines:
        lines = [l.strip() for l in Path(args.lines).read_text().splitlines() if l.strip()]
        jobs = [(f"{i + 1:03d}", l.replace(BEAT, ""), args.instruct) for i, l in enumerate(lines)]
        out_dir = Path(args.out)
    else:
        only = set(filter(None, args.only.split(",")))
        segs = [s for s in json.loads(Path(args.segments).read_text())["segments"]
                if s.get("text") and (not only or s["id"] in only)]
        out_dir = Path(args.out)
        jobs = []
        if args.no_split:
            jobs = [(f"seg_{s['id']}", s.get("voiceText", s["text"]).replace(BEAT, ""), s.get("instruct", args.instruct)) for s in segs]
        else:
            mpath = out_dir / "manifest.json"
            manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
            for s in segs:
                shown, spoken = split_sentences(s["text"]), split_sentences(s.get("voiceText", s["text"]))
                if len(shown) != len(spoken):
                    sys.exit(f"{s['id']}: text 与 voiceText 切句数量不一致（{len(shown)} vs {len(spoken)}），请让两者标点一致")
                manifest[s["id"]] = [{"file": f"seg_{s['id']}_{i + 1:02d}.wav", "text": t.replace(BEAT, ""), "end": k,
                                      **({"beats": beat_positions(t)} if BEAT in t else {})}
                                     for i, (t, k) in enumerate(shown)]
                jobs += [(f"seg_{s['id']}_{i + 1:02d}", t.replace(BEAT, ""), s.get("instruct", args.instruct)) for i, (t, _) in enumerate(spoken)]
    out_dir.mkdir(parents=True, exist_ok=True)
    if manifest is not None:
        # 先写清单：即使中途中断，已生成的句子也能被识别
        (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))

    t0 = time.time()
    tts, prompt_wav = load(voice_dir, args.llm, args.device)
    print(f"模型就绪 {time.time() - t0:.0f}s · 音色 {voice_dir.name} · {args.llm} · {args.device}", flush=True)
    for name, text, instruct in jobs:
        for k in range(args.takes):
            torch.manual_seed(1000 + k)  # 固定种子：同一 take 可复现，不同 take 有差异
            t1 = time.time()
            wav = synth(tts, prompt_wav, text, instruct, args.speed)
            fname = f"{name}.wav" if args.takes == 1 else f"{name}_t{k + 1}.wav"
            torchaudio.save(str(out_dir / fname), wav, tts.sample_rate)
            dur = wav.shape[1] / tts.sample_rate
            # 语速异常（每秒字数过高/过低）往往意味着吞字或卡住，提示人工复听
            chars = len(re.sub(r"\[.*?\]|[^一-鿿A-Za-z0-9]", "", text))
            rate = chars / dur if dur else 0
            flag = "" if 2.8 <= rate <= 6.5 else "  ⚠️ 语速异常，复听"
            print(f"{fname:<22} {dur:5.1f}s  {rate:4.1f}字/s  计算 {time.time() - t1:4.1f}s{flag}", flush=True)


if __name__ == "__main__":
    main()
