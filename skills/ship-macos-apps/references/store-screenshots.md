# App Store screenshots and posters

Store posters are product UI: a clipped heading or a blank panel on the product page makes the app look broken. These rules come from poster pipelines that each crop a real capture onto a 2880×1800 (Mac), 1320×2868 (iPhone 6.9″) or 2064×2752 (iPad 13″) canvas.

## Order: overview first, then one feature each

The set is general-then-specific:

- Poster 1 is the overview. It names every major feature in its copy and shows them as one main workspace plus small capability cards.
- Each later poster explains one feature.
- A version's new feature gets two changes: add it to the overview (subtitle, chips, a capability card), and give it its own poster at the **end** of the set. Don't move it to the front and push the overview out of first place.

## Crops

- Write every crop in raw-capture **pixels from the top-left**, the way the PNG looks in Preview. `NSImage.draw(in:from:)` measures its source rect from the **bottom-left** and in points; a crop picked by eye and passed straight to it shows the wrong band. Prefer `CGImage.cropping(to:)`, which is top-left pixels.
- Draw a crop **whole**: size the destination to the crop's aspect ratio. Never aspect-fill (silently trims the crop again) and never stretch.
- Hand-tuned pixel crops go stale. When the app's layout, the capture window or the scene moves, recheck every crop. Locate UI whose size follows the locale (toolbars, HUDs, buttons) per locale, e.g. by its fill colour, instead of fixing its width.
- A crop that frames "the interesting part" must still keep the controls that say what the app does. A breathing orb with no title, buttons or timer, or a chart without its toolbar, is not a screenshot of the app in use.

## Guards (run them as part of composing, failing the run)

1. **Crop edge check**: sample a line just inside each edge of every crop and count strong luminance crossings. Background crosses a few panel borders; a line through text crosses dozens. Failing at more than about 6 catches cut headings and cut columns.
2. **Empty-crop check**: a crop with almost no bright pixels no longer frames the UI (typical after a recapture shifts the layout).
3. **Safe area**: render the same background alone, diff it with the finished poster, and require every foreground pixel at least about 96 px (Mac) from the poster edge.
4. **Edge-sliver check**: a 5–48 px band along a crop edge whose colour differs from the content inside it (compare colour, not luma: a violet sidebar beside a grey panel has nearly the same brightness) is a sliver of a neighbouring panel or margin. At store size it reads as a grey or coloured strip stuck to the card. Put the edge on the panel's own border or leave a clear margin. Skip this check for HUD crops whose padding is intentional and clipped.
5. **Copy-column check**: fail when a subtitle line, chip row or card label runs past its column, instead of letting it collide with the product image.
6. **Detail-kept check**: a crop can cut cleanly and still leave out the UI that matters (one iPad crop kept the orb and dropped the title, icons and all three cards). Sum the capture's strong horizontal edges; fail when the crop keeps less than about 85% of them.
7. When a guard fails, move the crop or layout. Don't raise the limit.

The simplest pipeline needs few guards: draw the **whole** capture (no crop) at the device's real corner radius under one headline. That design (one background, one serif headline, a short gold rule, one subtitle, the same for every device and language) replaced per-slide colours and crops and read better at store size.

Prove each guard on the known-bad version before trusting it.

## Captures

- Capture from the Debug identity in a staged scene. Sandboxed Debug apps write into their sandbox container (`Library/Containers/<debug-id>/Data/` in the home folder). Reading that from another app (an agent's shell, an IDE terminal) fails with `Operation not permitted` until that host app has Full Disk Access and has been relaunched. The macOS Terminal app may already have it.
- A staged scene that pins "what's on screen" must cut the pin from a capture taken **after** the backdrop went up. A capture session snapshot taken before the backdrop holds the real desktop. A picture-in-picture backdrop window must sit below the menu bar (`visibleFrame`), or a strip of the real menu bar ends up at the top of every raw.
- A demo annotation must sit on something that explains it: a mosaic over blank panel edges looks like a rendering glitch, while a mosaic over an email address reads as redaction.
- Any scene that captures "what's on screen" (pin, overlay, magnifier, OCR) captures the **real desktop**: one recapture put lines of a private chat inside every locale's pin poster. Check every new raw for real-screen content before composing, and handle a hit by the privacy rule in apple-app-localization § Phase 3: Visual QA and storefront (remove it at once, tell the user). For scenes whose copy doesn't change between versions, keep the previous good raws, and back up `Raw/` before recapturing.
- Check animated values: a timer captured mid-transition shows a ghosted digit. In screenshot mode turn off value transitions (`.contentTransition(.identity)` instead of `.numericText()`) and set `transaction.animation = nil` on the root, and capture a running scene **mid-phase**, not on a phase boundary (a 6 s wait on 5.5 s phases caught two phases crossfading).
- Localized UI truncation (`Kohärente At…`, `Démar…`) in a capture is an app bug that the store will show. Fix the layout or the string, then recapture. Prefer one line at full size, then one line slightly smaller, then two lines (`ViewThatFits`), so CJK names stay on one line and long Latin names wrap between words. Give a badge next to a title a fixed width (the widest of its values) so the title never re-wraps as the badge changes.
- **Mac Catalyst form sheets**: `.presentationSizing(.form)` is a fixed card of about 470 × 400 pt in the Mac idiom and cut lists and charts off. Use `.form.fitted(horizontal: false, vertical: true)` on Catalyst. This is a real-user bug, not just a capture problem.
- **Dark-only apps must force dark** (`INFOPLIST_KEY_UIUserInterfaceStyle = Dark`). Without it, a Mac switches to Light by day and the app's materials turn grey: daytime captures differed from evening ones with no code change. To tell a regression from machine state, build the previous commit in a `git worktree` and capture it the same way.
- Mac window captures fail with "could not create image from window" while the **screen is locked** (`ioreg -n Root -d1 -a | grep -A1 CGSSessionScreenIsLocked`). Simulator captures keep working; run those meanwhile and ask the user to unlock.
- A Mac capture launch occasionally never shows a window; relaunch once before failing.
- iPhone Duo has two displays to capture: see [iphone-duo.md](iphone-duo.md).
- Headlines in a serif: New York's default optical size is the 256 pt display cut, whose hairlines vanish at store size ("Hören" read as "l lören"). Pin the optical-size axis to the text cut (about 32) when rendering with PIL (`set_variation_by_axes`).

## Review at store size

- Render every locale's posters at roughly the store card size (about 440–560 px wide for Mac, about 150–200 px for iPhone/iPad) into one contact sheet per device. Look at it, then open the suspicious ones at full size.
- App Store Connect's preview can show a different upload from the live page. Compare against the local files you intend to upload, not the ASC preview.
- Never upload screenshots or change store metadata without the user's go-ahead. Screenshots can only change with a new version.
- Uploading and replacing sets, header and search-result assets, and per-locale traps in App Store Connect: see [app-store-connect.md](app-store-connect.md).
