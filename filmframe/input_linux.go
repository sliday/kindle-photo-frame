//go:build linux

package main

import (
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"syscall"
	"time"
	"unsafe"
)

// Linux input constants (linux/input-event-codes.h).
const (
	evSyn           = 0x00
	evKey           = 0x01
	evAbs           = 0x03
	synReport       = 0x00
	synDropped      = 0x03
	absX            = 0x00
	absY            = 0x01
	absMTSlot       = 0x2f
	absMTPositionX  = 0x35
	absMTPositionY  = 0x36
	absMTTrackingID = 0x39
	btnTouch        = 0x14a
	keyPower        = 116
	inputPropDirect = 0x01
)

// input_event is 16 bytes on the Kindle's 32-bit kernel (timeval of two longs).
var eventSize = 2*strconv.IntSize/8 + 8

func ioc(dir, nr, size uintptr) uintptr { return dir<<30 | size<<16 | 'E'<<8 | nr }

func ioctl(fd uintptr, req uintptr, arg unsafe.Pointer) error {
	if _, _, e := syscall.Syscall(syscall.SYS_IOCTL, fd, req, uintptr(arg)); e != 0 {
		return e
	}
	return nil
}

func evBits(fd uintptr, ev int) []byte {
	b := make([]byte, 96)
	_ = ioctl(fd, ioc(2, 0x20+uintptr(ev), uintptr(len(b))), unsafe.Pointer(&b[0]))
	return b
}

func hasBit(b []byte, n int) bool { return n/8 < len(b) && b[n/8]&(1<<(n%8)) != 0 }

func evName(fd uintptr) string {
	b := make([]byte, 128)
	_ = ioctl(fd, ioc(2, 0x06, uintptr(len(b))), unsafe.Pointer(&b[0]))
	for i, c := range b {
		if c == 0 {
			return string(b[:i])
		}
	}
	return string(b)
}

type absInfo struct{ Value, Min, Max, Fuzz, Flat, Res int32 }

func evAbsInfo(fd uintptr, code int) absInfo {
	var a absInfo
	_ = ioctl(fd, ioc(2, 0x40+uintptr(code), unsafe.Sizeof(a)), unsafe.Pointer(&a))
	return a
}

func eventNodes() []string {
	m, _ := filepath.Glob("/dev/input/event*")
	sort.Strings(m)
	return m
}

// TouchScreen reads one touch panel with an exclusive grab, so the paused stock UI
// never sees (and later replays) our taps.
type TouchScreen struct {
	f                      *os.File
	Name                   string
	mt                     bool
	xmin, xmax, ymin, ymax int32
	cfg                    Config
}

// OpenTouch finds the panel: a multitouch device flagged INPUT_PROP_DIRECT (Goodix or Parade
// on the PW4), else any multitouch device, else a single-touch one.
func OpenTouch(cfg Config) (*TouchScreen, error) {
	nodes := eventNodes()
	if cfg.TouchDevice != "" && cfg.TouchDevice != "auto" {
		nodes = []string{cfg.TouchDevice}
	}
	best, bestScore := "", 0
	for _, n := range nodes {
		f, err := os.Open(n)
		if err != nil {
			continue
		}
		fd := f.Fd()
		abs := evBits(fd, evAbs)
		props := make([]byte, 8)
		_ = ioctl(fd, ioc(2, 0x09, uintptr(len(props))), unsafe.Pointer(&props[0]))
		score := 0
		switch {
		case hasBit(abs, absMTPositionX) && hasBit(props, inputPropDirect):
			score = 3
		case hasBit(abs, absMTPositionX):
			score = 2
		case hasBit(abs, absX) && hasBit(evBits(fd, evKey), btnTouch):
			score = 1
		}
		f.Close()
		if score > bestScore {
			best, bestScore = n, score
		}
	}
	if best == "" {
		return nil, fmt.Errorf("no touchscreen among %v", nodes)
	}
	f, err := os.Open(best)
	if err != nil {
		return nil, err
	}
	fd := f.Fd()
	ts := &TouchScreen{f: f, Name: best + " (" + evName(fd) + ")", mt: bestScore >= 2, cfg: cfg}
	xc, yc := absMTPositionX, absMTPositionY
	if !ts.mt {
		xc, yc = absX, absY
	}
	xi, yi := evAbsInfo(fd, xc), evAbsInfo(fd, yc)
	ts.xmin, ts.xmax, ts.ymin, ts.ymax = xi.Min, xi.Max, yi.Min, yi.Max
	one := int32(1)
	if err := ioctl(fd, ioc(1, 0x90, 4), unsafe.Pointer(&one)); err != nil {
		f.Close()
		return nil, fmt.Errorf("grab %s: %w", best, err)
	}
	return ts, nil
}

