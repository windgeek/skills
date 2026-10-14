#!/usr/bin/env python3
"""Merge per-language translation files into a String Catalog, validated.

Usage: merge_translations.py --catalog Path/Localizable.xcstrings --tr DIR
                             [--copy key1,key2] [--state needs_review] LANG…

DIR/<LANG>.json maps key -> value:
  "plain.key":   "text with %@ and %lld"
  "plural.key":  {"one": "…%lld…", "other": "…%lld…"}      # CLDR categories
  "subst.key":   {"template": "%#@items@ · %2$@", "one": "%arg x", "other": "%arg xs"}
Keys in --copy take the source-language value (brand names, tool names).

Nothing is written unless every key is present, placeholders match the source
by kind and position, and plural forms match the language's CLDR categories.
`many` is filled from `other` where CLDR has it but integers rarely hit it.
French no-break spaces are applied automatically (write plain spaces).
Re-running for a language replaces its entries; other languages are untouched.
"""
import argparse, json, pathlib, re, sys

# Integer-relevant CLDR cardinal categories (Xcode offers these).
FORMS = {
    "en": ["one", "other"], "de": ["one", "other"], "nl": ["one", "other"],
    "sv": ["one", "other"], "da": ["one", "other"], "nb": ["one", "other"],
    "fi": ["one", "other"], "el": ["one", "other"], "tr": ["one", "other"],
    "hu": ["one", "other"], "hi": ["one", "other"],
    "fr": ["one", "many", "other"], "es": ["one", "many", "other"],
    "es-419": ["one", "many", "other"], "it": ["one", "many", "other"],
    "pt-BR": ["one", "many", "other"], "pt-PT": ["one", "many", "other"],
    "ca": ["one", "many", "other"],
    "ru": ["one", "few", "many", "other"], "uk": ["one", "few", "many", "other"],
    "pl": ["one", "few", "many", "other"], "cs": ["one", "few", "many", "other"],
    "ar": ["zero", "one", "two", "few", "many", "other"], "he": ["one", "two", "other"],
    "ja": ["other"], "ko": ["other"], "zh-Hans": ["other"], "zh-Hant": ["other"],
    "zh-HK": ["other"], "th": ["other"], "vi": ["other"], "id": ["other"], "ms": ["other"],
}
FILL_MANY = {"fr", "es", "es-419", "it", "pt-BR", "pt-PT", "ca"}
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

def typo(lang, v):
    if lang.startswith("fr"):
        v = re.sub(r" :", " :", v)
        v = re.sub(r" ([;?!])", " \\1", v)
        v = v.replace("« ", "« ").replace(" »", " »").replace(" %%", " %%")
    return v

ap = argparse.ArgumentParser()
ap.add_argument("--catalog", required=True)
ap.add_argument("--tr", required=True)
ap.add_argument("--copy", default="")
ap.add_argument("--state", default="needs_review")
ap.add_argument("langs", nargs="+")
a = ap.parse_args()

cat = json.load(open(a.catalog))
source = cat.get("sourceLanguage", "en")
copy = set(filter(None, a.copy.split(",")))
errors = []

for lang in a.langs:
    need = FORMS.get(lang) or FORMS.get(lang.split("-")[0])
    if not need:
        sys.exit(f"{lang}: add its CLDR plural categories to FORMS")
    unit = lambda v: {"stringUnit": {"state": a.state, "value": typo(lang, v)}}
    data = json.load(open(pathlib.Path(a.tr) / f"{lang}.json"))
    for k in set(data) - set(cat["strings"]):
        errors.append(f"{lang}: unknown key {k}")
    for key, entry in cat["strings"].items():
        if entry.get("shouldTranslate") is False:
            continue
        src = entry["localizations"].get(source)
        if src is None:
            continue
        if key in copy:
            entry["localizations"][lang] = {"stringUnit": {"state": "translated", "value": src["stringUnit"]["value"]}}
            continue
        if key not in data:
            errors.append(f"{lang}: missing {key}"); continue
        v = data[key]
        if "variations" in src and "plural" in src["variations"]:
            ref = src["variations"]["plural"]["other"]["stringUnit"]["value"]
            if not isinstance(v, dict):
                errors.append(f"{lang}: {key} needs plural forms {need}"); continue
            forms = dict(v)
            if lang in FILL_MANY and "many" not in forms and "other" in forms:
                forms["many"] = forms["other"]
            if sorted(forms) != sorted(need):
                errors.append(f"{lang}: {key} forms {sorted(forms)} != {need}"); continue
            for f, t in forms.items():
                if specs(t) != specs(ref):
                    errors.append(f"{lang}: {key}[{f}] placeholders differ: {t!r} vs {ref!r}")
            entry["localizations"][lang] = {"variations": {"plural": {f: unit(forms[f]) for f in need}}}
        elif "substitutions" in src:
            tmpl = v.get("template") if isinstance(v, dict) else None
            if not tmpl or specs(tmpl) != specs(src["stringUnit"]["value"]):
                errors.append(f"{lang}: {key} template placeholders differ: {v!r}"); continue
            forms = {f: t for f, t in v.items() if f != "template"}
            if lang in FILL_MANY and "many" not in forms and "other" in forms:
                forms["many"] = forms["other"]
            if len(src["substitutions"]) != 1:
                errors.append(f"{lang}: {key} has several substitutions; merge by hand"); continue
            name, sub = next(iter(src["substitutions"].items()))
            if sorted(forms) != sorted(need) or any("%arg" not in t for t in forms.values()):
                errors.append(f"{lang}: {key} substitution forms wrong: {forms}"); continue
            sub = dict(sub)
            sub["variations"] = {"plural": {f: unit(forms[f]) for f in need}}
            entry["localizations"][lang] = {"stringUnit": {"state": a.state, "value": typo(lang, tmpl)},
                                            "substitutions": {name: sub}}
        else:
            ref = src["stringUnit"]["value"]
            if not isinstance(v, str) or not v.strip():
                errors.append(f"{lang}: {key} empty or not a string"); continue
            if specs(v) != specs(ref):
                errors.append(f"{lang}: {key} placeholders differ: {v!r} vs {ref!r}")
            entry["localizations"][lang] = unit(v)

if errors:
    print("\n".join(errors)); print(f"{len(errors)} errors; nothing written"); sys.exit(1)
pathlib.Path(a.catalog).write_text(
    json.dumps(cat, ensure_ascii=False, indent=2, separators=(",", " : ")) + "\n", encoding="utf-8")
print("merged", ", ".join(a.langs), "as", a.state)
