# Film Frame

A Kindle Paperwhite 4 (10th gen, 2018) as an e-ink frame for film scans. The screen shows a bare photograph. Tap it and a clock with the weather fades in over a dark band at the top, holds for six seconds, then fades out; a flashing full refresh clears the ghosting and the bare photo returns. Nothing moves until you touch it or the next photo is due.

![touch sequence](docs/touch-sequence.gif)

![overlay on three photos](docs/overlay-stills.png)

## Using it

| Gesture | Effect |
|---|---|
| Tap | show the clock and weather; tap again to hide early |
| Swipe left / right | next / previous photo |
| Power button | same as a tap |
| Hold a finger still for 3 s | leave the frame, back to the Kindle Home screen |

Photos change every 30 minutes in shuffle order: each one once, in random order, then a new shuffle. The position survives restarts. Set `order = random` or `order = name` in the config to change that.

Start it from KUAL > Film Frame > Start frame. If the screen ever stops reacting, hold the power button for about 40 seconds: the Kindle restarts into its normal UI, because the frame never starts on its own.

## Files on the Kindle

```
/mnt/us/extensions/filmframe/   KUAL menu, bin/filmframe, bin/run.sh
/mnt/us/filmframe/filmframe.conf settings (edit over USB)
/mnt/us/filmframe/photos/       the frames
/mnt/us/filmframe/state/        playlist position, last weather
/mnt/us/filmframe/filmframe.log what happened, with battery level per photo
```

## Setup

You need a jailbroken Kindle with KUAL; the hotfix puts FBInk at `/mnt/us/libkh/bin/fbink`, which the frame finds on its own. See [JAILBREAK.md](JAILBREAK.md) for that part.

```sh
# 1. turn scans into 1072x1448 grayscale JPEGs (q80, light sharpening)
tools/prep-photos.sh ~/Downloads/film-scans ~/Downloads/film-photos-kindle
# 2. build and copy onto the mounted Kindle
tools/install.sh /Volumes/Kindle ~/Downloads/film-photos-kindle
```

`prep-photos.sh` fills the screen with portrait shots (a centre crop loses at most 12%) and puts landscape shots on a black mat. It stretches contrast per image, which rescues thin negatives (`STRETCH=0` turns that off), and leaves out the frames listed in `tools/skip.txt`. Environment knobs: `QUALITY`, `MAT`, `MAX_CROP`, `SHARPEN`, `JOBS`.

To see the touch sequence without a Kindle:

```sh
cd filmframe && go run . -config /dev/null -preview /tmp/pv -photo ~/Downloads/film-photos-kindle/000001.jpg
```

## Settings

`filmframe.conf` documents every key. The ones you are likely to touch: `photo_minutes`, `order`, `hold_seconds`, `latitude`/`longitude`/`timezone` (example: London; set your own), `units`, `clock = 12h`, `frontlight`.

## Battery

The panel draws power only while it changes, but the Kindle stays awake to catch taps. Wi-Fi comes on only for the half-hourly weather fetch (`wifi_power_save = true`). Expect days on battery rather than weeks; the log records the battery level at each photo change so you can measure it. For a frame that never needs charging, leave it on a USB charger.

## How it works

`filmframe` is one static Go binary. `run.sh` pauses the stock UI the way KOReader does on firmware 5.x (pillow off, `awesome` and `volumd` frozen, a few services stopped, including the OTA updater) and restores all of it when the frame exits. The binary grabs the touchscreen exclusively, composites the overlay in memory, and dithers it to the panel's 16 gray levels with an ordered 8x8 pattern. The pattern depends only on pixel position, so pixels that did not change dither identically and each partial update leaves no seam. Only the changed rectangle goes to FBInk: the fade steps cover the top 585 rows, the rule steps a 2-pixel strip. Weather comes from Open-Meteo (no key); the server's Date header also corrects a drifted Kindle clock.

## Licenses

Inter typeface: SIL Open Font License (`filmframe/assets/Inter-LICENSE.txt`). Weather icons: Lucide, ISC.
