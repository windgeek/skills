# macOS release gates

Stop upload or release when a required item fails.

## Identity gate

- Debug and Release bundle identifiers differ.
- Release bundle identifier matches App Store Connect exactly.
- Team ID is the intended production team.
- Display name and app icon identify Debug visibly.
- Helpers/extensions use stable, correct identifiers.
- No production bundle ID appears in temporary, DerivedData, archive-install, or Trash registrations on the test Mac.

## Build gate

- Marketing version is intentional.
- macOS build string is greater than every previously uploaded build string.
- Release builds with the intended SDK and deployment target.
- Archive succeeds from a clean build.
- No build errors or unexplained signing warnings.
- The uploaded TestFlight build number matches the intended archive.

## Signing and entitlement gate

- Code signature verifies.
- Distribution method is correct: Mac App Store/TestFlight or Developer ID.
- App Sandbox is enabled for Mac App Store distribution.
- Hardened Runtime is configured when required.
- Entitlements are minimal and match provisioning profiles.
- Nested code is signed and sealed correctly.
- Usage-description keys exist for every protected capability used.

## Permission gate

- No permission request loop.
- Already-authorized users go directly to the feature.
- Denial leaves the app usable and recoverable.
- Returning from System Settings triggers a fresh preflight.
- Update preserves working permission behavior.
- Debug permission state is not used as Release evidence.

## Menu bar gate

- Product icon renders in light and dark menu bars.
- Icon appears after clean install, update, app relaunch, and Mac restart.
- Menu actions work.
- Settings and Quit remain reachable if the status item is system-hidden.
- macOS 26 “Allow in the Menu Bar” behavior is documented or recoverable.
- Independent TestFlight tester confirms the same build.

## Functional gate

- Core workflow completes with realistic data.
- Global shortcuts work and do not conflict silently.
- Save paths and sandbox bookmarks survive relaunch/update.
- Launch at login uses `SMAppService` and reflects user/system state.
- Localization, About, Help, feedback, and privacy copy are accurate.
- No known crash or data-loss regression remains.

## TestFlight gate

- Internal group receives the intended build.
- “What to Test” names the changed and risky paths.
- Clean-install and update matrices pass.
- At least one tester is outside the developer environment.
- Session/crash/feedback data has been reviewed.
- Exact validated build is selected for App Review.

## Release evidence

Record:

- source commit or snapshot;
- archive date/identifier;
- version and build;
- Xcode and macOS SDK versions;
- team and distribution channel;
- TestFlight testers/environments;
- clean-install result;
- update result;
- permission and menu-bar result;
- known limitations and release decision.

