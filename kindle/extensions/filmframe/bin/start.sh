#!/bin/sh
# KUAL entry point: detach so the frame outlives KUAL's menu process.
cd /
if command -v setsid >/dev/null 2>&1; then
	setsid sh /mnt/us/extensions/filmframe/bin/run.sh </dev/null >/dev/null 2>&1 &
else
	nohup sh /mnt/us/extensions/filmframe/bin/run.sh </dev/null >/dev/null 2>&1 &
fi
