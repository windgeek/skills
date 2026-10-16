---
name: ship-macos-apps
description: Develop, debug, test, diagnose, archive, distribute, and release native macOS apps safely with Xcode, AI coding agents (Codex, Claude Code…), TestFlight, and App Store Connect. Use for macOS vibe-coding workflows; Debug/Release identity separation; bundle IDs, signing, entitlements, TCC privacy permissions, Screen Recording, Accessibility, menu bar NSStatusItem issues, launch-at-login, LaunchServices conflicts, TestFlight updates, clean-install testing, App Store screenshots and posters, App Review preparation, or diagnosing behavior that differs between the developer Mac and other testers.
---

# Ship macOS Apps

Use separate identities and environments for development and distribution. Treat macOS privacy state, code signing, LaunchServices, and Control Center as part of the product—not as incidental machine state.

## Start with evidence

1. Read repository instructions and inspect the Xcode project, schemes, configurations, entitlements, Info.plist, version/build settings, and current working tree.
2. Preserve user changes. Do not clean DerivedData, reset TCC, delete containers, unregister apps, or modify Control Center before gathering evidence and obtaining authority for destructive changes.
3. Run the read-only project audit when an Xcode project is available:

   ```bash
   scripts/audit_project.sh --project /absolute/App.xcodeproj --scheme App \
     --debug-id com.example.App.debug --release-id com.example.App
   ```

4. Run the installed-app audit before diagnosing a TestFlight or App Store build:

   ```bash
   scripts/audit_installed_app.sh /Applications/App.app
   ```

5. Compare affected and unaffected machines/builds before changing code. If the same TestFlight build works for another tester, prioritize local identity, TCC, LaunchServices, Control Center, login-item, and stale-process state.

## Keep four lanes separate

### 1. Agent and Xcode development

- Use a dedicated Debug bundle identifier, such as `com.example.App.debug`.
- Use a visibly different Debug display name, such as `App Dev`, and preferably a distinguishable app icon badge.
- Sign Debug with Apple Development under the same intended team, but never reuse the production bundle identifier.
- Let the coding agent build, run, inspect, and restart only the Debug identity.
- Grant privacy permissions to Debug independently. Never interpret Debug permission as proof that Release/TestFlight has permission.
- Use unit, integration, UI, and feature tests here. Iterate quickly without touching production identity state.

### 2. Local Release and Archive

- Build Release and Archive for compilation, signing, entitlement, asset, and upload validation.
- Change the build number and version with `scripts/bump_build.sh --project /abs/App.xcodeproj [--version X.Y[.Z]|major|minor|patch] [build]`, not Xcode's General tab. A value typed there can reach the archived app while the archive metadata keeps the old number, so Organizer lists the wrong build. With no build given it adds one; `--version minor` (likewise `patch`, `major`) increments the current version, e.g. 2.0 → 2.1; `--version` also raises the build, since every new upload needs a higher one, so run it once per archive. The script edits `project.pbxproj`, which Xcode reloads while open; it changes every configuration holding the app's current build (app and extensions, not test targets) and warns if an Info.plist hard-codes `CFBundleVersion` or `CFBundleShortVersionString`.
- Archive without opening Xcode with `scripts/archive_app.sh --project /abs/App.xcodeproj --scheme App`. It writes to the folder Organizer reads, signs with the accounts signed in to Xcode, runs the check below, and prints the archive path last.
- After archiving, run `scripts/check_archive_build.sh` (newest archive, or pass a path). It compares the build Organizer shows with the one inside the app and prints the one-line fix if they differ. Archive folder names contain a narrow no-break space before AM/PM, so pass archive paths by glob or tab completion, never typed.
- Do not launch a production-bundle-ID Release build from the coding agent, a shell, Xcode DerivedData, or an archive path on the daily development account.
- Do not register archive products with LaunchServices for ad hoc testing.
- If local production-identity execution is unavoidable, use a disposable macOS user account or VM and document why.
- Keep the archive immutable after validation. Upload that archive; do not rebuild between final QA and upload.
- Upload with `scripts/upload_archive.sh /abs/App.xcarchive`. Without `--confirm` it only prints version, build, bundle ID, team, architectures and entitlements; show that to the user and upload with `--confirm` only after they approve that exact build, every time. An upload spends the build number and cannot be undone. The script refuses `.debug`/`.dev` bundle IDs and archives whose metadata disagrees with the app. The first command-line signing may raise a Keychain prompt the user must allow.

### 3. TestFlight

