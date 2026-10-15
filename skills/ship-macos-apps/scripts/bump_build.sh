#!/bin/sh

# Raise an Xcode project's build number (CURRENT_PROJECT_VERSION), and
# optionally set its version (MARKETING_VERSION), in the project file itself
# before archiving.
#
#   bump_build.sh --project /abs/App.xcodeproj                  # build N -> N+1
#   bump_build.sh --project /abs/App.xcodeproj 45               # build -> 45
#   bump_build.sh --project /abs/App.xcodeproj --version 2.1    # version -> 2.1, build N -> N+1
#   bump_build.sh --project /abs/App.xcodeproj --version 2.1 45
#   bump_build.sh --project /abs/App.xcodeproj --version minor  # 2.0 -> 2.1
#   (also patch: 2.0 -> 2.0.1, major: 2.0 -> 3.0)
#
# One call per archive: a new version is a new upload, and macOS build strings
# must keep increasing across versions, so --version raises the build too.
#
# Why not Xcode's General tab: a value typed there can reach the archived app
# while the archive's own metadata keeps the old number, so Organizer lists
# build 39 as 38. Editing project.pbxproj avoids that, and Xcode reloads the
# file when it changes on disk.
#
# The app's build number is taken to be the highest integer
# CURRENT_PROJECT_VERSION in the project. Every build configuration holding
# that value is changed, so the app and its extensions stay in step; test
# targets, which usually carry an older number, are left alone. The script
# prints what it changed so the assumption can be checked.

set -eu

usage() {
    echo "usage: bump_build.sh --project App.xcodeproj [--version X.Y[.Z]|major|minor|patch] [build]" >&2
    exit 2
}

project=""
target_build=""
target_version=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) [ "$#" -ge 2 ] || usage; project="$2"; shift 2 ;;
        --version) [ "$#" -ge 2 ] || usage; target_version="$2"; shift 2 ;;
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

# The version the app's configurations hold now, for --version major/minor/patch.
current_version() {
    awk -v cur="$current" '
        /buildSettings = \{/ { inblock = 1; build = ""; ver = "" }
        inblock && /CURRENT_PROJECT_VERSION = / { build = $0; sub(/.*= /, "", build); sub(/;.*/, "", build); gsub(/"/, "", build) }
        inblock && /MARKETING_VERSION = / { ver = $0; sub(/.*= /, "", ver); sub(/;.*/, "", ver); gsub(/"/, "", ver) }
        inblock && /^[[:space:]]*};[[:space:]]*$/ { if (build == cur && ver != "") print ver; inblock = 0 }
    ' "$pbxproj" | sort -u
}

case "$target_version" in
    major|minor|patch)
        old=$(current_version)
        [ -n "$old" ] || { echo "The app has no MARKETING_VERSION yet; give one, e.g. --version 1.0." >&2; exit 1; }
        [ "$(echo "$old" | wc -l | tr -d ' ')" -eq 1 ] \
            || { echo "The app's configurations disagree on the version ($(echo $old)); give it explicitly." >&2; exit 1; }
        echo "$old" | grep -Eq '^[0-9]+(\.[0-9]+){0,2}$' \
            || { echo "Cannot increment version '$old'; give it explicitly." >&2; exit 1; }
        IFS=. read -r v_major v_minor v_patch <<EOF2
$old
EOF2
        v_minor=${v_minor:-0}; v_patch=${v_patch:-0}
        case "$target_version" in
            major) target_version="$((v_major + 1)).0" ;;
            minor) target_version="$v_major.$((v_minor + 1))" ;;
            patch) target_version="$v_major.$v_minor.$((v_patch + 1))" ;;
        esac
        ;;
esac

if [ -n "$target_version" ]; then
    # App Store Connect accepts up to three period-separated integers.
    echo "$target_version" | grep -Eq '^[0-9]+(\.[0-9]+){0,2}$' \
        || { echo "Version must look like 2, 2.1 or 2.1.3, or be major, minor or patch: $target_version" >&2; exit 1; }
fi

# Rewrite only the buildSettings blocks that hold the app's current build.
tmp=$(mktemp)
awk -v cur="$current" -v next_build="$next" -v ver="$target_version" '
    function flush(   i, line) {
        for (i = 1; i <= n; i++) {
            line = buf[i]
            if (hit) {
                if (line ~ /CURRENT_PROJECT_VERSION = /) sub(/= [^;]*;/, "= " next_build ";", line)
                if (ver != "" && line ~ /MARKETING_VERSION = /) {
                    old = line; sub(/.*MARKETING_VERSION = /, "", old); sub(/;.*/, "", old); gsub(/"/, "", old)
                    olds[old] = 1
                    sub(/= [^;]*;/, "= " ver ";", line)
                    versions++
                }
            }
            print line
        }
        if (hit) configs++
        n = 0; hit = 0; inblock = 0
    }
    /buildSettings = \{/ { inblock = 1 }
    inblock {
        buf[++n] = $0
        if ($0 ~ /CURRENT_PROJECT_VERSION = /) {
            v = $0; sub(/.*= /, "", v); sub(/;.*/, "", v); gsub(/"/, "", v)
            if (v == cur) hit = 1
        }
        if ($0 ~ /^[[:space:]]*};[[:space:]]*$/) flush()
        next
    }
    { print }
    END {
        if (inblock) flush()
        list = ""; for (o in olds) list = list (list == "" ? "" : ", ") o
        printf "%d %d %s\n", configs, versions, list > "/dev/stderr"
    }
' "$pbxproj" > "$tmp" 2> "$tmp.report"
read -r configs versions old_versions < "$tmp.report" || true
rm -f "$tmp.report"

if [ "${configs:-0}" -eq 0 ]; then
    rm -f "$tmp"
    echo "No build configuration holds build $current; nothing changed." >&2
    exit 1
fi
if [ -n "$target_version" ] && [ "${versions:-0}" -eq 0 ]; then
    rm -f "$tmp"
    echo "The configurations with build $current have no MARKETING_VERSION; set the version once in Xcode first. Nothing changed." >&2
    exit 1
fi
cat "$tmp" > "$pbxproj"
rm -f "$tmp"

echo "Build $current -> $next ($configs configurations)"
[ -z "$target_version" ] || echo "Version ${old_versions:-?} -> $target_version ($versions configurations)"

others=$(sed -n 's/.*CURRENT_PROJECT_VERSION = \([^;]*\);.*/\1/p' "$pbxproj" | tr -d '"' | sort -u | grep -vx "$next" || true)
[ -z "$others" ] || echo "Left unchanged (other targets): build $(echo $others)"

# A hard-coded value in Info.plist ignores the build settings entirely.
root=$(dirname "$project")
for plist in $(sed -n 's/.*INFOPLIST_FILE = \([^;]*\);.*/\1/p' "$pbxproj" | tr -d '"' | sort -u); do
    path="$root/$(echo "$plist" | sed 's/\$(SRCROOT)\///')"
    [ -f "$path" ] || continue
    for key in CFBundleVersion CFBundleShortVersionString; do
        value=$(/usr/libexec/PlistBuddy -c "Print :$key" "$path" 2>/dev/null || true)
        case "$value" in
            ''|*'$('*) ;;
            *) echo "warning: $plist hard-codes $key = $value; use \$(CURRENT_PROJECT_VERSION) / \$(MARKETING_VERSION)." >&2 ;;
        esac
    done
done
