#!/bin/bash
# Convert film scans into Kindle Paperwhite 4 frames: 1072x1448 grayscale JPEG.
#   Near-portrait shots fill the screen (center crop, at most MAX_CROP lost).
#   Everything else fits on a mat so nothing of the frame gets cut.
#   Thin or underexposed negatives get a per-image contrast stretch (STRETCH=0 turns it off).
#   Files named in tools/skip.txt (blank leader frames) are left out.
# Usage: prep-photos.sh <src_dir> <out_dir>
# Env: QUALITY=80 MAT=black MAX_CROP=0.12 STRETCH=0.5% JOBS=<ncpu> SHARPEN=0x0.6+0.5+0.02
set -euo pipefail

SRC=${1:?source dir}
OUT=${2:?output dir}
W=1072
H=1448
export W H OUT
export QUALITY=${QUALITY:-80}
export MAT=${MAT:-black}
export MAX_CROP=${MAX_CROP:-0.12}
export STRETCH=${STRETCH:-0.5%}
# radius x sigma + amount + threshold; the threshold keeps flat grain from being boosted
export SHARPEN=${SHARPEN:-0x0.6+0.5+0.02}
export SKIP="$(dirname "$0")/skip.txt"
JOBS=${JOBS:-$(sysctl -n hw.ncpu 2>/dev/null || nproc)}

mkdir -p "$OUT"

convert_one() {
  local f=$1 base out iw ih ori loss
  base=$(basename "$f")
  out="$OUT/${base%.*}.jpg"
  # keep the extension in the name for anything but .jpg, so a.JPG and a.jpeg both survive
  case "$base" in *.[jJ][pP][gG]) ;; *) out="$OUT/${base%.*}-${base##*.}.jpg" ;; esac
  [ -s "$out" ] && return 0
  [ -f "$SKIP" ] && grep -qxF "$base" "$SKIP" && return 0
  local tone=()
  [ "$STRETCH" != "0" ] && tone=("-contrast-stretch" "${STRETCH}x${STRETCH}")
  read -r iw ih ori < <(magick identify -format "%w %h %[EXIF:Orientation]\n" "$f[0]" 2>/dev/null | head -1)
  # EXIF orientations 5-8 swap width and height
  case "${ori:-1}" in 5|6|7|8) read -r iw ih <<<"$ih $iw" ;; esac
  # share of the image a cover-crop would throw away
  loss=$(awk -v w="$iw" -v h="$ih" -v W="$W" -v H="$H" 'BEGIN{
    a=w/h; t=W/H; print (a>t) ? 1-t/a : 1-a/t }')
  if awk -v l="$loss" -v m="$MAX_CROP" 'BEGIN{exit !(l<=m)}'; then
    fit=("-resize" "${W}x${H}^")
  else
    fit=("-resize" "${W}x${H}")
  fi
  magick "$f[0]" -auto-orient -grayscale Rec709Luma "${fit[@]}" \
    ${tone[@]+"${tone[@]}"} -unsharp "$SHARPEN" \
    -background "$MAT" -gravity center -extent "${W}x${H}" \
    -strip -interlace none -quality "$QUALITY" "$out.tmp.jpg" \
    && mv "$out.tmp.jpg" "$out" \
    || { echo "FAILED: $f" >&2; rm -f "$out.tmp.jpg"; }
}
export -f convert_one

find "$SRC" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.tif' -o -iname '*.tiff' \) -print0 \
  | xargs -0 -n 1 -P "$JOBS" bash -c 'convert_one "$0"'

echo "done: $(find "$OUT" -maxdepth 1 -name '*.jpg' | wc -l | tr -d ' ') frames in $OUT"