- Install and launch the production identity through the visible TestFlight UI, not `open`, a terminal, an agent helper, or an Xcode build product.
- Test both update-over-existing and clean-install paths on real Macs.
- Include at least one clean tester who does not develop the app and has never installed Debug builds.
- Verify exact version and build in TestFlight before testing. Do not rely on the source project's build number if Xcode manages build numbers during upload.
- Test permission continuity, menu bar visibility, shortcuts, launch at login, capture, saving, relaunch, update, and restart.

### 4. App Store release

- Submit the exact TestFlight-validated build to App Review.
- Prefer manual release for a first launch or risky update.
- Do not change code, entitlements, signing, or assets after TestFlight approval without producing and retesting a new build.

Read [references/workflow.md](references/workflow.md) for the detailed test matrix and environment design.

## Handle permissions as state machines

- Never request Screen Recording, Accessibility, microphone, camera, or automation permission at launch unless the app cannot present any useful UI without it.
- Preflight permission when the user invokes the protected feature.
- If not authorized, explain why, request once, and provide a System Settings route plus a non-looping recovery path.
- Recheck on app activation and before retrying the feature. Do not assume the value is permanently cached at launch.
- Never force repeated relaunches. A restart button must be optional, idempotent, and must not reopen the same onboarding stage after authorization.
- Keep permission UI dismissible. If preflight says authorized, continue the action even if onboarding flags are stale.
- Treat bundle identifier, signing team, designated requirement, app path, and distribution channel as identity inputs. Debug and production permissions are intentionally separate.
- Reset TCC only after identity inspection proves the record is stale and the user approves losing that permission state.

Read [references/permissions-menu-bar.md](references/permissions-menu-bar.md) whenever permissions or status items are involved.

## Build menu bar apps defensively

- Create and retain one `NSStatusItem` on the main actor.
- Use a stable item identity if `autosaveName` is needed; never rotate names per build as a routine fix.
- Use a fixed square length for icon-only items and provide an eagerly rendered template image with accessibility text and a tooltip.
- Preserve a second way to reach Settings and Quit, such as opening the app from Finder/TestFlight or a normal window. Apple does not guarantee that status items are always visible.
- On macOS 26+, account for System Settings → Menu Bar → Allow in the Menu Bar. The system may override app intent.
- Do not conclude that a blank menu bar means the image is broken. First distinguish: process absent, item absent, item system-hidden, item offscreen, insufficient space, empty remote image, duplicate bundle registration, or cross-associated Control Center identity.
- Do not “fix” a local-only menu bar failure by changing production code until another clean tester reproduces it.

## Diagnose without contaminating production identity

Use this order:

1. Confirm the exact running executable path, bundle ID, build, signing team, designated requirement, entitlements, and TestFlight/App Store origin.
2. Confirm only one registered app path exists for the production bundle ID.
3. Confirm no Xcode, DerivedData, archive, Trash, or temporary build with the same production bundle ID is registered.
4. Check System Settings menu-bar allowance and available space.
5. Inspect whether Control Center tracks the app under its own bundle identity rather than under the coding agent, a Swift helper, Terminal, or another host.
6. Compare with a clean tester using the same build.
7. Back up relevant state before any targeted repair.
8. Repair the smallest proven local record, restart only the affected service, then launch from TestFlight UI and verify again.

Avoid compiling or running temporary AppKit/Swift GUI probes with the production identity. They can themselves appear as menu-bar providers or responsible launchers and corrupt the evidence.

## Make store screenshots that survive the store page

Posters crop real captures. Write crops as top-left raw pixels (`NSImage.draw(from:)` is bottom-left), draw them whole, find locale-sized UI per locale, and fail the compose step when a crop edge cuts content, a crop is empty, or content comes within the safe margin of the poster edge. Check new captures for real-desktop content and mid-animation values, and review every locale at store card size. Read [references/store-screenshots.md](references/store-screenshots.md) before building or changing a poster pipeline or recapturing.

## Enforce release gates

Before upload or review, read and apply [references/release-gates.md](references/release-gates.md). Stop the release when any required gate fails. Report the exact failing identity, build, entitlement, permission transition, or test case rather than giving a generic warning.

## Prefer fixes that survive updates

- Fix incorrect state-machine logic, identity configuration, or recovery UX in code.
- Treat one-machine corruption as a local repair, not a reason to churn bundle IDs, status-item identities, or permission prompts for every user.
- Add a regression test or build-time guard for each identity/configuration failure.
- Keep a brief release evidence record: archive ID, version/build, commit, signing team, tested macOS versions, clean/update test results, and known limitations.

