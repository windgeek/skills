#!/bin/sh

set -eu

usage() {
    echo "usage: audit_project.sh (--project App.xcodeproj | --workspace App.xcworkspace) --scheme Scheme --debug-id ID --release-id ID" >&2
    exit 2
}

container_kind=""
container_path=""
scheme=""
debug_id_expected=""
release_id_expected=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --project)
            [ "$#" -ge 2 ] || usage
            container_kind="-project"
            container_path="$2"
            shift 2
            ;;
        --workspace)
            [ "$#" -ge 2 ] || usage
            container_kind="-workspace"
            container_path="$2"
            shift 2
            ;;
        --scheme)
            [ "$#" -ge 2 ] || usage
            scheme="$2"
            shift 2
            ;;
        --debug-id)
            [ "$#" -ge 2 ] || usage
            debug_id_expected="$2"
            shift 2
            ;;
        --release-id)
            [ "$#" -ge 2 ] || usage
            release_id_expected="$2"
            shift 2
            ;;
        *) usage ;;
    esac
done

[ -n "$container_kind" ] && [ -n "$container_path" ] && [ -n "$scheme" ] || usage
[ -n "$debug_id_expected" ] && [ -n "$release_id_expected" ] || usage
[ -e "$container_path" ] || { echo "error: project/workspace not found: $container_path" >&2; exit 2; }

debug_settings=$(xcodebuild "$container_kind" "$container_path" -scheme "$scheme" -configuration Debug -showBuildSettings 2>/dev/null)
release_settings=$(xcodebuild "$container_kind" "$container_path" -scheme "$scheme" -configuration Release -showBuildSettings 2>/dev/null)

setting() {
    key="$1"
    awk -F ' = ' -v key="$key" '$1 ~ "^[[:space:]]*" key "$" { print $2; exit }'
}

debug_id=$(printf '%s\n' "$debug_settings" | setting PRODUCT_BUNDLE_IDENTIFIER)
release_id=$(printf '%s\n' "$release_settings" | setting PRODUCT_BUNDLE_IDENTIFIER)
debug_team=$(printf '%s\n' "$debug_settings" | setting DEVELOPMENT_TEAM)
release_team=$(printf '%s\n' "$release_settings" | setting DEVELOPMENT_TEAM)
debug_name=$(printf '%s\n' "$debug_settings" | setting APP_DISPLAY_NAME)
release_name=$(printf '%s\n' "$release_settings" | setting APP_DISPLAY_NAME)
version=$(printf '%s\n' "$release_settings" | setting MARKETING_VERSION)
build=$(printf '%s\n' "$release_settings" | setting CURRENT_PROJECT_VERSION)
deployment=$(printf '%s\n' "$release_settings" | setting MACOSX_DEPLOYMENT_TARGET)
entitlements=$(printf '%s\n' "$release_settings" | setting CODE_SIGN_ENTITLEMENTS)

printf '%-20s %-34s %-34s\n' 'SETTING' 'DEBUG' 'RELEASE'
printf '%-20s %-34s %-34s\n' 'Bundle ID' "$debug_id" "$release_id"
printf '%-20s %-34s %-34s\n' 'Display name' "${debug_name:-<unset>}" "${release_name:-<unset>}"
printf '%-20s %-34s %-34s\n' 'Team' "$debug_team" "$release_team"
printf '%-20s %-34s %-34s\n' 'Version/build' '-' "${version:-?} (${build:-?})"
printf '%-20s %-34s %-34s\n' 'Deployment target' '-' "${deployment:-?}"
printf '%-20s %-34s %-34s\n' 'Entitlements' '-' "${entitlements:-<unset>}"

failures=0
warn() { echo "warning: $1" >&2; }
fail() { echo "error: $1" >&2; failures=$((failures + 1)); }

[ "$debug_id" = "$debug_id_expected" ] || fail "Debug bundle ID is '$debug_id', expected '$debug_id_expected'."
[ "$release_id" = "$release_id_expected" ] || fail "Release bundle ID is '$release_id', expected '$release_id_expected'."
[ "$debug_id" != "$release_id" ] || fail "Debug and Release reuse the same bundle ID."
[ -n "$debug_team" ] || fail "Debug DEVELOPMENT_TEAM is empty."
[ "$debug_team" = "$release_team" ] || fail "Debug and Release use different teams ('$debug_team' vs '$release_team')."
[ -n "$build" ] || fail "Release build number is empty."
[ -n "$version" ] || fail "Release marketing version is empty."
[ -n "$entitlements" ] || warn "Release CODE_SIGN_ENTITLEMENTS is empty; verify this is intentional."
if [ -n "$debug_name" ] && [ -n "$release_name" ] && [ "$debug_name" = "$release_name" ]; then
    warn "Debug and Release display names are identical; use a visible Dev name."
fi

if [ "$failures" -ne 0 ]; then
    echo "FAIL: $failures identity/configuration problem(s)." >&2
    exit 1
fi

echo "PASS: Debug and Release identities are separated."
