#!/bin/bash
# Fill a mounted Kindle with zero files until only TARGET_MB stay free, so an OTA update
# can't download (kindlemodding "prevent auto update": leave 50-90 MB). Same idea as
# Kindle-Filler-Disk's Filler.sh. Undo by deleting <kindle>/fill_disk.
# Usage: fill.sh [/Volumes/Kindle] [target_mb=70]
set -euo pipefail
K=${1:-/Volumes/Kindle}
TARGET=${2:-70}
[ -d "$K/system" ] || { echo "no Kindle at $K" >&2; exit 1; }
D="$K/fill_disk"
mkdir -p "$D"
free_mb() { df -m "$K" | awk 'NR==2{print $4}'; }
n=$(ls "$D" | wc -l | tr -d ' ')
for chunk in 2048 512 128 32 8 2; do
	while [ $(( $(free_mb) - chunk )) -ge "$TARGET" ]; do
		n=$((n + 1))
		t=$(date +%s)
		dd if=/dev/zero of="$D/fill_$n.bin" bs=1m count=$chunk 2>/dev/null
		echo "fill_$n.bin ${chunk} MB in $(( $(date +%s) - t ))s, free $(free_mb) MB"
	done
done
dot_clean -m "$D" 2>/dev/null || true
sync
echo "done: $(free_mb) MB free on $K"
