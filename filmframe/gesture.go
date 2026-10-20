package main

import "time"

// TouchKind is a finger going down, moving or lifting.
type TouchKind int

const (
	TouchDown TouchKind = iota
	TouchMove
	TouchUp
)

// Touch is one finger event in screen pixels.
type Touch struct {
	Kind TouchKind
	X, Y int
	T    time.Time
}

// Gesture is what the frame reacts to.
type Gesture int

const (
	NoGesture Gesture = iota
	Tap
	SwipeLeft  // finger moves right to left: next photo
	SwipeRight // left to right: previous photo
	LongPress  // held still: leave the frame
)

const (
	tapSlop    = 50  // px a tap may wander
	swipeMinDX = 180 // px
	tapMaxTime = time.Second
)

// Gestures turns raw touches into taps, swipes and a long press. Muted swallows results while
// still tracking the finger, so touches made during a fade don't fire once it ends.
type Gestures struct {
	LongPress time.Duration
	Muted     bool
	down      bool
	swallow   bool // finger went down while muted: ignore it until it lifts
	sx, sy    int
	x, y      int
	t0        time.Time
	fired     bool
}

// Feed takes one touch and returns a finished gesture, if any.
func (g *Gestures) Feed(t Touch) Gesture {
	switch t.Kind {
	case TouchDown:
		g.down, g.fired, g.swallow = true, false, g.Muted
		g.sx, g.sy, g.x, g.y, g.t0 = t.X, t.Y, t.X, t.Y, t.T
	case TouchMove:
		if g.down {
			g.x, g.y = t.X, t.Y
		}
	case TouchUp:
		if !g.down {
			return NoGesture
		}
		g.down = false
		g.x, g.y = t.X, t.Y
		if g.Muted || g.swallow || g.fired {
			return NoGesture
		}
		dx, dy := g.x-g.sx, g.y-g.sy
		switch {
		case abs(dx) >= swipeMinDX && abs(dx) > 2*abs(dy) && dx < 0:
			return SwipeLeft
		case abs(dx) >= swipeMinDX && abs(dx) > 2*abs(dy):
			return SwipeRight
		case abs(dx) <= tapSlop && abs(dy) <= tapSlop && t.T.Sub(g.t0) <= tapMaxTime:
			return Tap
		}
	}
	return NoGesture
}

// Poll reports a long press once the finger has stayed put for LongPress.
func (g *Gestures) Poll(now time.Time) Gesture {
	if !g.down || g.fired || g.swallow || g.Muted || g.LongPress <= 0 {
		return NoGesture
	}
	if abs(g.x-g.sx) > tapSlop || abs(g.y-g.sy) > tapSlop {
		return NoGesture
	}
	if now.Sub(g.t0) >= g.LongPress {
		g.fired = true
		return LongPress
	}
	return NoGesture
}

func abs(v int) int {
	if v < 0 {
		return -v
	}
	return v
}
