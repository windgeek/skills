#!/usr/bin/env python3
"""中文稿件的 AI 腔扫描：按 SKILL.md 的病症清单列出线索，叙述和对话分开。

用法:
    scan.py 稿.md [--genre article|fiction|webnovel]

只读，不改稿。线索需要人判断：对话里的句式可能正是人物口吻，
网文的章末单句是钩子不是表演。退出码恒为 0。
"""

import argparse
import re
import sys
from pathlib import Path

# 编号与 SKILL.md 病症清单一致
RULES = [
    ("1 假转折", r"不是[^。！？\n“”]{1,24}?[，,—]\s*(?:而是|是|我是|它是|她是|他是)|不是[^。\n]{1,25}而是"
                r"|这不(?:只)?是.{1,20}[。，,]\s*(?:这|更)是|不只是.{0,20}更是|真正的?.{0,16}不是"
                r"|与其说|那一刻我明白|换句话说|其实|意味着"),
    ("1 后来我才（全文≤1）", r"后来我才"),
    ("3 情绪词直陈", r"痛苦|愤怒|尴尬|绝望|悲伤|崩溃了|心如刀割|五味杂陈|百感交集"),
    ("6 抽象词", r"本质|底层逻辑|维度|颗粒度|叙事权|时代浪潮|价值闭环|认知升级|赋能|抓手|闭环|打通|拉通|对齐"),
    ("7 流程套话", r"首先|其次|值得注意的是|不得不说|众所周知|让我们一起|一方面.{0,30}另一方面"),
    ("7 无来源热度", r"刷屏了|圈内炸了|所有人都在讨论|全网都在"),
    ("11 万能升华", r"我们每个人|时代已经改变|未来值得期待|选择适合自己的|工具越强.{0,12}人越重要|这个时代|背后是一场"),
    ("12 套路词", r"最狠的不是|所有人都低估|变天了|要完了|看完沉默|发现一个秘密|终于有人说清楚|正在偷偷"
                 r"|的尽头是|杀疯了|封神|炸裂|细思极恐"),
]
APHORISM_START = re.compile(r"^\s*(?:一个人(?!的时候)|人(?:给自己|在|是|被|会|往往|总是)|所有的事|任何一个人)")
APHORISM_ANY = re.compile(r"往往|从来都|永远都|总是会|才是真正的")
QUOTE = re.compile(r"[\"“”「」『』]")
SENT = re.compile(r"[^。！？\n]+[。！？]")


def is_dialogue(line):
    return bool(QUOTE.search(line))


def body_lines(text):
    """跳过代码块、链接行、表格分隔行；保留行号。"""
    in_code = False
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("```") or s.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code or not s or s.startswith(("http://", "https://", "|---", "<!--")):
            continue
        yield n, line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--genre", choices=["article", "fiction", "webnovel"], default="article")
    a = ap.parse_args()
    text = Path(a.file).expanduser().read_text(encoding="utf-8")
    lines = list(body_lines(text))
    total = 0

    print(f"扫描：{a.file}（体裁 {a.genre}）")

    # 标题
    title = next((l[2:].strip() for _, l in lines if l.startswith("# ")), None)
    if title:
        hits = [m.group(0) for _, rx in RULES for m in re.finditer(rx, title)]
        if hits or re.search(r"[:：].+[:：]", title):
            print(f"\n[12 标题] {title}\n   线索：{'、'.join(hits) or '冒号重复结论？'}")
            total += 1

    # 句式与词
    for label, rx in RULES:
        if label.startswith("3") and a.genre == "article":
            label += "（评论文章酌情）"
        nar, dia = [], []
        for n, line in lines:
            if line.startswith("#"):
                continue
            for m in re.finditer(rx, line):
                (dia if is_dialogue(line) else nar).append((n, m.group(0)))
        if nar or dia:
            total += len(nar) + len(dia)
            print(f"\n[{label}] 叙述 {len(nar)} 处 · 对话 {len(dia)} 处")
            for n, w in nar[:10]:
                print(f"   {n}: {w}")
            if dia:
                print(f"   对话（判断是否人物口吻）：" + "，".join(f"{n}:{w}" for n, w in dia[:8]))

    # 4 假金句：按 ## 分节，每节超过一句才列
    sections, cur = [], ("（开头）", [])
    for n, line in lines:
        if line.startswith("## "):
            sections.append(cur)
            cur = (line[3:].strip(), [])
        elif not line.startswith("#") and not is_dialogue(line):
            cur[1].append((n, line))
    sections.append(cur)
    printed = False
    for name, sec in sections:
        hits = [(n, x.strip()) for n, l in sec for x in SENT.findall(l)
                if APHORISM_START.search(x) or APHORISM_ANY.search(x)]
        if len(hits) > 1:
            if not printed:
                print("\n[4 假金句候选] 每节最多留一句，且要别扭、不对仗")
                printed = True
            total += len(hits)
            print(f"   {name[:20]}（{len(hits)} 句）")
            for n, h in hits[:5]:
                print(f"     {n}: {h[:48]}")

    # 5 排比：同一段里三个以上同字开头的分句
    for n, line in lines:
        if line.startswith("#"):
            continue
        clauses = [c.strip() for c in re.split(r"[，。；！？、]", line) if len(c.strip()) >= 4]
        for i in range(len(clauses) - 2):
            heads = {c[:2] for c in clauses[i:i + 3]}
            if len(heads) == 1:
                total += 1
                print(f"\n[5 排比] {n}: {'／'.join(clauses[i:i + 3])[:60]}")
                break

    # 8 短句表演：连续三段以上的短叙述段
    run, runs = [], []
    for n, line in lines + [(10 ** 9, "#")]:
        s = line.strip()
        short = (s and not s.startswith(("#", ">", "-", "*", "|", "!")) and not re.match(r"^\d+[.)]", s)
                 and len(s) < 26 and not is_dialogue(s))
        if short:
            run.append((n, s))
        else:
            if len(run) >= 3:
                runs.append(run)
            run = []
    if runs:
        note = "（网文的章末钩子、反转处可以保留）" if a.genre == "webnovel" else ""
        print(f"\n[8 短句表演] 连续短叙述段 {len(runs)} 组{note}")
        for r in runs[:8]:
            print(f"   {r[0][0]}: " + " / ".join(x for _, x in r)[:80])
        total += len(runs)

    print(f"\n共 {total} 条线索。逐条回到上下文判断；叙述里的假转折要清零。")


if __name__ == "__main__":
    main()
