---
name: apple-app-localization
description: Internationalize, localize and translate Apple-platform apps (macOS, iOS, iPadOS, Mac Catalyst, watchOS, tvOS, visionOS) with Xcode String Catalogs — migrating legacy .strings/.stringsdict, generated string symbols, plural and device variations, adding languages, translating and reviewing copy, locale QA, and App Store copy. Use automatically whenever work on an Apple app adds or changes user-facing text in a .xcstrings/.strings file (new features, new screens, copy edits), not only when the user asks to localize; also when they ask to internationalize, add languages, translate, or clean up Localizable.strings. Holds the translation rules and system-term table, so projects need no TRANSLATION.md. Not for websites or non-Apple apps.
---

# Apple App Localization

Build a localization system that stays correct as the app grows, without changing product behavior. Migration, translation, UI verification and storefront copy are separate deliverables. Finish and verify one before starting the next, and tell the user what was verified at each step.

Scripts live next to this file. Resolve `<skill>` to this skill's directory; never assume the project contains them.

The translation rules, the verified system-term table and the punctuation rules are in `references/translation-guide.md`. They belong to this skill, not to any project: don't create a `TRANSLATION.md` in a repo, and if a project has one, fold its project-specific parts into catalog comments and a short "Localization" section of the project's agent instructions file, AGENTS.md or CLAUDE.md (see the guide), then remove it.

**When the user has no native-speaker reviewers, the agent's review is the final review.** Nothing waits for a human: every string the agent drafts goes through the Phase 2b review pass in the same task and ships as `translated`. `needs_review` is a working state inside a task, never a handoff state.

## Everyday use: a change adds or edits strings

Most of the time the catalog already exists and a feature adds a few keys. Do this before calling the feature done:

1. Read the project's "Localization" section (AGENTS.md / CLAUDE.md, or README) and `references/translation-guide.md`.
2. Write the English source with a `comment` on each new entry, then draft every shipped language. Look up each OS term with `scripts/system_terms.py`; never guess one.
3. Insert entries without reformatting the rest of the catalog. Xcode's JSON layout differs from `json.dump`, and a rewrite of the whole file buries the change in noise. Splice new blocks in at their sorted position, or use `merge_translations.py`.
4. Run the Phase 2b review on the new keys only (`dump_for_review.py --only-pending`), one language at a time, as a separate pass from drafting. Fix, then mark `translated`.
5. Append the changes to the project's review log (`Localization/review/<lang>.md`, or create it): key | before | after | reason, plus the system terms checked.
6. Gate on `audit_xcstrings.py --fail-on-review` and the project's own localization tests or scripts.

## Phase 0: Audit (read-only)

Before editing, establish:

- **Tooling.** Run `xcodebuild -version`. Xcode 26+ generates catalog symbols; Xcode 27+ adds agent translation (GUI only).
- **Current state.** Record `developmentRegion` / `knownRegions` in the pbxproj, and existing `*.lproj/*.strings`, `.stringsdict`, `.xcstrings`, `InfoPlist.strings`.
- **Project format.** Check whether the project uses synchronized folders (`PBXFileSystemSynchronizedRootGroup`). If it does, new files are picked up automatically, but deleted files must really be deleted.
- **How code reaches strings.** Look for a wrapper (such as `L10n.string`), `NSLocalizedString`, `String(localized:)`, or `Text("literal")`. Count the call sites.
- **Keys assembled at run time**, such as `"category.\(rawValue)"` or a key held in a variable. The compiler cannot check these.
- **Count strings** that use `%d`/`%ld` next to a noun. These are plural bugs waiting to happen.
- **Sentences built by concatenation or interpolation**, such as `Text("\(a): \(b)")`. Punctuation and word order differ per language.
- **The in-app language override**, if any (usually by writing `AppleLanguages`).
- **Tests and scripts that read `.strings` files directly.** They break after migration.
- **Git state.** If the tree is dirty or has no commits, snapshot the old resources to a scratch directory before touching anything; that snapshot is the comparison baseline.

## Phase 1: Migrate to a String Catalog (no visible change except plural fixes)

1. **Convert.** Run `python3 <skill>/scripts/migrate_strings.py <app-source-dir>`. It merges every `*.lproj/Localizable.strings` into `Localizable.xcstrings`:
   - format version 1.1, with `extractionState: manual` on every key;
   - each block comment becomes the comment of the entries under it;
   - `%d` becomes `%lld`.

   It prints the count strings that are likely plural candidates.
2. **Add plurals.** Use `variations.plural`: `one`/`other` in English, only `other` in zh/ja/ko. For a string with more than one argument, use `substitutions` (`%#@items@ … %2$@`); see `references/workflow.md`.
3. **Delete the old files.** Remove the `.lproj/*.strings` files; Xcode refuses a catalog alongside a same-named table. Keep the snapshot. Don't create an `InfoPlist.xcstrings` unless something in Info.plist actually needs translating. A catalog can silently localize `CFBundleDisplayName` and override a Debug/Release naming scheme.
4. **Generate symbols.** Add `STRING_CATALOG_GENERATE_SYMBOLS = YES` to the app target's Debug and Release configurations. Build, then read `DerivedSources/GeneratedStringSymbols_Localizable.swift` for the real symbol names and argument labels.
5. **Rewrite call sites.** Run `python3 <skill>/scripts/rewrite_call_sites.py --generated <that file> --wrapper L10n.string <repo>`. It turns `L10n.string("a.b", n)` into `L10n.string(.aB(n))`, using labels from the generated signatures. Keys assembled at run time are skipped and listed. Keep the project's wrapper and add one overload:
   ```swift
   static func string(_ resource: LocalizedStringResource) -> String { String(localized: resource) }
   ```
   Now a misspelt key or a wrong argument type is a compile error.