func (ts *TouchScreen) Close() error {
	zero := int32(0)
	_ = ioctl(ts.f.Fd(), ioc(1, 0x90, 4), unsafe.Pointer(&zero))
	return ts.f.Close()
}

func (ts *TouchScreen) Range() string {
	return fmt.Sprintf("x %d..%d y %d..%d", ts.xmin, ts.xmax, ts.ymin, ts.ymax)
}

func scaleAxis(v, lo, hi int32, size int) int {
	if hi <= lo {
		return int(v)
	}
	return int(int64(v-lo) * int64(size-1) / int64(hi-lo))
}

func (ts *TouchScreen) toScreen(rx, ry int32) (int, int) {
	if ts.cfg.TouchSwapXY {
		rx, ry = ry, rx
	}
	xlo, xhi, ylo, yhi := ts.xmin, ts.xmax, ts.ymin, ts.ymax
	if ts.cfg.TouchSwapXY {
		xlo, xhi, ylo, yhi = ylo, yhi, xlo, xhi
	}
	x, y := scaleAxis(rx, xlo, xhi, ScreenW), scaleAxis(ry, ylo, yhi, ScreenH)
	if ts.cfg.TouchMirrorX {
		x = ScreenW - 1 - x
	}
	if ts.cfg.TouchMirrorY {
		y = ScreenH - 1 - y
	}
	return x, y
}

// Run decodes events into Touches for the first finger (slot 0) until the device closes.
func (ts *TouchScreen) Run(out chan<- Touch) error {
	buf := make([]byte, eventSize*64)
	var slot int32
	var id, prevID int32 = -1, -1
	var rx, ry int32
	moved, dropped := false, false
	for {
		n, err := ts.f.Read(buf)
		if err != nil {
			return err
		}
		for off := 0; off+eventSize <= n; off += eventSize {
			e := buf[off+eventSize-8 : off+eventSize]
			typ := binary.LittleEndian.Uint16(e[0:])
			code := binary.LittleEndian.Uint16(e[2:])
			val := int32(binary.LittleEndian.Uint32(e[4:]))
			if typ == evSyn && code == synDropped {
				// the kernel buffer overflowed: skip to the next report, then end the touch
				// so a stale "finger down" can't turn into a long press
				dropped = true
				continue
			}
			if dropped {
				if typ == evSyn && code == synReport {
					dropped, moved = false, false
					if prevID >= 0 {
						x, y := ts.toScreen(rx, ry)
						out <- Touch{TouchUp, x, y, time.Now()}
					}
					slot = evAbsInfo(ts.f.Fd(), absMTSlot).Value
					id, prevID = -1, -1
				}
				continue
			}
			switch {
			case typ == evAbs && code == absMTSlot:
				slot = val
			case typ == evAbs && slot == 0 && (code == absMTPositionX || (!ts.mt && code == absX)):
				rx, moved = val, true
			case typ == evAbs && slot == 0 && (code == absMTPositionY || (!ts.mt && code == absY)):
				ry, moved = val, true
			case typ == evAbs && slot == 0 && code == absMTTrackingID:
				id = val
			case typ == evKey && code == btnTouch && !ts.mt:
				if val != 0 {
					id = 0
				} else {
					id = -1
				}
			case typ == evSyn && code == synReport:
				x, y := ts.toScreen(rx, ry)
				now := time.Now()
				switch {
				case prevID < 0 && id >= 0:
					out <- Touch{TouchDown, x, y, now}
				case prevID >= 0 && id < 0:
					out <- Touch{TouchUp, x, y, now}
				case id >= 0 && moved:
					out <- Touch{TouchMove, x, y, now}
				}
				prevID, moved = id, false
			}
		}
	}
}

// WatchPower sends on out for every power-button press, read without a grab so powerd
// still sees it. preventScreenSaver may stop powerd acting on the button; we still do.
func WatchPower(out chan<- struct{}) {
	for _, n := range eventNodes() {
		f, err := os.Open(n)
		if err != nil {
			continue
		}
		if !hasBit(evBits(f.Fd(), evKey), keyPower) || hasBit(evBits(f.Fd(), evAbs), absMTPositionX) {
			f.Close()
			continue
		}
		go func(f *os.File) {
			defer f.Close()
			buf := make([]byte, eventSize*16)
			for {
				n, err := f.Read(buf)
				if err != nil {
					return
				}
				for off := 0; off+eventSize <= n; off += eventSize {
					e := buf[off+eventSize-8 : off+eventSize]
					if binary.LittleEndian.Uint16(e[0:]) == evKey &&
						binary.LittleEndian.Uint16(e[2:]) == keyPower &&
						binary.LittleEndian.Uint32(e[4:]) == 1 {
						select {
						case out <- struct{}{}:
						default:
						}
					}
				}
			}
		}(f)
	}
}
