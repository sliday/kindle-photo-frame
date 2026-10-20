#!/bin/bash
# Copy Film Frame onto a mounted, jailbroken Kindle.
# Usage: install.sh [/Volumes/Kindle] [photos_dir]
#   Keeps an existing filmframe.conf. Photos are added; nothing on the Kindle gets deleted.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
K=${1:-/Volumes/Kindle}
PHOTOS=${2:-}

[ -d "$K/documents" ] && [ -d "$K/system" ] || { echo "no Kindle mounted at $K" >&2; exit 1; }
[ -x "$ROOT/dist/filmframe" ] || "$ROOT/tools/build.sh"

EXT="$K/extensions/filmframe"
mkdir -p "$EXT/bin" "$K/filmframe/photos"
# -X: no extended attributes, so macOS doesn't litter the FAT drive with ._ files
cp -X "$ROOT/kindle/extensions/filmframe/config.xml" "$ROOT/kindle/extensions/filmframe/menu.json" "$EXT/"
cp -X "$ROOT"/kindle/extensions/filmframe/bin/*.sh "$ROOT/dist/filmframe" "$EXT/bin/"
# scriptlets: after the jailbreak, .sh files in documents/ show up as tappable books
cp -X "$ROOT"/kindle/documents/*.sh "$K/documents/"
cp -X "$ROOT/kindle/filmframe/cover.png" "$K/filmframe/"
if [ -f "$K/filmframe/filmframe.conf" ]; then
	echo "kept existing $K/filmframe/filmframe.conf"
else
	cp -X "$ROOT/kindle/filmframe/filmframe.conf" "$K/filmframe/"
fi

if [ -n "$PHOTOS" ]; then
	n=0
	for f in "$PHOTOS"/*.jpg "$PHOTOS"/*.jpeg "$PHOTOS"/*.png; do
		[ -f "$f" ] || continue
		dst="$K/filmframe/photos/$(basename "$f")"
		if [ ! -f "$dst" ] || [ "$(stat -f %z "$f")" != "$(stat -f %z "$dst")" ]; then
			cp -X "$f" "$dst"
			n=$((n + 1))
		fi
	done
	echo "copied $n new photos; $(ls "$K/filmframe/photos" | wc -l | tr -d ' ') on the Kindle"
fi
dot_clean -m "$K/extensions/filmframe" "$K/filmframe" "$K/documents" 2>/dev/null || true
sync
echo "installed. Eject the Kindle, then tap Film Frame in the library."
