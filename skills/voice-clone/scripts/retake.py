#!/usr/bin/env python3
"""给断句自查报出来的句子另出几个版本，自动挑一版换进去。

用法:
  python3 retake.py --segments script.json --out build/voice --only s4:4,s21:6 [--takes 4] [--voice me]
做法：调用 clone_tts.py 的 --takes 生成 t1..tN 到 <out>/../takes/（t1 与现有版本相同，种子固定），
每版跑一遍断句自查（句中多停、停顿挪位、连停两次、结尾截断），在没有问题的版本里选语速最接近
全片中位数的那一版，复制成 seg_<id>_<k>.wav，原文件备份为 .bak.wav。都有问题时不替换，列出来交给用户试听。
挑出来的版本只是“检查没报问题”，自然不自然仍以用户试听为准。换完后重新拼接音轨。

需要的环境：CosyVoice 所在的 Python（用 $VOICE_CLONE_PY 指定，缺省用当前解释器），
以及 $VOICE_CLONE_HOME（缺省 ~/voice-clone，clone_tts.py 用它找模型和音色）。
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pause_check as pc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--segments', required=True, help='clone_tts 用的 segments JSON')
    ap.add_argument('--out', required=True, help='配音目录（含 manifest.json）')
    ap.add_argument('--only', required=True, help='要重出的句子，如 s4:4,s21:6')
    ap.add_argument('--takes', type=int, default=4)
    ap.add_argument('--voice', default='me')
    a = ap.parse_args()
    voice = Path(a.out); takes = voice.parent / 'takes'
    py = os.environ.get('VOICE_CLONE_PY', sys.executable)
    subprocess.run([py, str(HERE / 'clone_tts.py'), '--voice', a.voice, '--segments', a.segments,
                    '--out', str(takes), '--only', a.only, '--takes', str(a.takes)], check=True)
    man = json.loads((voice / 'manifest.json').read_text())
    rates = []
    for items in man.values():
        for it in items:
            f = voice / it['file']
            if f.exists():
                x, sr = pc.load(f); rates.append(len(pc.SPOKEN.findall(it['text'])) / (len(x) / sr))
    mid = float(np.median(rates))
    for item in a.only.split(','):
        sid, _, k = item.partition(':'); k = int(k)
        text = man[sid][k - 1]['text']
        ok = []
        for t in range(1, a.takes + 1):
            f = takes / f'seg_{sid}_{k:02d}_t{t}.wav'
            issues = pc.check(f, text)
            x, sr = pc.load(f); rate = len(pc.SPOKEN.findall(text)) / (len(x) / sr)
            print(f'{sid}:{k} t{t}  {rate:.1f}字/s  ' + ('；'.join(issues) if issues else '无问题'))
            if not issues:
                ok.append((abs(rate - mid), t, f))
        if ok:
            _, t, f = min(ok)
            dst = voice / f'seg_{sid}_{k:02d}.wav'
            shutil.copy(dst, dst.with_suffix('.bak.wav')); shutil.copy(f, dst)
            print(f'  → {sid}:{k} 换成 t{t}')
        else:
            print(f'  → {sid}:{k} {a.takes} 个版本都有问题，保留原版，请用户试听或改写这句')


if __name__ == '__main__':
    main()
