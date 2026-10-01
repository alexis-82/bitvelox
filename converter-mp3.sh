#!/usr/bin/env bash
# Re-encode broken MP3s (e.g. files with huge zero padding or MP4 metadata
# masquerading as MP3) into clean MP3 files with libmp3lame.
#
# Usage:
#   ./converter-mp3.sh [MUSIC_DIR]
#
# Default MUSIC_DIR is ./music (relative to current directory).
# Files that convert successfully are replaced in-place. Files that fail
# are left untouched and listed at the end.

set -euo pipefail

MUSIC_DIR="${1:-./music}"
QUALITY="${QUALITY:-2}"   # libmp3lame VBR quality (0=best, 9=worst). Override: QUALITY=4 ./fix-mp3s.sh

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg not found. Install it first (e.g. apt install ffmpeg)." >&2
    exit 1
fi

if [ ! -d "$MUSIC_DIR" ]; then
    echo "Directory not found: $MUSIC_DIR" >&2
    exit 1
fi

TOTAL=$(find "$MUSIC_DIR" -type f -name '*.mp3' | wc -l)
if [ "$TOTAL" -eq 0 ]; then
    echo "No .mp3 files under $MUSIC_DIR"
    exit 0
fi

echo "Found $TOTAL .mp3 files under $MUSIC_DIR"
echo "Quality (VBR -q:a): $QUALITY"
read -r -p "Re-encode in place? Original files will be overwritten. [y/N] " ans
case "$ans" in
    y|Y|yes|YES) ;;
    *) echo "Aborted."; exit 0 ;;
esac

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

ok=0
fail=0
failed_files=()

while IFS= read -r -d '' f; do
    out="$TMPDIR/$(basename "$f")"
    if ffmpeg -nostdin -y -loglevel error -i "$f" -codec:a libmp3lame -q:a "$QUALITY" "$out" 2>/dev/null; then
        mv -- "$out" "$f"
        ok=$((ok + 1))
        printf 'OK   %s\n' "$f"
    else
        fail=$((fail + 1))
        failed_files+=("$f")
        printf 'FAIL %s\n' "$f"
        rm -f -- "$out"
    fi
done < <(find "$MUSIC_DIR" -type f -name '*.mp3' -print0)

echo
echo "Done. Re-encoded: $ok   Failed: $fail   Total: $TOTAL"

if [ "$fail" -gt 0 ]; then
    echo
    echo "Failed files (likely truly corrupt — no MP3 stream ffmpeg can decode):"
    for f in "${failed_files[@]}"; do
        echo "  $f"
    done
fi
