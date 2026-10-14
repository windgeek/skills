#!/usr/bin/env python3
"""Print one language side by side with the source (and a reference language),
grouped by comment, for the Phase 2b review pass.

Usage: dump_for_review.py --catalog Localizable.xcstrings --lang de [--ref zh-Hans] [--only-pending]
"""
import argparse, json

ap = argparse.ArgumentParser()
ap.add_argument("--catalog", required=True)
ap.add_argument("--lang", required=True)
ap.add_argument("--ref")
ap.add_argument("--only-pending", action="store_true")
a = ap.parse_args()
cat = json.load(open(a.catalog)); src = cat.get("sourceLanguage", "en")

def show(loc):
    if loc is None:
        return "∅", False
    pending = False
    def walk(n, pre=""):
        nonlocal pending
        out = []
        if "stringUnit" in n:
            pending |= n["stringUnit"].get("state") == "needs_review"
            out.append(pre + n["stringUnit"]["value"])
        for name, sub in n.get("substitutions", {}).items():
            out += walk(sub, f"{pre}[{name}] ")
        for axis, forms in n.get("variations", {}).items():
            for f, node in forms.items():
                out += walk(node, f"{pre}{f}: ")
        return out
    return " | ".join(walk(loc)), pending

last = None
for key, e in cat["strings"].items():
    if e.get("shouldTranslate") is False:
        continue
    locs = e.get("localizations", {})
    text, pending = show(locs.get(a.lang))
    if a.only_pending and not pending:
        continue
    if e.get("comment") != last:
        last = e.get("comment")
        if last:
            print(f"\n## {last}")
    print(key)
    print(f"  {src}: {show(locs.get(src))[0]}")
    if a.ref:
        print(f"  {a.ref}: {show(locs.get(a.ref))[0]}")
    print(f"  {a.lang}: {text}")