6. **Fix concatenation.** Turn concatenated sentences into one catalog entry (`"%1$@: %2$@"`, with `%1$@：%2$@` in CJK), and turn pure numbers into `Text(verbatim:)`.
7. **Update checks.** Tests that read `Localizable.strings` must also read the compiled `Localizable.stringsdict`, or plural copy escapes them. Key-parity tests should iterate `Bundle.main.localizations`.
8. **Verify.** Nothing from Phase 1 counts as done until all of these pass:
   - Build Debug and Release, and run the tests.
   - Run `<skill>/scripts/compare_bundles.swift` between the snapshot and the new `.app`. It checks every key in every language at counts 1 and 5. The only allowed differences are intended plural fixes.
   - Prove the language override still works. System language X plus an `AppleLanguages` override of Y must resolve to Y through `String(localized: LocalizedStringResource)`. `references/workflow.md` has a 10-line probe.

## Phase 2: Add languages

1. **Choose languages.** Default high-value set: `zh-Hant ja ko de fr es pt-BR`. Confirm it with the user if they have not already chosen.
2. **Record the project's rules.** Add a short "Localization" section to the project's AGENTS.md / CLAUDE.md (or README): the reference language, tone and banned words, key prefixes that are promises, and terms that must stay consistent. Put per-string intent in catalog comments. Everything general is already in `references/translation-guide.md`; don't copy it into the repo.
3. **Draft the translations.** Write one `tr/<lang>.json` per language in a scratch directory. The value is a string, or `{"one":…,"other":…}` for plural keys, or `{"template":…, <forms>}` for substitution keys. Drafting inline is fine for catalogs up to about 1,000 keys. Read the whole English source with comments first, and use the reviewed secondary language (for example zh-Hans) as the tone reference.
4. **Merge.** Run `python3 <skill>/scripts/merge_translations.py --catalog <path> --tr <dir> [--copy key,…] <langs…>`. It refuses to write anything unless:
   - every key is present;
   - placeholders match English by kind and position;
   - plural forms match the CLDR categories (fills `many` from `other` for fr/es/pt/it).

   It also applies French no-break spaces. New entries get `state: needs_review` until the review pass in Phase 2b.
5. **Register the languages.** Add the new locales to `knownRegions` in the pbxproj.
6. **Audit.** Run `python3 <skill>/scripts/audit_xcstrings.py --required-locales … <catalog>`. Build and test.
7. **Runtime probe.** Format a plural key at 0, 1, 2 and 1,000,000 in each locale, and a multi-argument substitution string.
8. **Check agreement.** An English participle that doesn't change with number ("%lld selected", "%lld found") becomes a plural adjective in fr/es/pt ("1 sélectionnés" is wrong). Rephrase as a label, "Sélection : %lld", or give that language a plural variation.
9. **Length check.** Flag short UI strings (buttons, tabs, titles) more than 1.6× the English length in de/fr/es/pt. Don't shorten the system's own terms.

## Phase 2b: Professional review (by the agent, when no native speaker is available)

Unless the user has native reviewers, the agent does the review, as a professional localizer for each language, in a pass separate from drafting. Drafting and reviewing in the same breath catches nothing. Review one language at a time:

1. **Load the catalog.** Run `python3 <skill>/scripts/dump_for_review.py --catalog … --lang <lang> --ref zh-Hans`. It prints that language next to the source and the reference language, grouped by the source comments. Read all of it. Don't sample.
2. **Check every entry** against `references/workflow.md` § Review checklist. That covers meaning, system terms, register, grammar and agreement, plurals, punctuation, consistency, length, and anything culturally off. Verify every OS term with `scripts/system_terms.py` rather than from memory: in a real review, 聚焦 (zh-Hans Spotlight), Übersicht (de Quick Look) and 系統完整保護 (zh-Hant SIP) were all wrong in drafts that looked fine.
3. **Fix the draft, then re-merge.** Edit `tr/<lang>.json` and run the merge again with `--state translated`. The merge re-validates placeholders and plural forms.
4. **Keep a review log** in the project at `Localization/review/<lang>.md`. List each change as key, before, after and reason, and list the terms checked against the system. Then give the user a short summary per language: number of changes, and the kinds of problem found.
5. **Name the sensitive strings.** Legal, medical, financial, and claims Apple reviews (privacy, subscriptions, permissions) get extra care in the pass. List them in the handoff so the user knows where a wording mistake would cost most, but still finish the review and mark them translated: there is no one else to hand them to. (If the user does have native reviewers, hand them the review log and these strings.)

After this pass, `needs_review` should be 0. Use `audit_xcstrings.py --fail-on-review` as the gate.

## Phase 3: Visual QA and storefront

Screenshots come after the user has verified functionality, and only when they ask.

- **Never** run a full-screen `screencapture`. The user's screen may be showing a meeting or private content. Capture only the app's own window: use `screencapture -l <windowID>` or the app's own snapshot mechanism. Or ask the user to look for themselves, giving them the exact launch command:
  ```bash
  open -n "<App>.app" --args -AppleLanguages '(de)'
  ```
  If an unintended capture happens, delete it at once and tell the user.
- Storefront copy (name, subtitle, keywords, description) is per locale and must use the same terms as the app. Publishing to App Store Connect is a separate action that needs explicit permission.

## Handoff

Report:

- the languages added and catalogs changed;
- the plural and substitution entries introduced;
- the builds and tests run, with results;
- the runtime probes run;
- what was *not* visually inspected;
- the `needs_review` count per language;
- per language, the review-pass summary: changes made, and anything flagged for outside review.

Say plainly that the translations were drafted and reviewed by an AI agent (name the model). Name the strings where a mistake would matter most, such as legal, commerce and permissions text.
