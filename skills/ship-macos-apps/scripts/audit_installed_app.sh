#!/bin/sh

set -eu

app=${1:-}
[ -n "$app" ] || { echo "usage: audit_installed_app.sh /absolute/App.app" >&2; exit 2; }
[ -d "$app" ] || { echo "error: app not found: $app" >&2; exit 2; }

case "$app" in
    /*) ;;
    *) echo "error: use an absolute app path" >&2; exit 2 ;;
esac

plist="$app/Contents/Info.plist"
[ -f "$plist" ] || { echo "error: Info.plist not found" >&2; exit 2; }

read_key() {
    /usr/libexec/PlistBuddy -c "Print :$1" "$plist" 2>/dev/null || true
}

bundle_id=$(read_key CFBundleIdentifier)
display_name=$(read_key CFBundleDisplayName)
[ -n "$display_name" ] || display_name=$(read_key CFBundleName)
version=$(read_key CFBundleShortVersionString)
build=$(read_key CFBundleVersion)
executable=$(read_key CFBundleExecutable)
lsuielement=$(read_key LSUIElement)

echo "App:          $app"
echo "Bundle ID:    $bundle_id"
echo "Name:         $display_name"
echo "Version:      $version ($build)"
echo "Executable:   $executable"
echo "LSUIElement:  ${lsuielement:-false}"

signature=$(codesign -dv --verbose=4 "$app" 2>&1)
team=$(printf '%s\n' "$signature" | awk -F= '/^TeamIdentifier=/{print $2; exit}')
authority=$(printf '%s\n' "$signature" | awk -F= '/^Authority=/{print $2; exit}')
echo "Team:         ${team:-<none>}"
echo "Authority:    ${authority:-<none>}"

codesign --verify --deep --strict "$app"
echo "Code signing: PASS"

if spctl --assess --type execute "$app" >/dev/null 2>&1; then
    echo "Gatekeeper:   PASS"
else
    echo "Gatekeeper:   WARNING (assessment failed)" >&2
fi

entitlements=$(codesign -d --entitlements :- "$app" 2>/dev/null || true)
if printf '%s\n' "$entitlements" | grep -q 'com.apple.security.app-sandbox'; then
    echo "App Sandbox:  present"
else
    echo "App Sandbox:  absent"
fi
if printf '%s\n' "$entitlements" | grep -q '<key>com.apple.security.get-task-allow</key>.*' ; then
    echo "Get task allow: inspect entitlements (development capability may be present)"
fi

lsregister='/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister'
escaped_id=$(printf '%s' "$bundle_id" | sed 's/[][\\.^$*+?{}|()]/\\&/g')
matches=$("$lsregister" -dump | grep -E -B 12 -A 18 "identifier:[[:space:]]+$escaped_id\$" || true)
paths=$(printf '%s\n' "$matches" | awk -F':  +' '/^path:/{print $2}' | sort -u)
path_count=$(printf '%s\n' "$paths" | awk 'NF{count++} END{print count+0}')

echo "LaunchServices registrations ($path_count):"
if [ "$path_count" -eq 0 ]; then
    echo "  <none>"
else
    printf '%s\n' "$paths" | sed 's/^/  /'
fi

if [ "$path_count" -gt 1 ]; then
    echo "warning: duplicate bundle registrations can redirect TestFlight launches and corrupt menu-bar identity." >&2
fi

echo "Running matching executable paths:"
running=$(ps -axo pid=,command= | grep -F "/Contents/MacOS/$executable" | grep -v grep || true)
if [ -n "$running" ]; then
    printf '%s\n' "$running" | sed 's/^/  /'
else
    echo "  <none>"
fi

echo "Audit complete (read-only)."
