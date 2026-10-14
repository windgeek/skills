# Permissions and menu bar diagnostics

## Contents

- Identity model
- Screen Recording
- Accessibility and Automation
- Menu bar implementation
- Menu bar diagnostic tree
- Local repair boundaries
- Official references

## Identity model

macOS decides whether code is the “same app” using signed-code requirements, typically including the bundle identifier and signing chain. A matching display name or executable filename is not sufficient.

Use:

```bash
codesign -dv --verbose=4 /Applications/App.app
codesign -dr - /Applications/App.app
codesign -d --entitlements :- /Applications/App.app
```

Keep these stable for production updates:

- production bundle identifier;
- development team/signing chain;
- required entitlements and app groups;
- helper/extension identifiers;
- distribution channel expectations.

Give Debug a separate bundle identifier so development prompts and settings cannot masquerade as production state.

## Screen Recording

Preferred flow:

1. Call `CGPreflightScreenCaptureAccess()` when the user invokes capture.
2. If authorized, capture immediately.
3. If unauthorized and the app has not just requested, explain the need and call `CGRequestScreenCaptureAccess()` from an explicit user action.
4. If the user opens System Settings, observe app activation and preflight again.
5. If authorized after returning, dismiss recovery UI and continue or invite one explicit retry.
6. Never keep reopening the same permission page because an onboarding flag says permission is missing.

Do not use a real ScreenCaptureKit capture attempt merely to determine launch-time permission. It can produce prompts or failures that are harder to reason about than the dedicated preflight API.

## Accessibility and Automation

- Ask for Accessibility only when input monitoring or UI control is required.
- Keep Screen Recording, Accessibility, Input Monitoring, Microphone, and Automation as separate capabilities and states.
- Do not infer one permission from another.
- For Apple Events automation, identify the target app and include the correct usage description.
- Explain the protected action before the system prompt appears.

## Menu bar implementation

Recommended AppKit properties:

- one strongly retained `NSStatusItem`;
- creation and UI changes on the main actor/thread;
- `NSStatusItem.squareLength` for an icon-only item;
- `button.imagePosition = .imageOnly`;
- template image with accessibility description and tooltip;
- eager bitmap/vector representation that survives macOS 26 remote hosting;
- stable `autosaveName` only if persistent visibility/position is desired;
- no per-build `autosaveName` churn;
- fallback path to Settings/Quit outside the status item.

`isVisible == true` is not proof that pixels are visible. Apple documents that it can remain true while the item is temporarily hidden for insufficient space. On macOS 26, System Settings also has an application-level “Allow in the Menu Bar” control.

## Menu bar diagnostic tree

### A. Process is absent

Check crash/termination logs, login-item state, launch source, signature, Gatekeeper, and whether TestFlight actually launched the installed path.

### B. Process exists but no status item AX tree

Check initialization order, controller retention, main-thread creation, early returns, activation policy, and exceptions.

### C. Status item and menu exist, but coordinates are hidden/offscreen

Check:

1. macOS 26 Menu Bar allowance;
2. available menu-bar space and notch behavior;
3. stable autosave identity;
4. duplicate production bundle registrations;
5. stale Xcode/DerivedData/archive/Trash app paths;
6. Control Center tracking the item under another responsible application;
7. whether a helper, Terminal, the coding agent, or a Swift interpreter launched the production app.

A negative Y or a coordinate at a screen boundary is system/layout evidence, not proof that the image is missing.

### D. Item is visible geometrically but image is blank

Check template rendering, image size, bitmap/vector representation, dark/light mode, remote-host transfer, and accessibility description. Test a known SF Symbol only as a temporary diagnostic; restore the product icon after confirming the path.

### E. Only the developer Mac fails

Assume local contamination until disproven. Compare the exact same TestFlight build with an independent tester. Audit LaunchServices and Control Center before changing source code.

## Local repair boundaries

Safe first actions:

- quit only the affected app;
- back up the relevant preference/database file;
- unregister a proven stale app path;
- remove a proven cross-reference for the affected bundle only;
- restart Control Center/SystemUIServer;
- relaunch from TestFlight's visible UI;
- verify the app is tracked under its own identity.

Require explicit user approval before:

- resetting all TCC permissions;
- resetting the whole Control Center layout;
- deleting all app containers/preferences;
- emptying Trash or removing archives;
- changing the production bundle identifier/team;
- deleting user files or saved captures.

Never launch a production-ID test app from the coding agent after repairing responsible-application tracking. That can recreate the cross-association being diagnosed.

## Official references

- Apple: [Code signing designated requirements](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/AboutCS/AboutCS.html)
- Apple: [CGPreflightScreenCaptureAccess](https://developer.apple.com/documentation/coregraphics/cgpreflightscreencaptureaccess())
- Apple: [CGRequestScreenCaptureAccess](https://developer.apple.com/documentation/coregraphics/cgrequestscreencaptureaccess())
- Apple: [NSStatusItem isVisible](https://developer.apple.com/documentation/appkit/nsstatusitem/isvisible)
- Apple: [NSStatusBar](https://developer.apple.com/documentation/appkit/nsstatusbar)
- Apple Support: [Change Menu Bar settings on Mac](https://support.apple.com/guide/mac-help/change-menu-bar-settings-mchlad96d366/mac)
- Apple: [SMAppService mainApp](https://developer.apple.com/documentation/servicemanagement/smappservice/mainapp)

