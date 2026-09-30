#!/usr/bin/env python3
"""检查一段声音样本并整理成复刻用的音色。只依赖 ffmpeg，用系统 python3 即可运行。

  python3 prep_sample.py <录音文件> --name me --text "样本里逐字念的内容"
  python3 prep_sample.py <录音文件> --check        # 只体检，不写文件

写入 $VOICE_CLONE_HOME/voices/<name>/：raw.<ext>（原件）、prompt.wav（24kHz 单声道，已清理）、prompt.txt、report.txt
清理步骤：裁掉首尾静音 → 去 75Hz 以下嗡声 → 轻度降噪 → 把 >0.55s 的停顿压短 → 响度标准化到 -18 LUFS。
"""
import argparse, os, re, shutil, subprocess, sys
from pathlib import Path

HOME = Path(os.environ.get("VOICE_CLONE_HOME", Path.home() / "voice-clone"))


def ff(args, capture=True):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", *args], capture_output=True, text=True)
    return r.stderr


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,sample_rate,bit_rate:format=duration",
                          "-of", "default=nw=1", str(path)], capture_output=True, text=True).stdout
    return dict(line.split("=", 1) for line in out.strip().splitlines() if "=" in line)


def rms_db(path, start, end):
    err = ff(["-ss", f"{start}", "-to", f"{end}", "-i", str(path), "-af", "astats=measure_overall=RMS_level:measure_perchannel=0", "-f", "null", "-"])
    m = re.search(r"RMS level dB: (-?[\d.]+|-inf)", err)
    return float(m.group(1)) if m and m.group(1) != "-inf" else -120.0


def analyze(path):
    info = probe(path)
    dur = float(info.get("duration", 0))
    err = ff(["-i", str(path), "-af", "silencedetect=noise=-45dB:d=0.35,astats=measure_overall=Peak_level:measure_perchannel=0,ebur128=framelog=quiet", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    peak = float(re.search(r"Peak level dB: (-?[\d.]+)", err).group(1))
    lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])
    speech_start = ends[0] if starts and starts[0] < 0.05 and ends else 0.0
    # 末段静音可能一直持续到文件尾（没有 end），也可能在尾前一点点被判结束
    trailing = starts and (len(ends) < len(starts) or ends[-1] > dur - 0.3)
    speech_end = starts[-1] if trailing else dur
    pauses = [e - s for s, e in zip(starts, ends) if s > speech_start + 0.1 and e < speech_end - 0.1]
    lead = (0.05, speech_start - 0.1) if speech_start > 0.4 else None
    tail = (speech_end + 0.1, dur - 0.05) if dur - speech_end > 0.4 else None
    noise = min([rms_db(path, *r) for r in (lead, tail) if r] or [None]) if (lead or tail) else None
    return dict(info=info, dur=dur, peak=peak, lufs=lufs, start=speech_start, end=speech_end, pauses=pauses, noise=noise)


def verdict(a):
    lines, speech = [], a["end"] - a["start"]
    br = int(a["info"].get("bit_rate", 0) or 0)
    codec = a["info"].get("codec_name", "?")
    def row(ok, name, value, note):
        lines.append(f"{'✅' if ok is True else '⚠️' if ok is None else '❌'} {name:<6} {value:<28} {note}")
    row(True if 8 <= speech <= 25 else (None if 5 <= speech <= 30 else False), "有效语音", f"{speech:.1f}s ({a['start']:.1f}→{a['end']:.1f})",
        "10–20s 最理想；>30s 要截取最好的一段")
    row(a["peak"] < -1.0, "峰值", f"{a['peak']:.1f} dB", "接近 0 dB 说明破音，需重录" if a["peak"] >= -1 else "无破音")
    row(True if a["lufs"] > -28 else None, "响度", f"{a['lufs']:.1f} LUFS", "偏小（离麦远？）已自动拉平，无大碍" if a["lufs"] <= -28 else "")
    if a["noise"] is not None:
        snr_ok = True if a["noise"] < -55 else (None if a["noise"] < -45 else False)
        row(snr_ok, "底噪", f"{a['noise']:.1f} dB", "安静" if snr_ok is True else "有环境噪声，换更安静的地方更好")
    lossy = codec in ("aac", "mp3", "opus") and br and br < 160000
    row(None if lossy else True, "格式", f"{codec} {br // 1000 if br else '?'}kbps",
        "有损压缩；模型内部只用 24kHz，影响有限。iPhone 语音备忘录可在设置里改“无损”" if lossy else "")
    long = [p for p in a["pauses"] if p > 0.6]
    row(None if len(long) > 3 else True, "停顿", f"{len(a['pauses'])} 处，>0.6s 的 {len(long)} 处",
        "停顿偏长，模型会模仿成一顿一顿；清理时会压短" if len(long) > 3 else "")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--name", default="me")
    ap.add_argument("--text", help="样本逐字文本（和实际念的一致，语气词也要写上）")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    src = Path(args.audio).expanduser().resolve()
    a = analyze(src)
    report = f"样本: {src}\n" + verdict(a)
    print(report)
    if args.check:
        return
    if not args.text:
        sys.exit("\n需要 --text：样本里实际念的文字（让用户对照 iPhone 转写逐字确认）")
    d = HOME / "voices" / args.name
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, d / f"raw{src.suffix.lower()}")
    t0, t1 = max(0, a["start"] - 0.2), min(a["dur"], a["end"] + 0.3)
    ff(["-y", "-ss", f"{t0:.2f}", "-to", f"{t1:.2f}", "-i", str(src), "-af",
        "highpass=f=75,afftdn=nf=-60:nr=10,silenceremove=stop_periods=-1:stop_duration=0.55:stop_threshold=-45dB,"
        "loudnorm=I=-18:TP=-2:LRA=9,aresample=24000", "-ac", "1", str(d / "prompt.wav")])
    (d / "prompt.txt").write_text(args.text.strip() + "\n")
    (d / "report.txt").write_text(report + "\n")
    out = probe(d / "prompt.wav")
    print(f"\n已写入音色 “{args.name}”: {d}/prompt.wav ({float(out['duration']):.1f}s)")


if __name__ == "__main__":
    main()
