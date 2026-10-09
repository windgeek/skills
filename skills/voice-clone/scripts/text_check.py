#!/usr/bin/env python3
"""配音前的文本自查：按“韵律短语”检查标点，列出可能读得不自然的地方，交给写稿的人逐条确认。

依据（实测 + 中文 TTS 的通行做法）：
  - 句号、问号会让语调收住，逗号让语势延续。模型按句生成，句号处一定停、语调重起；
    逗号只是“建议”，逗号两边能连成别的词时会被无视（“奴隶，主人” → “奴隶主人”）。
  - 标点要落在韵律短语的边界上，而不只是语法边界。一个连贯的动作中间不要打逗号
    （“他去了北方的一座小城，接着教书” → 读断了；应为“去了北方的一座小城接着教书”）。
  - 单独成句的短句（8 个字以内）容易读得生硬、一顿一顿（“回头看这几个比喻。”），能并进前后句就并进去，
    用冒号或逗号接上；有意的短句（“我也是。”“孩子死了？”）看过保留。
  - 一个意思没说完就用句号断开，会听成“突然断开”（同一句引语中间打了句号）。

用法: python3 text_check.py <script.json>
看过并决定保留的句子，原样写进 script.json 的 "textCheckOk": ["我也是。", ...]，以后不再提示。
它只提示，不改稿；每条都要读出声判断。
"""
import json, re, sys

SPOKEN = re.compile(r'[一-鿿A-Za-z0-9]')
n = lambda s: len(SPOKEN.findall(s))
# 句首常见的虚词、连接词，短一点是正常的（“所以，”“可是，”）
LEAD = ('所以', '可是', '但是', '后来', '其实', '那么', '于是', '而且', '比如', '首先', '然后', '再后来', '相传', '当然', '同样', '这时候')


def check(sid, text):
    out = []
    t = text.replace('｜', '')
    sents = [s for s in re.split(r'(?<=[。！？])', t) if s.strip()]
    for s in sents:
        k = n(s)
        if 0 < k <= 8 and not s.endswith('？'):
            out.append(f'短句单独成句（{k} 字），可能读得生硬，能并进前后句就并：{s}')
        chunks = re.split(r'[，；：、]', s.rstrip('。！？'))
        seps = re.findall(r'[，；：、]', s)
        for i in range(1, len(chunks)):
            c, prev, sep = chunks[i], chunks[i - 1], seps[i - 1]
            if sep == '、' or n(prev) <= 3 and i == 1 and prev.strip() in LEAD:
                continue
            # 逗号后面只有一两个词的尾巴（“……一座小城，接着教书”），且不是并列（前后都短的列举除外）
            if sep == '，' and 0 < n(c) <= 3 and i == len(chunks) - 1 and n(prev) >= 6:
                out.append(f'逗号后只剩很短的尾巴，可能把一个连贯的动作读断：……{prev[-6:]}，{c}')
    return out


def main():
    d = json.load(open(sys.argv[1]))
    ok = d.get('textCheckOk', [])   # 看过、决定保留的句子（写在 script.json 里），不再重复提示
    total, kept = 0, 0
    for s in d['segments']:
        if not s.get('text'):
            continue
        for line in check(s['id'], s['text']):
            if any(o in line for o in ok):
                kept += 1
                continue
            total += 1
            print(f'⚠️  {s["id"]}  {line}')
    print(f'\n文本自查：{total} 处请读出声确认（另有 {kept} 处已看过保留，见 script.json 的 textCheckOk）。另外逐个逗号检查：前后几个字连起来，能不能连成别的词（奴隶，主人 → 奴隶主）。')


if __name__ == '__main__':
    main()
