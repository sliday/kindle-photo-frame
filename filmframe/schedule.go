package main

import "time"

// wallNow is the current time without Go's monotonic reading. The monotonic clock stops
// while the Kindle is suspended, so every deadline that may span a sleep uses wall time.
func wallNow() time.Time { return time.Now().Round(0) }

// earliest returns the soonest non-zero time, or the zero time when all are zero.
func earliest(ts ...time.Time) time.Time {
	var e time.Time
	for _, t := range ts {
		if !t.IsZero() && (e.IsZero() || t.Before(e)) {
			e = t
		}
	}
	return e
}

// due reports whether deadline t is set and has passed.
func due(t, now time.Time) bool { return !t.IsZero() && !now.Before(t) }

// future returns t if it lies ahead of now, else the zero time.
func future(t, now time.Time) time.Time {
	if t.After(now) {
		return t
	}
	return time.Time{}
}

// wantSleep decides whether the frame suspends between photos. auto sleeps only on battery:
// on a charger staying awake is free and keeps taps instant.
func wantSleep(mode string, externalPower bool) bool {
	switch mode {
	case "sleep":
		return true
	case "awake":
		return false
	}
	return !externalPower
}

// refusalBackoff is how long to stay awake after the kernel refused to suspend.
func refusalBackoff(n int) time.Duration {
	if n >= 3 {
		return 5 * time.Minute
	}
	return 30 * time.Second
}
