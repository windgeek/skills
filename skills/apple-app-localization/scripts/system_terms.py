#!/usr/bin/env python3
"""Look up how macOS itself translates UI terms, from the OS's own resources.

Reads every `.loctable` under /System, the Finder's `.lproj/*.strings` and the
system folder-name table, finds
entries whose English value equals a term, and prints what each language shows
on screen. Several variants can exist (a newer and an older string, or the word
used in another sense), so they are listed by how many tables use them. Prefer
the Finder's and System Settings' own string when they disagree.

Usage: system_terms.py "Quick Look" "Open With" "Spotlight" [--langs zh_CN,zh_TW,ja,ko,de,fr,es,pt_BR]
       system_terms.py Memory --app "Activity Monitor"

A common English word can mean different things in different apps ("Memory"
is a tab in Activity Monitor and a feature in Photos). When the term names
something in one app, pass --app to read only that app's own tables.
"""
import argparse, glob, json, plistlib, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("terms", nargs="+")
ap.add_argument("--langs", default="zh_CN,zh_TW,ja,ko,de,fr,es,pt_BR")
ap.add_argument("--variants", type=int, default=3)
ap.add_argument("--app", help="only tables inside this app's bundle, e.g. \"Activity Monitor\"")
a = ap.parse_args()
langs = a.langs.split(",")
terms = set(a.terms)
found = {}

def note(term, values, source):
    found.setdefault(term, {}).setdefault(tuple(values), []).append(source)

tables = glob.glob("/System/Library/**/*.loctable", recursive=True) \
       + glob.glob("/System/Applications/**/*.loctable", recursive=True)
if a.app:
    tables = [t for t in tables if f"/{a.app}.app/" in t]
for path in tables:
    try:
        data = plistlib.load(open(path, "rb"))
    except Exception:
        continue
    for key, value in (data.get("en") or {}).items():
        if isinstance(value, str) and value.rstrip("…").strip() in terms:
            note(value.rstrip("…").strip(), [data.get(l, {}).get(key) for l in langs], path)

# The Finder keeps its menus in classic .strings files.
finder = "/System/Library/CoreServices/Finder.app/Contents/Resources"
def strings(path):
    out = subprocess.run(["plutil", "-convert", "json", "-o", "-", path], capture_output=True).stdout
    return json.loads(out) if out else {}
for name in (() if a.app else ("LocalizableMerged.strings", "Localizable.strings")):
    en = strings(f"{finder}/en.lproj/{name}")
    per = {l: strings(f"{finder}/{l}.lproj/{name}") for l in langs}
    for key, value in en.items():
        if isinstance(value, str) and value.rstrip("…").strip() in terms:
            note(value.rstrip("…").strip(), [per[l].get(key) for l in langs], "Finder " + name)

# Folder names (Applications, Utilities, Library…) have their own table, and
# it is the authority for a folder: Finder's sidebar may use another word
# (German shows the folder as "Programme" but a sidebar label as "Apps").
folders = "/System/Library/CoreServices/SystemFolderLocalizations"
en = {} if a.app else strings(f"{folders}/en.lproj/SystemFolderLocalizations.strings")
per = {l: strings(f"{folders}/{l}.lproj/SystemFolderLocalizations.strings") for l in langs}
for key, value in en.items():
    if isinstance(value, str) and value in terms:
        note(value, [per[l].get(key) for l in langs], "Folder SystemFolderLocalizations")

def rank(kv):
    sources = kv[1]
    return (not any(s.startswith("Folder") for s in sources),
            not any(s.startswith("Finder") for s in sources), -len(sources))

for term in a.terms:
    print(f"## {term}")
    # A folder's own name first, then the Finder's string: that is what users
    # see next to the app.
    variants = sorted(found.get(term, {}).items(), key=rank)
    if not variants:
        print("  not found — search a shorter or different English string")
    for values, sources in variants[: a.variants]:
        tag = " · folder name" if any(s.startswith("Folder") for s in sources) \
            else " · Finder" if any(s.startswith("Finder") for s in sources) else ""
        print(f"  {len(sources)} table(s){tag}:")
        for l, v in zip(langs, values):
            print(f"    {l}: {v}")
