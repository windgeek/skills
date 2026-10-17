# iPhone Duo (foldable) support

iPhone Duo shipped 2026-10-23 with Xcode 27.1 / iOS 27.1. Screenshots for it are required from April 2027. Learned adapting a SwiftUI app that ships on iOS and Mac Catalyst.

## What to read first

- `xcrun agent skills export --output-dir <dir>` exports Apple's own Xcode agent skills. `app-resizability` is the official checklist for Duo (UIScreen.main, orientation, idiom, safe-area and scene-lifecycle tasks). Run its prerequisites (launch screen key, iPad orientations, `UIRequiresFullScreen`) before anything else.
- Recompile with the 27.1 SDK; a binary built with an older SDK gets a letterboxed phone window when unfolded.

## The fold

- SwiftUI: `GeometryProxy.reservedRegions(kind: .division, options: .includeInactive)` gives the crease as a frame plus `margins` to keep content away from it. Read it on every body evaluation and never cache it: it is empty during the first layout passes.
- Include **inactive** regions. The crease is inactive when the phone is flat and active when bent into a book; following that flag would re-layout mid-interaction, and the crease is physically there either way.
- `reservedRegions` and `UIHinge`/`UIHingeInteraction` are **unavailable on Mac Catalyst** even though they are "iOS 27.1" APIs. Guard with `#if os(iOS) && !targetEnvironment(macCatalyst)` plus `#available(iOS 27.1, *)`; a Catalyst build catches what an iOS build does not.
- Measure in the coordinate space where the layout actually sits (inside padding and below the top bar), so the crease lines up with the panes.
- Lay out per crease direction: vertical crease (open, book) → content on the leading page, text on the trailing page; horizontal crease (open and turned) → upper and lower pages. Never draw a centred hero element across the fold.
- Book and open-flat have the same window size; keep one layout for both so folding does not rearrange the screen.

## Traps found

- **Idiom checks are wrong on the inner display.** Code like `isFloatingCard = idiom != .phone` treated the inner display as a phone and drew a card inside the system's floating sheet. Decide from the window width (≥ 600 pt) or size class instead.
- **Text written for half a screen.** The trailing page is narrow; titles that fit a full iPad width truncate. Size the side column for the page, not the window.
- **Outer display is short and compact.** Long localized titles (German, French, Spanish, Portuguese) truncated there; give the hero element less height on short phone windows.

## Testing in the simulator

- `simctl` cannot change the pose. Fold and unfold in **Device Hub** (Xcode → Device Hub); its window does not take automated clicks, so ask the user. If unfolding seems to do nothing, Device Hub is probably showing a "Start" button: it is not attached to the booted simulator yet.
- The device has two displays. Screenshot them separately: `xcrun simctl io <udid> screenshot --display=1 out.png` (outer, 1398×2034, portrait closed) and `--display=3` (inner, 2853×2007 landscape when open flat). The display that is switched off returns a black image, which is how to tell the pose from the shell. `xcrun simctl io <udid> enumerate` lists them.
- A screenshot call against an unavailable display can hang; wrap it (`perl -e 'alarm 25; exec @ARGV' xcrun simctl io …`). macOS has no `timeout`.
- Store-screenshot capture: add a display option to the capture script (`--display=1` folded pass, `--display=3` after unfolding), not a second script.
