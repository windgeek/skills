#!/usr/bin/env python3
"""配音“听写”自查：用 macOS 自带的离线语音识别（SpeechAnalyzer，macOS 26+）把每句配音转成文字，
按拼音和台词逐句比对，列出对不上的地方，交给用户重点试听。

用法: python3 listen_check.py <配音目录（含 manifest.json）> [--only s3,s7:2] [--all]
  默认只列出有出入的句子；--all 列出全部识别结果。

局限（告诉用户）：识别器会按上下文“纠正”，所以同音或近音的读错（如“事”读成 chì）不一定能抓到；
它主要抓漏字、多字、整词读错、读成别的词。它是辅助，不能代替试听。
"""
import json, os, re, subprocess, sys, difflib
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = Path(os.environ.get('VOICE_CLONE_HOME', Path.home() / 'voice-clone')) / 'bin' / 'asr'
PUNCT = re.compile(r'[\s，。！？；：、“”‘’《》（）「」…—·,.!?;:"\'()\[\]｜|-]')


def ensure_bin():
    src = HERE / 'asr.swift'
    if not BIN.exists() or BIN.stat().st_mtime < src.stat().st_mtime:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['swiftc', '-O', '-o', str(BIN), str(src)], check=True)


DIG = '零一二三四五六七八九'


def cardinal(n):
    if n == 0:
        return '零'
    out, units, zero = '', [(10000, '万'), (1000, '千'), (100, '百'), (10, '十'), (1, '')], False
    for u, name in units:
        d, n = divmod(n, u)
        if d:
            if zero:
                out += '零'
            out += (cardinal(d) if u == 10000 else DIG[d]) + name
            zero = False
        elif out:
            zero = True
    return out[1:] if out.startswith('一十') else out


def digits_to_cn(s):
    """识别器把数字写成阿拉伯数字；年份按位读（1974 年 → 一九七四年），其余按数值读（2300 → 二千三百）。"""
    def rep(m):
        num, after = m.group(0), s[m.end():m.end() + 1]
        if len(num) in (3, 4) and after == '年':
            return ''.join(DIG[int(c)] for c in num)
        return cardinal(int(num))
    return re.sub(r'\d+', rep, s)


def py(s):
    from pypinyin import lazy_pinyin, Style
    s = PUNCT.sub('', digits_to_cn(s))
    p = lazy_pinyin(s, style=Style.TONE3, neutral_tone_with_five=True)
    p = ['er4' if x == 'liang3' else x for x in p]  # “两千”与“二千”不算差异
    p = ['de5' if c in '的地得' else x for c, x in zip(s, p)]  # 助词“的/地/得”识别器常互换
    return s, p


def main():
    args = sys.argv[1:]
    vdir = Path(args[0]); show_all = '--all' in args
    only = None
    if '--only' in args:
        only = set(args[args.index('--only') + 1].split(','))
    ensure_bin()
    man = json.loads((vdir / 'manifest.json').read_text())
    items = []
    for seg, sents in man.items():
        for i, s in enumerate(sents, 1):
            if only and seg not in only and f'{seg}:{i}' not in only:
                continue
            items.append((f'{seg}:{i}', vdir / s['file'], s['text']))
    out = subprocess.run([str(BIN)] + [str(f) for _, f, _ in items], capture_output=True, text=True, check=True).stdout
    heard = dict(line.split('\t', 1) for line in out.splitlines() if '\t' in line)
    bad, tone_notes = 0, []
    for key, f, text in items:
        h = heard.get(str(f), '')
        t_chars, t_py = py(text)
        h_chars, h_py = py(h)
        strip = lambda p: [re.sub(r'\d', '', x) for x in p]
        sm = difflib.SequenceMatcher(a=strip(t_py), b=strip(h_py), autojunk=False)
        diffs = [(t_chars[i1:i2], h_chars[j1:j2]) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != 'equal']
        tones = []
        if not diffs:  # 字音一致时，再看声调
            tones = [(t_chars[i], h_chars[i]) for i in range(min(len(t_py), len(h_py))) if t_py[i] != h_py[i]]
        if diffs:
            bad += 1
            print(f'⚠️  {key:7} 台词：{text}')
            print(f'{"":11}听到：{h}')
            print(f'{"":11}差异：' + '；'.join(f'“{a or "（无）"}” → “{b or "（无）"}”' for a, b in diffs))
        elif tones:
            tone_notes.append(f'{key}：' + '、'.join(f'“{a}”听成“{b}”' for a, b in tones))
        elif show_all:
            print(f'    {key:7} {h}')
    if tone_notes:
        print('\n只差声调（多半是识别器猜字，偶尔是真的读错了声调，顺带听一下）：')
        for n in tone_notes:
            print('  ' + n)
    print(f'\n共 {len(items)} 句，{bad} 句字音对不上，{len(tone_notes)} 句只差声调。请重点试听 ⚠️ 的句子；识别器本身也会听错，以试听为准。')


if __name__ == '__main__':
    main()
