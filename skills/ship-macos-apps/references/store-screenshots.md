# App Store screenshots and posters

Store posters are product UI: a clipped heading or a blank panel on the product page makes the app look broken. These rules come from poster pipelines that each crop a real capture onto a 2880×1800 (Mac), 1320×2868 (iPhone 6.9″) or 2064×2752 (iPad 13″) canvas.

## Crops

- Write every crop in raw-capture **pixels from the top-left**, the way the PNG looks in Preview. `NSImage.draw(in:from:)` measures its source rect from the **bottom-left** and in points; a crop picked by eye and passed straight to it shows the wrong band. Prefer `CGImage.cropping(to:)`, which is top-left pixels.
- Draw a crop **whole**: size the destination to the crop's aspect ratio. Never aspect-fill (silently trims the crop again) and never stretch.
- Hand-tuned pixel crops go stale. When the app's layout, the capture window or the scene moves, recheck every crop. Locate UI whose size follows the locale (toolbars, HUDs, buttons) per locale, e.g. by its fill colour, instead of fixing its width.
- A crop that frames "the interesting part" must still keep the controls that say what the app does. A breathing orb with no title, buttons or timer, or a chart without its toolbar, is not a screenshot of the app in use.

## Guards (run them as part of composing, failing the run)

1. **Crop edge check**: sample a line just inside each edge of every crop and count strong luminance crossings. Background crosses a few panel borders; a line through text crosses dozens. Failing at more than about 6 catches cut headings and cut columns.
2. **Empty-crop check**: a crop with almost no bright pixels no longer frames the UI (typical after a recapture shifts the layout).
3. **Safe area**: render the same background alone, diff it with the finished poster, and require every foreground pixel at least about 96 px (Mac) from the poster edge.
4. When a guard fails, move the crop or layout. Don't raise the limit.

Prove each guard on the known-bad version before trusting it.

## Captures

- Capture from the Debug identity in a staged scene. Sandboxed Debug apps write into their sandbox container (`Library/Containers/<debug-id>/Data/` in the home folder). Reading that from another app (an agent's shell, an IDE terminal) fails with `Operation not permitted` until that host app has Full Disk Access and has been relaunched. The macOS Terminal app may already have it.
- Any scene that captures "what's on screen" (pin, overlay, magnifier, OCR) captures the **real desktop**: one recapture put lines of a private chat inside every locale's pin poster. Check every new raw for real-screen content before composing, and handle a hit by the privacy rule in apple-app-localization § Phase 3: Visual QA and storefront (remove it at once, tell the user). For scenes whose copy doesn't change between versions, keep the previous good raws, and back up `Raw/` before recapturing.
- Check animated values: a timer captured mid-transition shows a ghosted digit.
- Localized UI truncation (`Kohärente At…`, `Démar…`) in a capture is an app bug that the store will show. Fix the layout or the string, then recapture.

## Review at store size

- Render every locale's posters at roughly the store card size (about 440–560 px wide for Mac, about 150–200 px for iPhone/iPad) into one contact sheet per device. Look at it, then open the suspicious ones at full size.
- App Store Connect's preview can show a different upload from the live page. Compare against the local files you intend to upload, not the ASC preview.
- Never upload screenshots or change store metadata without the user's go-ahead. Screenshots can only change with a new version.
