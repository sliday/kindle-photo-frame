#!/bin/sh
# Film Frame session: pause the stock UI the way KOReader does on FW 5.x (Upstart),
# run the frame, then put everything back, even if the frame crashed or we got killed.
EXT=/mnt/us/extensions/filmframe
BASE=/mnt/us/filmframe
LOG="$BASE/filmframe.log"
PIDF=/tmp/filmframe.pid

if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
	exit 0
fi
echo $$ >"$PIDF"
mkdir -p "$BASE"
if [ -f "$LOG" ] && [ "$(wc -c <"$LOG")" -gt 1048576 ]; then
	mv "$LOG" "$LOG.old"
fi
exec >>"$LOG" 2>&1
echo "== $(date -u) session start"

STOPPED=""
CHILD=""
RESTORED=""
restore() {
	[ -n "$RESTORED" ] && return
	RESTORED=yes
	killall -CONT volumd 2>/dev/null
	for job in $STOPPED; do
		start "$job" >/dev/null 2>&1
	done
	killall -CONT awesome
	lipc-set-prop com.lab126.pillow disableEnablePillow enable
	# Leave the user on a freshly drawn Home screen instead of our last frame.
	lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home
	rm -f "$PIDF"
	echo "== $(date -u) stock UI restored"
}
on_signal() {
	[ -n "$CHILD" ] && kill -TERM "$CHILD" 2>/dev/null && wait "$CHILD"
	restore
	exit 0
}
trap on_signal TERM INT HUP
trap restore EXIT

# Hide the status bar and freeze the window manager so the clock stops redrawing over us.
lipc-set-prop com.lab126.pillow disableEnablePillow disable
killall -STOP awesome
# Free RAM, and keep the OTA updater asleep while Wi-Fi is up for the weather.
SERVICES="stored webreader kfxreader kfxview todo tmd rcm archive scanner otav3 otaupd"
[ -f /etc/upstart/statusbar.conf ] && SERVICES="$SERVICES statusbar"
for job in $SERVICES; do
	if status "$job" 2>/dev/null | grep -q "start/"; then
		stop "$job" >/dev/null 2>&1 && STOPPED="$STOPPED $job"
	fi
done
# Keep USB mass storage from yanking /mnt/us (photos, log) away mid-run.
killall -STOP volumd 2>/dev/null

# In the background plus wait, so this shell can still act on signals while the frame runs.
"$EXT/bin/filmframe" -config "$BASE/filmframe.conf" &
CHILD=$!
wait "$CHILD"
echo "== $(date -u) frame exited with $?"
CHILD=""
restore
