#!/bin/sh

# Compare the build number Organizer shows for an archive with the one inside
# the archived app. They can disagree when the build number was changed in
# Xcode's Build field just before archiving: the app is right, the archive
# metadata is stale.
#
#   check_archive_build.sh                       # newest archive
#   check_archive_build.sh /path/App.xcarchive   # a given one

set -eu

archive=${1:-}
if [ -z "$archive" ]; then
    archive=$(ls -td "$HOME"/Library/Developer/Xcode/Archives/*/*.xcarchive 2>/dev/null | head -1)
    [ -n "$archive" ] || { echo "No archives found." >&2; exit 1; }
fi
[ -d "$archive" ] || { echo "Not an archive: $archive" >&2; exit 1; }

app=$(ls -d "$archive"/Products/Applications/*.app 2>/dev/null | head -1)
[ -n "$app" ] || { echo "No app inside $archive" >&2; exit 1; }

shown_version=$(/usr/libexec/PlistBuddy -c "Print :ApplicationProperties:CFBundleShortVersionString" "$archive/Info.plist")
shown_build=$(/usr/libexec/PlistBuddy -c "Print :ApplicationProperties:CFBundleVersion" "$archive/Info.plist")
real_version=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$app/Contents/Info.plist")
real_build=$(/usr/libexec/PlistBuddy -c "Print :CFBundleVersion" "$app/Contents/Info.plist")

echo "Archive:   $archive"
echo "Organizer: $shown_version ($shown_build)"
echo "App:       $real_version ($real_build)"

if [ "$shown_version" = "$real_version" ] && [ "$shown_build" = "$real_build" ]; then
    echo "OK"
else
    echo "MISMATCH: archive metadata is stale. Re-archive, or fix the listing with:"
    echo "  /usr/libexec/PlistBuddy -c \"Set :ApplicationProperties:CFBundleVersion $real_build\" \"$archive/Info.plist\""
    exit 1
fi
