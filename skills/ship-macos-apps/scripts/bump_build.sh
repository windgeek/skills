#!/bin/sh

# Raise an Xcode project's build number (CURRENT_PROJECT_VERSION) in the
# project file itself, before archiving.
#
#   bump_build.sh --project /abs/App.xcodeproj          # N -> N+1
#   bump_build.sh --project /abs/App.xcodeproj 45       # -> 45
#
# Why not Xcode's General > Build field: a value typed there can reach the
# archived app while the archive's own metadata keeps the old number, so
# Organizer lists build 39 as 38. Editing project.pbxproj avoids that, and
# Xcode reloads the file when it changes on disk.
#
# The app's build number is taken to be the highest integer
# CURRENT_PROJECT_VERSION in the project. Every configuration holding that
# value is changed, so the app and its extensions stay in step; test targets,
# which usually carry an older number, are left alone. The script prints what
# it changed so the assumption can be checked.

set -eu

usage() {
    echo "usage: bump_build.sh --project App.xcodeproj [build]" >&2
    exit 2
}

project=""
target_build=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) [ "$#" -ge 2 ] || usage; project="$2"; shift 2 ;;
        -h|--help) usage ;;
        *) [ -z "$target_build" ] || usage; target_build="$1"; shift ;;
    esac
done
[ -n "$project" ] || usage

pbxproj="$project/project.pbxproj"
[ -f "$pbxproj" ] || { echo "Not found: $pbxproj" >&2; exit 1; }

values=$(sed -n 's/.*CURRENT_PROJECT_VERSION = \([^;]*\);.*/\1/p' "$pbxproj" | tr -d '"' | sort -u)
[ -n "$values" ] || { echo "No CURRENT_PROJECT_VERSION in $pbxproj. Set the build number once in Xcode first." >&2; exit 1; }

current=""
for v in $values; do
    case "$v" in
        ''|*[!0-9]*) echo "Skipping non-integer build value: $v" >&2 ;;
        *) if [ -z "$current" ] || [ "$v" -gt "$current" ]; then current=$v; fi ;;
    esac
done
[ -n "$current" ] || { echo "No integer build number found." >&2; exit 1; }

next=${target_build:-$((current + 1))}
case "$next" in
    ''|*[!0-9]*) echo "Build number must be a whole number: $next" >&2; exit 1 ;;
esac
[ "$next" -gt "$current" ] || echo "warning: $next is not greater than $current; App Store Connect rejects a build that does not increase." >&2

count=$(grep -c "CURRENT_PROJECT_VERSION = \"\{0,1\}$current\"\{0,1\};" "$pbxproj")
sed -i '' "s/CURRENT_PROJECT_VERSION = \"\{0,1\}$current\"\{0,1\};/CURRENT_PROJECT_VERSION = $next;/" "$pbxproj"
echo "Build $current -> $next ($count configurations)"

others=$(sed -n 's/.*CURRENT_PROJECT_VERSION = \([^;]*\);.*/\1/p' "$pbxproj" | tr -d '"' | sort -u | grep -vx "$next" || true)
[ -z "$others" ] || echo "Left unchanged (other targets): $(echo $others)"

# A hard-coded CFBundleVersion ignores the build setting entirely.
root=$(dirname "$project")
for plist in $(sed -n 's/.*INFOPLIST_FILE = \([^;]*\);.*/\1/p' "$pbxproj" | tr -d '"' | sort -u); do
    path="$root/$(echo "$plist" | sed 's/\$(SRCROOT)\///')"
    [ -f "$path" ] || continue
    value=$(/usr/libexec/PlistBuddy -c "Print :CFBundleVersion" "$path" 2>/dev/null || true)
    case "$value" in
        ''|*'$('*) ;;
        *) echo "warning: $plist hard-codes CFBundleVersion = $value; use \$(CURRENT_PROJECT_VERSION)." >&2 ;;
    esac
done
