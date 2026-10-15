#!/bin/sh

# Upload an archive to App Store Connect, as Organizer's Distribute App does.
#
#   upload_archive.sh /abs/App.xcarchive            # print what would go up; uploads nothing
#   upload_archive.sh /abs/App.xcarchive --confirm  # upload it
#
# An upload cannot be taken back: once Apple has the build, that build number
# is spent. So the default is a summary for a person to approve, and only
# --confirm uploads. The team is read from the archive's signature; signing
# for distribution uses the accounts signed in to Xcode.

set -eu

usage() {
    echo "usage: upload_archive.sh App.xcarchive [--confirm]" >&2
    exit 2
}

archive=""
confirm=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --confirm) confirm=1; shift ;;
        -*) usage ;;
        *) [ -z "$archive" ] || usage; archive="$1"; shift ;;
    esac
done
[ -n "$archive" ] && [ -d "$archive" ] || usage

app=$(ls -d "$archive"/Products/Applications/*.app 2>/dev/null | head -1)
[ -n "$app" ] || { echo "No app inside $archive" >&2; exit 1; }

plist="$app/Contents/Info.plist"
version=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$plist")
build=$(/usr/libexec/PlistBuddy -c "Print :CFBundleVersion" "$plist")
bundle_id=$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$plist")
name=$(/usr/libexec/PlistBuddy -c "Print :CFBundleDisplayName" "$plist" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Print :CFBundleName" "$plist")
team=$(codesign -dvv "$app" 2>&1 | sed -n 's/^TeamIdentifier=//p')
archs=$(lipo -archs "$app/Contents/MacOS/$(/usr/libexec/PlistBuddy -c "Print :CFBundleExecutable" "$plist")")

echo "Archive:      $archive"
echo "App:          $name $version ($build)"
echo "Bundle ID:    $bundle_id"
echo "Team:         $team"
echo "Architectures: $archs"
echo "Entitlements:"
codesign -d --entitlements - --xml "$app" 2>/dev/null | plutil -p - 2>/dev/null | sed 's/^/  /' || echo "  (none)"

"$(dirname "$0")/check_archive_build.sh" "$archive" > /dev/null \
    || { echo "Archive metadata disagrees with the app; re-archive before uploading." >&2; exit 1; }

case "$bundle_id" in
    *.debug|*.dev) echo "Refusing to upload a development bundle ID: $bundle_id" >&2; exit 1 ;;
esac
[ -n "$team" ] && [ "$team" != "not set" ] || { echo "The archive is not signed by a team." >&2; exit 1; }

if [ "$confirm" -ne 1 ]; then
    echo
    echo "Nothing uploaded. Run again with --confirm to upload $version ($build)."
    exit 0
fi

work=$(mktemp -d -t upload_archive)
cat > "$work/ExportOptions.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key><string>app-store-connect</string>
    <key>destination</key><string>upload</string>
    <key>teamID</key><string>$team</string>
    <key>signingStyle</key><string>automatic</string>
    <key>manageAppVersionAndBuildNumber</key><false/>
    <key>uploadSymbols</key><true/>
</dict>
</plist>
EOF

echo
echo "Uploading $version ($build)… log: $work/upload.log"
if xcodebuild -exportArchive -archivePath "$archive" \
        -exportOptionsPlist "$work/ExportOptions.plist" -exportPath "$work/export" \
        -allowProvisioningUpdates > "$work/upload.log" 2>&1 \
   && grep -q "Upload succeeded" "$work/upload.log"; then
    echo "Upload succeeded: $name $version ($build). App Store Connect processes it before it appears in TestFlight."
else
    grep -E "error|Error|failed" "$work/upload.log" | tail -15 >&2
    echo "Upload failed. Full log: $work/upload.log" >&2
    exit 1
fi
