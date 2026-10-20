#!/bin/bash
# Run right after ejecting the Kindle for the WinterBreak2 step. The jailbreak ends with a reboot;
# with the cable still in, the Kindle comes back as a USB drive. This script waits for that,
# checks the jailbreak, removes update files and then the filler (kindlemodding order),
# and ejects again so the Kindle returns to its Home screen. Nobody touches the cable.
# Usage: watch-jailbreak.sh [/Volumes/Kindle] [timeout_minutes=120]
K=${1:-/Volumes/Kindle}
LIMIT=$(( ${2:-120} * 60 ))
start=$(date +%s)
echo "$(date '+%H:%M:%S') waiting for the Kindle to come back at $K"
while [ ! -d "$K/documents" ]; do
	if [ $(( $(date +%s) - start )) -ge "$LIMIT" ]; then
		echo "gave up after ${2:-120} minutes; the Kindle never remounted"
		exit 2
	fi
	sleep 5
done
sleep 10 # let the mount settle
echo "$(date '+%H:%M:%S') Kindle mounted"
cat "$K/system/version.txt" 2>/dev/null
jb=no
[ -f "$K/documents/JAILBROKEN.txt" ] && jb=yes
echo "JAILBROKEN.txt: $jb"
[ -f "$K/documents/JAILBROKEN.txt" ] && sed 's/^/  | /' "$K/documents/JAILBROKEN.txt"
echo "libkh/bin/fbink: $([ -f "$K/libkh/bin/fbink" ] && echo yes || echo no)"
ls "$K"/update*.bin "$K"/update.bin.tmp.partial 2>/dev/null | sed 's/^/update file: /'
if [ "$jb" = yes ]; then
	rm -rf "$K"/update*.bin "$K"/update.bin.tmp.partial
	if [ -d "$K/fill_disk" ]; then
		rm -rf "$K/fill_disk" && echo "filler removed"
	fi
else
	echo "NOT jailbroken: filler kept so no update can download"
fi
df -m "$K" | awk 'NR==2{print "free: " $4 " MB"}'
sync
if diskutil eject "$K"; then
	echo "$(date '+%H:%M:%S') ejected; the Kindle is back on its Home screen"
else
	echo "eject failed; eject it from Finder"
fi
[ "$jb" = yes ]
