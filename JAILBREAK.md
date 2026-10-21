# Jailbreak: Kindle Paperwhite 4 on firmware 5.15.1.1

**Scope.** This repo contains no jailbreak or circumvention code. The jailbreak is third-party: WinterBreak2 and jb.sh by the [KindleModding](https://github.com/KindleModding) project, documented at [kindlemodding.org](https://kindlemodding.org). These notes describe how it went on one Kindle the owner bought, to run the frame app on it. Use it only on your own Kindle and check the law where you live first. Nothing here touches Kindle books, DRM or Amazon's ads.

Device: Paperwhite 10th gen (2018), serial prefix G000T6, 32 GB, firmware 5.15.1.1 (392498 005).
Method: **WinterBreak2** (kindlemodding.org wizard's first pick for PW4 up to 5.16.3). No Amazon registration and no factory reset. It needs Wi-Fi for one step.

Checked on 2026-10-20:
- `wb2.zip` v1.1.0 sha256 `9e859709…cdfdf` matches the GitHub release digest. Its `winterbreak2/dialoger.html` pipes `https://kindlemodding.org/jb.sh` into `sh`.
- The live `kindlemodding.org/jb.sh` is byte-identical to the jb.sh v2.2.1 GitHub release (sha256 `cf60f9f9…08ba`, published 2026-10-04).
- jb.sh installs the hotfix, MKK and developer keystore, FBInk at `/mnt/us/libkh/bin/fbink`, KPM, scriptlet support, and renames the OTA updaters. The legacy hotfix, renameotabin and KUAL steps don't apply.
- Scriptlets (`.sh` in `documents/`) run as root through `/var/local/mkk/su -c` (sh_integration `launcher/main.c`).

## The danger

The newest PW4 firmware, 5.18.1.1.1 (June 2026), closes this jailbreak; only SpringBreak works there and it needs registration. A Kindle that sat offline since 2023 fetches it the moment it gets Wi-Fi. The guard: fill storage until 50 to 90 MB stay free, so the update can't download. `tools/fill.sh` does that (same idea as Kindle-Filler-Disk). Never factory-reset or deregister.

## What sits on the Kindle before you start

```
/winterbreak2/dialoger.html              WinterBreak2 v1.1.0
/fill_disk/                              zero files, ~70 MB left free
/documents/Film Frame - finish setup.sh  scriptlet: checks the jailbreak, frees the filler
/documents/Film Frame.sh                 scriptlet: starts the frame
/extensions/filmframe/, /filmframe/      the frame and your photos
```

## Steps (cable stays plugged in throughout)

1. The Mac ejects the Kindle; it shows its Home screen and keeps charging. `tools/watch-jailbreak.sh` starts on the Mac.
2. **Check the firmware and space:** tap the top of the screen > **All Settings** > **Device Options** > **Device Info**. Expect version 5.15.1.1 and about 70 MB free. Anything else: stop.
3. **Join Wi-Fi:** All Settings > **Wi-Fi & Bluetooth** (or **Wireless**) > Airplane Mode off > **Wi-Fi Networks** > your network.
4. **Open the browser:** Home > **⋮** (top right) > **Experimental Browser**. If it isn't there: All Settings > Device Options > Advanced Options > Experimental Browser.
5. Tap the address bar, type the address that the [kindlemodding.org WinterBreak2 guide](https://kindlemodding.org/jailbreaking/WinterBreak2/) gives, and press Go.
6. Tap **Jailbreak**. Hands off. Text scrolls at the top, then "Restarting Kindle", then a reboot. "Application error" popups along the way are normal.
7. After the reboot the Kindle comes back as a USB drive. The watcher on the Mac checks for `documents/JAILBROKEN.txt`, deletes update files and the filler, and ejects it.
8. In the library: **JAILBROKEN**, **Film Frame - finish setup**, **Film Frame**. Tap *finish setup* once (three "ok" lines), then tap **Film Frame**.

Optional, KOReader: Home search bar `;kpm update`, Enter, then `;kpm install koreader`, Enter (needs Wi-Fi; KPM picks the soft-float `kindlepw2` build, KOReader v2026.07.x).

## If something goes wrong

- Browser page won't load: check Wi-Fi, retype the address, restart (hold power until the menu shows, tap Restart).
- Jailbreak button does nothing: restart and try again. Then follow the fallback in the kindlemodding.org WinterBreak2 guide.
- Scriptlets missing from the library after the reboot: restart the Kindle once so it rescans `documents/`.
- Frame unresponsive: hold power about 40 s. The Kindle restarts into the stock UI; nothing starts the frame on its own.

Sources: kindlemodding.org (jailbreak wizard data, /jailbreaking/WinterBreak2/, /jailbreaking/prevent-auto-update/, /kindle-dev/scriptlets.html), github.com/KindleModding (Winterbreak2, jb.sh, sh_integration), github.com/koreader/koreader wiki.
