# macOS development and distribution workflow

## Contents

- Environment model
- Daily development loop
- Permission feature loop
- Release candidate loop
- TestFlight matrix
- App Review and release
- Incident response

## Environment model

Use three environments when practical:

| Environment | Identity | Launch source | Purpose |
|---|---|---|---|
| Developer account | `com.example.App.debug` | Xcode or the coding agent | Fast iteration and automated tests |
| Clean local user or VM | Production bundle ID | TestFlight | First-run, permissions, update, and contamination testing |
| Independent tester Mac | Production bundle ID | TestFlight | Real-world confirmation outside the developer environment |

Never install a production-ID Xcode build on the daily developer account merely to “see if Release works.” Archive validation and TestFlight exist for that purpose.

## Daily development loop

1. Pull or inspect the current working tree; preserve unrelated work.
2. Confirm Debug uses a unique bundle ID and visible Dev name.
3. Build Debug.
4. Run focused unit/integration tests.
5. Run the changed feature manually under Debug.
6. For privacy features, test these transitions:
   - undetermined → request → allowed;
   - undetermined → deny → recovery;
   - denied → System Settings → allowed → app activation → retry;
   - already allowed → immediate feature execution;
   - app relaunch while allowed;
   - app update while allowed, later in TestFlight.
7. Record regressions before changing unrelated UI or release settings.

## Permission feature loop

Model each protected capability explicitly:

```text
unknown/denied ── user invokes feature ──> explain/request
      │                                      │
      │ denied                               │ allowed
      ▼                                      ▼
recovery UI <── app becomes active ── preflight again ──> execute feature
```

Rules:

- The protected action, not app launch, triggers the request.
- The authoritative preflight result outranks onboarding flags.
- Opening System Settings is not success; re-preflight after returning.
- Avoid timers that repeatedly request or relaunch.
- Keep retry and cancel available.

## Release candidate loop

1. Freeze the intended scope.
2. Run the project identity audit.
3. Build and test Debug one final time.
4. Archive Release once from a clean build.
5. Inspect the archive:
   - production bundle ID and display name;
   - version/build;
   - signing team and distribution certificate;
   - App Sandbox and required entitlements;
   - usage-description keys;
   - embedded helpers/extensions and their identifiers;
   - app icon and menu bar asset.
6. Upload the same archive.
7. Wait for App Store Connect processing; verify the build displayed in TestFlight.
8. Add the build to the internal group and write explicit “What to Test” instructions.

Apple associates uploads using bundle ID and version/build, and macOS build strings must increase across releases. If Xcode manages build numbers during upload, TestFlight is the source of truth for the distributed build.

## TestFlight matrix

Run all required rows before App Review:

| Scenario | Developer Mac | Clean user/VM | Independent tester |
|---|---:|---:|---:|
| Clean install and first launch | Optional | Required | Required for first release |
| Update from previous TestFlight build | Required | Required | Required |
| Existing permission remains usable | Required | Required | Required |
| Denied permission recovery | Required | Required | Recommended |
| Menu bar icon after launch | Required | Required | Required |
| Menu bar icon after update/restart | Required | Required | Required |
| Global shortcuts | Required | Required | Required |
| Launch at login | Required | Required | Recommended |
| Core capture/save flow | Required | Required | Required |
| Settings/About/Quit reachable | Required | Required | Required |
| Crash-free repeated relaunch | Required | Required | Recommended |

For update testing:

1. Install build N through TestFlight.
2. Grant the real permissions and configure realistic preferences.
3. Capture evidence of working features.
4. Update to build N+1 using TestFlight.
5. Do not uninstall first.
6. Verify permissions, preferences, menu item, shortcuts, login item, and files.
7. Separately perform a clean install of N+1 on another user or Mac.

## App Review and release

1. Submit the exact TestFlight-approved build.
2. Provide complete review notes for permissions, shortcuts, menu bar behavior, and any non-obvious feature path.
3. Keep manual release enabled when timing matters.
4. After approval, recheck the selected build before release.
5. After release, perform a storefront install/update smoke test on a non-developer Mac.

## Incident response

When a tester reports a permission or menu bar regression:

1. Capture macOS version, hardware, app version/build, install channel, and update/clean-install history.
2. Ask whether another tester on the same build reproduces it.
3. Inspect identity and system state before changing code.
4. Avoid asking the user to repeatedly uninstall, reset all privacy permissions, or reboot without a hypothesis.
5. If local-only, repair the narrow local record and preserve a backup.
6. If reproducible across clean testers, add a code regression test and ship a new TestFlight build.

