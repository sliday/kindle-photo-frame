#!/bin/sh
# Name: Film Frame - finish setup
# Author: Film Frame
# Run once after the jailbreak. Checks it worked, then frees the space the filler took.
# The filler stays if any check fails, so no firmware update can download.
echo "Film Frame: finishing setup"
echo
ok=1
check() {
	if eval "$2"; then
		echo "  ok    $1"
	else
		echo "  FAIL  $1"
		ok=0
	fi
}
check "jailbreak installed" "[ -f /var/local/jailbreak.txt ] || [ -f /mnt/us/documents/JAILBROKEN.txt ]"
check "fbink present" "[ -x /mnt/us/libkh/bin/fbink ]"
check "updater disabled" "[ ! -e /usr/bin/otaupd ] || [ -e /usr/bin/otaupd.bck ]"
echo
# update files first, filler second (kindlemodding order)
for f in /mnt/us/update*.bin /mnt/us/update.bin.tmp.partial; do
	[ -e "$f" ] && rm -rf "$f" && echo "  removed $f"
done
if [ "$ok" = 1 ]; then
	if [ -d /mnt/us/fill_disk ]; then
		rm -rf /mnt/us/fill_disk && echo "  filler removed, space is back"
	fi
	echo
	df -h /mnt/us | tail -1 | awk '{print "  free: " $4}'
	echo
	echo "Done. Go Home and tap Film Frame."
else
	echo "Something is missing, so the filler stays."
	echo "Take a photo of this screen and send it over."
fi
