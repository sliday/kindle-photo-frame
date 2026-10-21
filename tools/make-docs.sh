#!/bin/bash
# Regenerate the README previews (touch sequence GIF, overlay stills) and the library cover
# from the public-domain photos in samples/, so committed images never carry private photos.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
S="$ROOT/samples"
T=$(mktemp -d)
(cd "$ROOT/filmframe" && go build -o "$T/filmframe-mac" .)
preview() { "$T/filmframe-mac" -config /dev/null -preview "$T/$1" -photo "$S/$2" -at "$3" -line "$4" -icon "$5" >/dev/null; }
preview a lange-migrant-mother.jpg 18:42 "12°C · Partly cloudy" cloud-sun
preview b delano-victory-garden.jpg 07:05 "3°C · Light snow" cloud-snow
preview c evans-allie-mae-burroughs.jpg 21:30 "18°C · Clear" moon
SZ=536x724
# e-ink flash approximated as a brief black frame before the final image
magick -size $SZ xc:black "$T/flash.png"
magick -delay 150 "$T/a/01.png" -delay 35 "$T/a/02.png" "$T/a/03.png" "$T/a/04.png" "$T/a/05.png" \
	-delay 250 "$T/a/06.png" -delay 35 "$T/a/07.png" "$T/a/08.png" -delay 12 "$T/flash.png" \
	-delay 200 "$T/a/09.png" -resize $SZ -colors 64 -layers Optimize -loop 0 "$ROOT/docs/touch-sequence.gif"
magick "$T/a/06.png" "$T/b/06.png" "$T/c/06.png" -resize 420x567 +append "$ROOT/docs/overlay-stills.png"
magick "$S/lange-migrant-mother.jpg" -resize 300x405 -gravity center -extent 300x400 -strip "$ROOT/kindle/filmframe/cover.png"
rm -r "$T"
ls -la "$ROOT/docs" "$ROOT/kindle/filmframe/cover.png"
