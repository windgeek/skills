# App Store Connect: versions, uploads and the store page

Learned shipping an iOS + Mac Catalyst app through a major version in nine languages (2026-10). Every change here is outward-facing: get the user's go-ahead before an upload or a store edit, and never press Add for Review or Submit yourself.

## Versions and uploads for iOS + Mac Catalyst

- One app record, two platforms, **one shared bundle ID** (Universal Purchase). Archive each platform separately: `archive_app.sh --platform ios` and `--platform catalyst`. Never upload the iOS archive as the Mac build.
- Each platform has its own version train. When a marketing version is already approved on **one** platform, that train is closed there: the upload fails with "Invalid Pre-Release Train … closed for new build submissions" / "must contain a higher version than … previously approved". The other platform's upload may still succeed. Fix: raise the marketing version for **both** platforms (keep them in step), rebuild, re-archive both. A build already uploaded under the old version just goes unused.
- A major visual change (new main screen, new icon) is a new major version (3.x → 4.0). Do the work on its own branch and merge once the user has seen it on a device.
- Verify an iOS archive the same way as a Mac one: Organizer version/build equal the app's, bundle ID, team, `UIUserInterfaceStyle`, and that new asset-catalog entries are in `Assets.car` (`xcrun assetutil --info`).

## The version page (per locale)

- A new version may start with **Promotional Text and What's New empty** and the Support URL carried over from the old version. Check every field in every locale.
- Write release notes as a file in the repo first (`docs/…/releases/<version>/localized-update.json`), review them per language (system terms via apple-app-localization), then enter them. Same text on iOS and macOS is fine when it mentions platform-specific changes ("On Mac, …").
- The release option ("Automatically release … no earlier than <date>") is per platform. Point it out to the user before review.

### Filling fields from a script (browser automation)

- Version-page text fields accept a value set with the native setter plus `input`/`change`/`blur` events; Save then enables and persists.
- The **App Privacy → Privacy Policy** dialog does not: its Save stays disabled until the URL is typed with real keystrokes (triple-click the field, type).
- The Privacy Policy URL lives on **App Privacy**, not on App Information. It is per locale, behind its own Edit dialog.
- Keep long values in `sessionStorage` (survives reloads), not in `window`.

### Switching locales safely

- The locale menu is anchored to the right; its button moves as the label width changes ("French" vs "Chinese (Simplified)"). Click the chevron at the right edge, not the label's centre.
- **A click on a menu item can silently miss** and leave the page on the previous locale. Twice this put one language's text into another (once saved). Every write must first check that the visible locale button reads the expected language, and refuse otherwise.
- After all writes, **reload and read every locale back**. Clicking during a page load also misses, so wait for the content before the first click.

## Media Manager (screenshots)

- Find it via "View All Sizes in Media Manager". Deep links to `/media-manager/ipad` may bounce to the version page; open `/media-manager/iphone` and click the iPad tab.
- Limits: 10 screenshots per set, 10 MB per upload call from the browser tool, so split a set into calls of 2–3 files and upload **in display order**.
- **Remove All** opens a confirmation ("they remain in your Asset Library"): it detaches, it does not delete files. Replacing a store set is still a destructive action: ask the user once for the whole job, and expect the agent's own safety layer to require that explicit approval.
- Clearing an **optional** set collapses its section, and its file input leaves the DOM. A selector that finds "the input near this label" can then pick the neighbouring set's input (an upload into the medium-display set was rejected only because the sizes were wrong). Expand the section again and re-resolve the input after every clear.
- Clearing a non-primary locale's set makes it fall back to "Using Existing Assets" from the primary language until new files arrive; the section text then starts with "Using…". Match sections by their own header text, not by the first ancestor that mentions screenshots.
- Set names and what to put in them:
  - iPhone: the required "medium display" set reuses the "large display" (6.9″) uploads; upload only the large set.
  - iPad: one "iPad 13″ display" set is used for every iPad size; an info dialog says so on first upload (OK button).
  - iPhone Duo: **one** set takes both outer (1398×2034) and inner (2853×2007 landscape / 2007×2853) sizes, 10 in total. With 6 posters per display, drop the least device-specific slide from each (e.g. the Lock Screen card) to fit 5 + 5.
  - Mac: one "Mac" set, 2880×1800.
- Read back each set's "N of 10 App Screenshots" per locale after a reload. Parse the page text; `\b` after a closing parenthesis never matches, so don't put a word boundary there.
- **Stuck uploads block review.** "Unable to Add for Review: 1 or more screenshots must finish uploading" means a tile is a grey cloud placeholder that never finished. It still counts toward "N of 10", so counts alone don't catch it. Scan each locale and device tab for `[aria-label^="Screenshot "]` tiles with no `img` inside. Fix: hover the tile, click its red minus badge, Remove, then re-upload that file. A stuck tile mid-set: remove it and every tile after it (from the end), then upload them again in order. Upload **one file per call** and wait until each tile shows its image; multi-file calls are where tiles got stuck, and a re-upload can fail silently, so read the set back after a reload.
- The browser tool's `find` is model-backed and rate limited. Mark the target input (`aria-label`) in JS and use `find` only to turn it into a ref; check in JS that exactly one element is marked before uploading.

## Header and search-results assets (iOS 27)

New in 2026: under the version page's **Header and Search Results** tab.

| Asset | Size | Notes |
|---|---|---|
| Product page header | 3840 × 1646 (21:9) JPEG/PNG, or 5244 × 2950 PNG | No alpha. Template safe area x 1097–2743, y 493–1154. |
| Search results | 3840 × 2560 (3:2), min 1920 × 1280, or 5244 × 2950 PNG | No alpha. Safe area x 836–3004, y 765–1795. Shown about 365 pt wide on iPhone. |

- Uploaded on the primary locale, the **header is inherited** by every other locale ("Using primary language asset"); upload once. A wordless header (the app's art opened wide) needs no localization.
- The **search image is per locale**: headline + the real app screen, all of it inside the safe area, type large enough for 365 pt. Fill the area outside the safe band with quiet art so the full 3:2 card is not empty, and fade that art out before the text column so nothing crosses a letter.
- Apple's rules for both: no prices, URLs, ©, other platforms' logos, Apple awards, unverifiable claims.
- Asset Library holds everything ever uploaded, so a removed screenshot can be reused.
