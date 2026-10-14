# Workflow details and pitfalls

Lessons from a real migration (a macOS app, 429 keys, en and zh-Hans to 9
languages). Read the section you need.

## Catalog JSON shapes

Plain entry:
```json
"review.title" : { "comment" : "…", "extractionState" : "manual",
  "localizations" : { "en" : { "stringUnit" : { "state" : "translated", "value" : "What the scan found" } } } }
```

Plural, when the count is the only argument:
```json
"en" : { "variations" : { "plural" : {
  "one"   : { "stringUnit" : { "state" : "translated", "value" : "%lld item found" } },
  "other" : { "stringUnit" : { "state" : "translated", "value" : "%lld items found" } } } } }
```

Several arguments with one count (use substitutions; the count is `argNum`):
```json
"en" : { "stringUnit" : { "state" : "translated", "value" : "%#@items@ · %2$@ selected" },
  "substitutions" : { "items" : { "argNum" : 1, "formatSpecifier" : "lld",
    "variations" : { "plural" : {
      "one"   : { "stringUnit" : { "state" : "translated", "value" : "%arg item" } },
      "other" : { "stringUnit" : { "state" : "translated", "value" : "%arg items" } } } } } } }
```

The compiled bundle splits these up. Plain entries go to `<lang>.lproj/Localizable.strings`, and entries with variations go to `Localizable.stringsdict`. Any test that reads the compiled tables must read both.

A language may have plural variations even where English doesn't. This is useful for agreement, as in "%lld selected" in French.

## Generated symbols

- The build setting `STRING_CATALOG_GENERATE_SYMBOLS = YES` needs catalog version 1.1. Only manual keys get symbols, and every migrated key is manual.
- Naming: periods are removed and the key is camel-cased. `review.heldBy.hint` becomes `.reviewHeldByHint`.
- Argument types follow the specifiers: `%lld` is `Int`, `%@` is `String`. A substitution's argument takes the substitution name as its label, so `confirmSummary(items:_:)`.
- The generated file is at `DerivedData/…/DerivedSources/GeneratedStringSymbols_Localizable.swift`. Read it rather than guessing the labels.
- If the call sites compile on the first try after rewriting, every argument type already matched. That is a useful free check.
- Keys assembled at run time (`"category.\(rawValue)"`) stay as strings. A check script should confirm each such prefix still has catalog keys under it.

## The locale-override probe

Apps that offer an in-app language picker usually write `AppleLanguages`. Before moving call sites to `String(localized: LocalizedStringResource)`, prove it honours the override:

```swift
import Foundation
let app = URL(fileURLWithPath: CommandLine.arguments[1])
let r = LocalizedStringResource("some.key", table: "Localizable", bundle: .atURL(app))
print(Locale.current.identifier, Locale.preferredLanguages.prefix(2), String(localized: r))
```

Run it three times, against the built `.app`: with no arguments, with `-AppleLanguages '(en)'`, and with `-AppleLanguages '(zh-Hans)'`. The result must follow the override even when the system language differs. In the real test it did: `Locale.current` stayed at the system locale while the string followed `AppleLanguages`.

Don't switch views to `Text(LocalizedStringResource)` without the same probe. SwiftUI resolves that through the environment locale.

## Migration traps

- **Dirty tree.** `git rm` fails when the index and the working tree differ. Delete with `rm` and leave the staging to the user. Check the snapshot matches the working tree before deleting.
- **InfoPlist.** Creating `InfoPlist.xcstrings` can make Xcode extract `CFBundleDisplayName`. That silently localizes an app name that differs between Debug and Release. Only create it when a usage description or similar needs translating.
- **App name with spaces.** Debug builds are often named something like "App Dev.app". Always quote paths, or find the bundle with `find … -name '*.app'`.
- **Scripts that search for `L10n.string("…")`** find nothing after the rewrite. Point them at the catalog instead.

## Translating inline

- Read the whole source with its comments, grouped by comment, before writing anything. The comments carry the intent.
- Write one JSON file per language and merge with `merge_translations.py`. Merge each language as soon as it is written, so errors are found early.
- Keep terms consistent across strings that point at each other. A button name quoted in a message must match the button's own string. So must a checkbox label quoted in an error.
- After merging, format a plural key at 0, 1, 2 and 1,000,000 per locale, and one substitution string. In fr and pt, CLDR puts 0 in `one` ("0 élément"). That is correct.

## Visual QA and privacy

- Launch one locale: `open -n App.app --args -AppleLanguages '(de)' [debug flags]`.
- Never capture the whole screen: the user may be in a meeting or screen-sharing. Capture only the app's window, for example `screencapture -l $(osascript … windowID)`, or ask the user to look.
- If a capture shows anything other than the app, delete it right away, tell the user, and stop taking screenshots.
- Quit only processes you launched, matched by their exact path (for example the DerivedData path). Never kill by app name alone.

## Review checklist (Phase 2b)

Review as a professional localizer for that market, reading the whole
language side by side with the source and the reference language. For each
entry, check:

1. **Meaning.** Nothing added, dropped or softened. Promises ("does not
   remove", "never") stay absolute. Conditions ("may", "usually") keep their
   strength.
2. **System terms.** Every OS noun and menu path is exactly what the OS shows
   in that language (look it up with `scripts/system_terms.py`; the table in `references/translation-guide.md` is verified for macOS 26). Watch for near misses
   such as 程序坞 / Dock, Papierkorb / Mülleimer, or 環境設定 / 設定.
3. **Register.** It matches the OS form of address and is used the same way
   everywhere. No mixing *du*/*Sie* or *tú*/*usted*, and no colloquialisms.
4. **Grammar and agreement.** Gender and number agree with the nouns, and
   participles agree after counts ("1 sélectionnés" is wrong). Check
   case after prepositions in de, and particles in ja/ko: が/を/は, 을/를
   and 이/가 after a `%@` name, where the `(이)가` form is acceptable.
5. **Plurals.** Every CLDR form is present and reads correctly at 0, 1, 2 and
   5 (and 21, 22 and 25 for ru/pl).
6. **Punctuation and typography.** fr no-break spaces; the quotation marks
   each language uses (de „…“, fr « … », es «…», ja/zh 「…」); CJK full-width
   punctuation with no spaces around it; the ellipsis character `…`, not three
   dots.
7. **Consistency.** A term is translated the same way everywhere. A button,
   checkbox or setting quoted in a message matches that control's own string
   exactly.
8. **Length.** Short UI strings fit (compare with the English, and with the
   longest existing string in the same place). Shorten by rewording.
9. **Naturalness.** It reads as if written in that language. Rewrite
   calqued word order and nominal chains, especially in ja/ko/de.
10. **Culture and compliance.** Units, number and date formats come from the
    formatter and are not hard-coded. Name legal, privacy, subscription and
    health claims in the handoff rather than approving them silently.

Record every change in `Localization/review/<lang>.md` as key | before | after | reason.
