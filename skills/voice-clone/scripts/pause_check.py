#!/usr/bin/env python3
"""断句自查：检查每句配音的停顿是不是落在标点上。

听写自查（listen_check）只比字，抓不到断句错：例如“他是个奴隶，主人扭他的腿”被读成
“他是个奴隶主人，扭他的腿”，外国译名的第一个字被单独顿开，字一个不差，意思却变了。
这个脚本按能量找出句中的停顿，按语速把停顿换算成“读到第几个字”，再和台词里的标点位置比：
  - 句中多停：≥0.22 秒的停顿不在任何标点附近（把词拆开，如“一世纪 / 中叶”“可能 / 选的”）
  - 停顿挪位：标点处没停，旁边两三个字以内却停了（如“奴隶，主人” → “奴隶主人，”）
  - 结尾被截断：最后一个字没收住，听起来像“突然断开”（实测一百多句里常有 3–4 句）
  - 连停两次：两个停顿相隔不到两个字，其中一个多半把词拆开了（如“挑好｜弓，”）
逗号处只是没停、旁边也没停的不报：模型常用拖长和语调表示逗号，不一定留出静音。

用法: python3 pause_check.py <配音目录（含 manifest.json）> [--only s3,s7:2]
局限：语速按整句平均估算，位置误差约 1–2 个字。它只抓“真的停了”的错；很多断句错没有静音，
只是语调把两个词连成了一个（“奴隶主人”“可能选的”），这类抓不到，要靠写稿时避开、用户试听。
"""
import json, re, sys
from pathlib import Path
import numpy as np

SPOKEN = re.compile(r'[一-鿿A-Za-z0-9]')
BREAK = set('，、：；,;:')          # 句中应当停顿的标点（句末标点在句与句之间，由排布留白）
FRAME = 0.01


def load(path):
    """读 PCM 或 32 位浮点 wav（配音是 float32，标准库 wave 读不了）。"""
    b = Path(path).read_bytes()
    i, fmt, data = 12, None, None
    while i + 8 <= len(b):
        cid, size = b[i:i + 4], int.from_bytes(b[i + 4:i + 8], 'little')
        if cid == b'fmt ':
            fmt = b[i + 8:i + 8 + size]
        elif cid == b'data':
            data = b[i + 8:i + 8 + size]
        i += 8 + size + (size & 1)
    tag, ch, sr = int.from_bytes(fmt[0:2], 'little'), int.from_bytes(fmt[2:4], 'little'), int.from_bytes(fmt[4:8], 'little')
    bits = int.from_bytes(fmt[14:16], 'little')
    dt = np.float32 if tag == 3 or (tag == 0xFFFE and bits == 32 and fmt[24:26] == b'\x03\x00') else {16: np.int16, 32: np.int32}[bits]
    x = np.frombuffer(data[:len(data) // np.dtype(dt).itemsize * np.dtype(dt).itemsize], dtype=dt).astype(np.float32)
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    return x / (np.abs(x).max() + 1e-9), sr


def pauses(x, sr, min_len=0.09):
    hop = int(sr * FRAME)
    rms = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, 'same')[::hop])
    voiced = rms > max(0.04 * np.percentile(rms, 95), 1e-4)
    # 两段静音之间夹着不到 30ms 的“有声”（呼吸、咔嗒声），并成一段静音
    v = voiced.copy(); k = 0
    while k < len(v):
        if v[k]:
            e = k
            while e < len(v) and v[e]:
                e += 1
            if 0 < k and e < len(v) and (e - k) * FRAME < 0.03:
                v[k:e] = False
            k = e
        else:
            k += 1
    voiced = v
    idx = np.flatnonzero(voiced)
    if len(idx) == 0:
        return [], 0, 0
    a, b = idx[0], idx[-1]
    out, i = [], a
    while i <= b:
        if not voiced[i]:
            j = i
            while j <= b and not voiced[j]:
                j += 1
            if (j - i) * FRAME >= min_len:
                out.append((i, j))
            i = j
        else:
            i += 1
    return out, a, b


def check(path, text):
    clean = text.replace('｜', '')
    chars = [c for c in clean if SPOKEN.match(c)]
    n = len(chars)
    if n < 4:
        return None
    # 每个句中标点之前有几个字
    marks, k = [], 0
    for c in clean:
        if SPOKEN.match(c):
            k += 1
        elif c in BREAK and 0 < k < n:
            marks.append(k)
    x, sr = load(path)
    ps, a, b = pauses(x, sr, 0.04)
    total_voiced = (b - a) - sum(j - i for i, j in ps)
    if total_voiced <= 0:
        return None
    pos, gone = [], 0
    for i, j in ps:
        pos.append((n * ((i - a) - gone) / total_voiced, (j - i) * FRAME))
        gone += j - i
    near = lambda p, tol: any(abs(p - m) <= tol for m in marks)
    # 句中多停：≥0.22s 的停顿不在任何标点附近（爆破音的闭塞只有几十毫秒，不算）；句首句尾一个字以内不算
    extra = [p for p, dur in pos if dur >= 0.22 and 0.8 < p < n - 0.8 and not near(p, 1.8)]
    # 停顿挪位：标点处没停，但旁边三个字以内另有停顿（“奴隶，主人” → “奴隶主人，”）
    moved = [m for m in marks if not any(abs(p - m) <= 1.8 and dur >= 0.06 for p, dur in pos)
             and any(1.8 < abs(p - m) <= 3.5 and dur >= 0.12 and not near(p, 1.8) for p, dur in pos)]
    # 双停：两个 ≥0.2s 的停顿相隔不到两个字——其中一个多半把词拆开了（“挑好｜弓，”）
    big = [p for p, dur in pos if dur >= 0.2 and 0.8 < p < n - 0.8]
    double = [q for p, q in zip(big, big[1:]) if q - p < 2.0]
    # 结尾被截断：文件最后 30ms 的音量还在峰值的 20% 以上，最后一个字没收住（听起来“突然断开”）
    hop = int(sr * FRAME)
    rms = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, 'same')[::hop])
    cut = rms[-3:].mean() / (np.percentile(rms, 95) + 1e-9) > 0.2
    if not extra and not moved and not double and not cut:
        return None
    show = lambda q: ''.join(chars[:q]) + '｜' + ''.join(chars[q:])
    return ([f'停顿挪位（这里该停没停，旁边多停了）：{show(m)}' for m in moved] +
            [f'句中多停（约在）：{show(int(round(p)))}' for p in extra] +
            [f'连停两次（可能拆开了词）：{show(int(round(q)))}' for q in double] +
            (['结尾被截断：最后一个字没收住，听起来像突然断开（用 --takes 换一版）'] if cut else []))


def main():
    d = Path(sys.argv[1])
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else ''
    want = {}
    for it in filter(None, only.split(',')):
        sid, _, k = it.partition(':')
        want.setdefault(sid, set()).add(int(k)) if k else want.setdefault(sid, None)
    man = json.loads((d / 'manifest.json').read_text())
    bad = 0
    for sid, items in man.items():
        if want and sid not in want:
            continue
        for i, it in enumerate(items, 1):
            if want and want.get(sid) and i not in want[sid]:
                continue
            f = d / it['file']
            if not f.exists():
                continue
            r = check(f, it['text'])
            if r:
                bad += 1
                print(f'⚠️  {sid}:{i}  {it["text"]}')
                for line in r:
                    print(f'           {line}')
    print(f'\n断句自查：{bad} 句停顿位置可疑。请把这些句子连同时间点列给用户重点听；位置误差约 1–2 个字。')


if __name__ == '__main__':
    main()
