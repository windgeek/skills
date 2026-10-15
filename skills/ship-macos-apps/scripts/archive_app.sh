#!/bin/sh

# Archive a macOS app from the command line, into the folder Organizer reads,
# then confirm the archive shows the build it contains.
#
#   archive_app.sh --project /abs/App.xcodeproj --scheme App
#   archive_app.sh --workspace /abs/App.xcworkspace --scheme App [--output /abs/dir]
#
# Same result as Product > Archive in Xcode, which need not be open. Signing
# uses the accounts signed in to Xcode (-allowProvisioningUpdates). Prints the
# archive path on the last line, for upload_archive.sh.

set -eu

usage() {
    echo "usage: archive_app.sh (--project App.xcodeproj | --workspace App.xcworkspace) --scheme Scheme [--configuration Release] [--output dir]" >&2
    exit 2
}

container_flag=""
container=""
scheme=""
configuration="Release"
output=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) [ "$#" -ge 2 ] || usage; container_flag=-project; container="$2"; shift 2 ;;
        --workspace) [ "$#" -ge 2 ] || usage; container_flag=-workspace; container="$2"; shift 2 ;;
        --scheme) [ "$#" -ge 2 ] || usage; scheme="$2"; shift 2 ;;
        --configuration) [ "$#" -ge 2 ] || usage; configuration="$2"; shift 2 ;;
        --output) [ "$#" -ge 2 ] || usage; output="$2"; shift 2 ;;
        *) usage ;;
    esac
done
[ -n "$container" ] && [ -n "$scheme" ] || usage

dir=${output:-"$HOME/Library/Developer/Xcode/Archives/$(date +%F)"}
mkdir -p "$dir"
archive="$dir/$scheme $(date '+%d-%m-%Y, %H.%M.%S').xcarchive"
log=$(mktemp -t archive_app).log

echo "Archiving $scheme ($configuration)… log: $log"
if ! xcodebuild archive "$container_flag" "$container" -scheme "$scheme" \
        -configuration "$configuration" -destination 'generic/platform=macOS' \
        -archivePath "$archive" -allowProvisioningUpdates > "$log" 2>&1; then
    grep -E "error:|\*\* ARCHIVE" "$log" | head -20 >&2
    echo "Archive failed. Full log: $log" >&2
    exit 1
fi

"$(dirname "$0")/check_archive_build.sh" "$archive"
echo "$archive"
