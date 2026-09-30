"""把歌词原稿逐行对齐到 whisper 的逐字时间戳。
用法: python align_lyrics.py audio.wav lyrics.txt lyrics.json [--lang zh|ja|en]
lyrics.txt：一行一句；[Verse]、(啊——) 之类的段落标记行会被跳过（括号里的吟唱会保留为 hum 行）。
输出 [{i, text, start, end, conf, section}]；conf < 0.5 的行请人工核对。"""
import sys, json, re, difflib
wav, txt, out = sys.argv[1], sys.argv[2], sys.argv[3]
lang = sys.argv[sys.argv.index('--lang') + 1] if '--lang' in sys.argv else None
import mlx_whisper
r = mlx_whisper.transcribe(wav, path_or_hf_repo="mlx-community/whisper-large-v3-mlx", language=lang,
                           word_timestamps=True, condition_on_previous_text=False)
chars, times = [], []
for s in r["segments"]:
    for w in s.get("words", []):
        t = [c for c in w["word"] if not c.isspace() and c not in "，。、,.!?！？…-—"]
        for k, c in enumerate(t):
            d = (w["end"] - w["start"]) / max(len(t), 1)
            chars.append(c.lower()); times.append((w["start"] + k * d, w["start"] + (k + 1) * d))
lines, section = [], ""
for raw in open(txt, encoding="utf-8"):
    s = raw.strip()
    if not s: continue
    m = re.match(r"^\[(.+)\]$", s)
    if m: section = m.group(1); continue
    lines.append({"text": s, "section": section})
L, owner = [], []
for i, ln in enumerate(lines):
    for c in ln["text"]:
        if not c.isspace() and c not in "，。、,.!?！？…-—()（）":
            L.append(c.lower()); owner.append(i)
sm = difflib.SequenceMatcher(None, L, chars, autojunk=False)
m = {}
for a, b, n in sm.get_matching_blocks():
    for k in range(n): m[a + k] = b + k
res = []
for i, ln in enumerate(lines):
    idx = [k for k, o in enumerate(owner) if o == i]
    hit = [m[k] for k in idx if k in m]
    if hit:  # 丢掉离群的匹配（同样的字在别处出现）
        med = sorted(times[h][0] for h in hit)[len(hit) // 2]
        span = max(4., len(idx) * .9)
        hit = [h for h in hit if abs(times[h][0] - med) < span]
    conf = len(hit) / max(len(idx), 1)
    st = times[hit[0]][0] if hit else None
    en = times[hit[-1]][1] if hit else None
    res.append({"i": i, "text": ln["text"], "section": ln["section"], "start": st, "end": en, "conf": round(conf, 2)})
# 没匹配上的行：在前后行之间插值
for i, x in enumerate(res):
    if x["start"] is None:
        p = next((res[j]["end"] for j in range(i - 1, -1, -1) if res[j]["end"] is not None), 0)
        q = next((res[j]["start"] for j in range(i + 1, len(res)) if res[j]["start"] is not None), p + 3)
        x["start"], x["end"] = p + .1, max(p + .5, q - .1)
json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
for x in res:
    flag = "  ⚠️" if x["conf"] < .5 else ""
    print(f'{x["start"]:7.2f}-{x["end"]:7.2f}  {x["conf"]:.2f}  {x["text"]}{flag}')
