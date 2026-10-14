#!/usr/bin/env python3
"""Rewrite wrapper("literal.key", args…) calls to generated catalog symbols.

Usage: rewrite_call_sites.py --generated GeneratedStringSymbols_Localizable.swift
                             [--wrapper L10n.string] <repo-dir> [--dry-run]

L10n.string("review.count", n)  ->  L10n.string(.reviewCount(n))
Argument labels come from the generated signatures, so run a build with
STRING_CATALOG_GENERATE_SYMBOLS = YES first. Keys built at run time
("prefix.\\(x)") or not in the catalog are left alone and listed.
Afterwards the wrapper needs an overload taking LocalizedStringResource.
Trailing whitespace on rewritten multi-line calls is trimmed.
"""
import argparse, pathlib, re

ap = argparse.ArgumentParser()
ap.add_argument("repo")
ap.add_argument("--generated", required=True)
ap.add_argument("--wrapper", default="L10n.string")
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()

gen = open(a.generated).read()
sym = {}
for m in re.finditer(r'static (var|func) (\w+)(\(([^)]*)\))?[^\n]*\n\s*LocalizedStringResource\("([^"]+)"', gen):
    kind, name, _, params, key = m.groups()
    labels = None
    if kind == "func":
        labels = []
        for p in params.split(","):
            outer = p.strip().split(":")[0].split()[0]
            labels.append(None if outer == "_" else outer)
    sym[key] = (name, labels)
print(len(sym), "symbols")

def split_args(s):
    out, depth, cur, q, i = [], 0, "", False, 0
    while i < len(s):
        c = s[i]
        if q:
            cur += c
            if c == "\\":
                cur += s[i + 1]; i += 1
            elif c == '"':
                q = False
        elif c == '"':
            q = True; cur += c
        elif c in "([{":
            depth += 1; cur += c
        elif c in ")]}":
            depth -= 1; cur += c
        elif c == "," and depth == 0:
            out.append(cur); cur = ""
        else:
            cur += c
        i += 1
    out.append(cur)
    return out

opener = a.wrapper + '("'
changed, skipped = 0, []
for f in pathlib.Path(a.repo).rglob("*.swift"):
    if any(p in f.parts for p in (".build", "DerivedData", "Pods", "Carthage")):
        continue
    src = f.read_text()
    if opener not in src:
        continue
    out, i = [], 0
    while True:
        j = src.find(opener, i)
        if j < 0:
            out.append(src[i:]); break
        out.append(src[i:j])
        k = j + len(a.wrapper) + 1
        depth, q, e = 1, False, k
        while depth:
            c = src[e]
            if q:
                if c == "\\": e += 1
                elif c == '"': q = False
            elif c == '"': q = True
            elif c == "(": depth += 1
            elif c == ")": depth -= 1
            e += 1
        inner = src[k:e - 1]
        args = split_args(inner)
        m = re.fullmatch(r'\s*"([A-Za-z0-9_.\-]+)"\s*', args[0])
        if not m or m.group(1) not in sym:
            skipped.append(f"{f}: {inner[:70]}"); out.append(src[j:e]); i = e; continue
        name, labels = sym[m.group(1)]
        rest = [x.strip() if "\n" not in x else x.lstrip(" ") for x in args[1:]]
        if labels is None:
            if rest:
                skipped.append(f"{f}: args for argument-less key {m.group(1)}"); out.append(src[j:e]); i = e; continue
            new = f"{a.wrapper}(.{name})"
        else:
            if len(rest) != len(labels):
                skipped.append(f"{f}: {m.group(1)} expects {len(labels)} args"); out.append(src[j:e]); i = e; continue
            parts = [f"{l}: {x}" if l else x for l, x in zip(labels, rest)]
            new = f"{a.wrapper}(.{name}(" + ", ".join(parts) + "))"
        out.append(new); changed += 1; i = e
    text = "".join(out)
    text = re.sub(r"(" + re.escape(a.wrapper) + r"\(\..*?,) +$", r"\1", text, flags=re.M)
    if not a.dry_run:
        f.write_text(text)
print(changed, "call sites rewritten" + (" (dry run)" if a.dry_run else ""))
for s in skipped:
    print("SKIP", s)
