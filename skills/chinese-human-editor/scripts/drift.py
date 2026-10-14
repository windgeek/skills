#!/usr/bin/env python3
"""核对改稿前后“不可改动”的东西有没有漂移：数字、引号里的话、书名号、链接、英文专名。

用法:
    drift.py 原稿.md 改后.md

列出只在原稿里有（被删或改了）和只在改后稿里有（新出现）的条目。
每一条都要能说清为什么变；说不清就改回去。退出码：有漂移为 1，否则 0。
"""

import re
import sys
from collections import Counter
from pathlib import Path

KINDS = {
    "数字": re.compile(r"\d+(?:[.,]\d+)*\s*(?:美元|人民币|分钟|小时|%|％|[年月日号岁个位次章万亿千百元天周倍]|[A-Za-z]+)?"),
    "引语": re.compile(r"“([^”]{2,80})”|「([^」]{2,80})」"),
    "书名": re.compile(r"《[^》]{1,40}》"),
    "链接": re.compile(r"https?://[^\s)）\]>\"']+"),
    "专名": re.compile(r"\b[A-Z][A-Za-z0-9.+-]*(?:\s+[A-Z0-9][A-Za-z0-9.+-]*)*\b"),
}


def grab(text):
    found = {}
    for k, rx in KINDS.items():
        items = []
        for m in rx.finditer(text):
            v = next((g for g in m.groups() if g), None) if m.groups() else None
            items.append((v or m.group(0)).strip())
        found[k] = Counter(items)
    return found


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    a = grab(Path(sys.argv[1]).read_text(encoding="utf-8"))
    b = grab(Path(sys.argv[2]).read_text(encoding="utf-8"))
    drift = 0
    for k in KINDS:
        gone, new = a[k] - b[k], b[k] - a[k]
        if gone or new:
            print(f"[{k}]")
            for v, c in gone.items():
                print(f"   − {v}" + (f" ×{c}" if c > 1 else ""))
            for v, c in new.items():
                print(f"   + {v}" + (f" ×{c}" if c > 1 else ""))
            drift += sum(gone.values()) + sum(new.values())
    print(f"漂移 {drift} 处。" + ("" if drift else "数字、引语、书名、链接、英文专名前后一致。"))
    sys.exit(1 if drift else 0)


if __name__ == "__main__":
    main()
