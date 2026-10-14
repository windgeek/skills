#!/usr/bin/env python3
"""Merge <src>/*.lproj/<Table>.strings into <src>/<Table>.xcstrings.

Usage: migrate_strings.py <app-source-dir> [--table Localizable] [--source en]

- Every language found as <lang>.lproj/<Table>.strings is included.
- Order and comments come from the source-language file: a block comment
  describes the contiguous entries under it, up to the next blank line.
- %d / %ld / %i become %lld (Swift Int; also what generated symbols expect).
- Every key gets extractionState "manual" so Xcode never marks it stale.
- Prints English strings that look like count + noun: add plural variations
  to those by hand (see references/workflow.md).
Old .strings files are left in place; delete them once the build is green.
"""
import argparse, json, pathlib, re, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("--table", default="Localizable")
ap.add_argument("--source", default="en")
a = ap.parse_args()
src = pathlib.Path(a.src)

files = sorted(src.glob(f"*.lproj/{a.table}.strings"))
langs = [f.parent.name[:-len(".lproj")] for f in files if f.parent.name != "Base.lproj"]
if a.source not in langs:
    sys.exit(f"no {a.source}.lproj/{a.table}.strings under {src}")

def load(lang):
    p = src / f"{lang}.lproj/{a.table}.strings"
    out = subprocess.run(["plutil", "-convert", "json", "-o", "-", str(p)],
                         check=True, capture_output=True).stdout
    return json.loads(out), p.read_text(encoding="utf-8")

values = {l: load(l)[0] for l in langs}
text = load(a.source)[1]

order, comments, pending = [], {}, None
lines, i = text.split("\n"), 0
while i < len(lines):
    s = lines[i].strip()
    if s.startswith("/*"):
        buf = [s]
        while "*/" not in buf[-1]:
            i += 1
            buf.append(lines[i].strip())
        pending = re.sub(r"\s+", " ", re.sub(r"^/\*\s*|\s*\*/$", "", " ".join(buf))).strip()
    elif s.startswith("//"):
        pending = s[2:].strip()
    elif s == "":
        pending = None
    else:
        m = re.match(r'^"((?:[^"\\]|\\.)*)"\s*=', s)
        if m:
            key = json.loads(f'"{m.group(1)}"')
            order.append(key)
            if pending:
                comments[key] = pending
    i += 1

missing_order = set(values[a.source]) - set(order)
order += sorted(missing_order)  # entries the line parser could not see

def canon(v):
    return re.sub(r"%(\d+\$)?(?:l|ll)?[di]", lambda m: f"%{m.group(1) or ''}lld", v)

strings = {}
for key in order:
    e = {}
    if key in comments:
        e["comment"] = comments[key]
    e["extractionState"] = "manual"
    e["localizations"] = {l: {"stringUnit": {"state": "translated", "value": canon(values[l][key])}}
                          for l in langs if key in values[l]}
    strings[key] = e
    for l in langs:
        if key not in values[l]:
            print(f"warning: {key} missing in {l}")

out = src / f"{a.table}.xcstrings"
cat = {"sourceLanguage": a.source, "strings": dict(sorted(strings.items())), "version": "1.1"}
out.write_text(json.dumps(cat, ensure_ascii=False, indent=2, separators=(",", " : ")) + "\n", encoding="utf-8")
print(f"wrote {out}: {len(strings)} keys, {len(comments)} with comments, languages {', '.join(langs)}")

cands = [(k, v) for k, v in values[a.source].items()
         if re.search(r"%(\d+\$)?(l|ll)?[di](\s+[\w-]+){0,2}?\s+[\w-]+s\b|\b\w+s:?\s*%(\d+\$)?(l|ll)?[di]", v)]
if cands:
    print("\nPlural candidates (review; add variations.plural or substitutions):")
    for k, v in cands:
        print(f"  {k}: {v}")
