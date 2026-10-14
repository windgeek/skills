#!/usr/bin/env python3
"""Audit String Catalogs: coverage, placeholders, plural forms, review state.

Usage: audit_xcstrings.py [--required-locales en,de,…] [--fail-on-review] CATALOG…

Fails (exit 1) on: invalid JSON, a required locale missing or empty for a
translatable key, placeholders that differ from the source language, or an
entry in state "new". Entries in "needs_review" are counted, and fail only
with --fail-on-review (use once the review pass is supposed to be finished).
Does not judge translation quality.
"""
import argparse, json, re, sys
from collections import Counter

SPEC = re.compile(r"%(?:(\d+)\$)?(lld|ld|d|@|f|\.\d+f|%|#@\w+@)")

def specs(s):
    out, n = [], 0
    for m in SPEC.finditer(s):
        pos, kind = m.groups()
        if kind == "%":
            out.append(("%", 0)); continue
        n += 1
        kind = "#" if kind.startswith("#") else ("d" if kind in ("lld", "ld", "d") else kind)
        out.append((kind, int(pos) if pos else n))
    return sorted(out)

def units(loc, path=""):
    if "stringUnit" in loc:
        yield path or "value", loc["stringUnit"]
    for name, sub in loc.get("substitutions", {}).items():
        yield from units(sub, f"{path}sub:{name}/")
    for axis, forms in loc.get("variations", {}).items():
        for f, node in forms.items():
            yield from units(node, f"{path}{axis}:{f}/")

def ref_for(src, path):
    d = dict(units(src))
    if path in d:
        return d[path]["value"]
    # plural/device form missing in source: compare against its `other`
    for p, u in d.items():
        if p.endswith("other/") or p == "value":
            return u["value"]
    return None

ap = argparse.ArgumentParser()
ap.add_argument("--required-locales", default="")
ap.add_argument("--fail-on-review", action="store_true")
ap.add_argument("catalogs", nargs="+")
a = ap.parse_args()

failed = False
for path in a.catalogs:
    try:
        cat = json.load(open(path))
    except Exception as e:
        print(f"{path}: invalid JSON: {e}"); failed = True; continue
    source = cat.get("sourceLanguage", "en")
    strings = cat.get("strings", {})
    locales = set(filter(None, a.required_locales.split(","))) or \
        {l for e in strings.values() for l in e.get("localizations", {})}
    problems, review = [], Counter()
    for key, e in strings.items():
        if e.get("shouldTranslate") is False:
            continue
        locs = e.get("localizations", {})
        src = locs.get(source)
        for lang in sorted(locales):
            loc = locs.get(lang)
            if loc is None:
                if lang != source or src is None:
                    problems.append(f"{lang}: missing {key}")
                continue
            for p, u in units(loc):
                if not u.get("value"):
                    problems.append(f"{lang}: empty {key} [{p}]")
                if u.get("state") == "new":
                    problems.append(f"{lang}: state new {key} [{p}]")
                if u.get("state") == "needs_review":
                    review[lang] += 1
                if src and lang != source:
                    r = ref_for(src, p)
                    if r is not None and "%arg" not in u.get("value", "") and specs(u.get("value", "")) != specs(r):
                        problems.append(f"{lang}: placeholders differ {key} [{p}]: {u.get('value')!r} vs {r!r}")
    print(f"{path}: {len(strings)} keys · locales {', '.join(sorted(locales))}")
    for p in problems[:60]:
        print("  " + p)
    if len(problems) > 60:
        print(f"  … and {len(problems) - 60} more")
    if review:
        print("  needs_review units: " + ", ".join(f"{l} {n}" for l, n in sorted(review.items())))
    if problems or (a.fail_on_review and review):
        failed = True
print("FAILED" if failed else "OK")
sys.exit(1 if failed else 0)
