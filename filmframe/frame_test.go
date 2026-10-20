package main

import (
	"image"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestDitherKeepsExactLevelsAndStaysOnPalette(t *testing.T) {
	src := image.NewGray(image.Rect(0, 0, 64, 16))
	for i := range src.Pix {
		src.Pix[i] = uint8(i % 256)
	}
	dst := image.NewGray(src.Bounds())
	Dither16(dst, src, src.Bounds())
	for i, v := range dst.Pix {
		if v%17 != 0 {
			t.Fatalf("pixel %d = %d, not one of the 16 panel levels", i, v)
		}
		if s := src.Pix[i]; s%17 == 0 && v != s {
			t.Fatalf("exact level %d changed to %d", s, v)
		}
	}
}

func TestDitherAverageTracksInput(t *testing.T) {
	src := image.NewGray(image.Rect(0, 0, 64, 64))
	dst := image.NewGray(src.Bounds())
	for _, g := range []uint8{40, 100, 128, 200} {
		for i := range src.Pix {
			src.Pix[i] = g
		}
		Dither16(dst, src, src.Bounds())
		sum := 0
		for _, v := range dst.Pix {
			sum += int(v)
		}
		if avg := float64(sum) / float64(len(dst.Pix)); avg < float64(g)-2 || avg > float64(g)+2 {
			t.Errorf("gray %d dithers to average %.1f", g, avg)
		}
	}
}

func TestDiffRect(t *testing.T) {
	a := image.NewGray(image.Rect(0, 0, 100, 100))
	b := image.NewGray(a.Bounds())
	if r := DiffRect(a, b, a.Bounds()); !r.Empty() {
		t.Fatalf("identical images differ in %v", r)
	}
	b.Pix[b.PixOffset(10, 20)] = 1
	b.Pix[b.PixOffset(30, 5)] = 1
	if r := DiffRect(a, b, a.Bounds()); r != image.Rect(10, 5, 31, 21) {
		t.Fatalf("got %v", r)
	}
}

func TestShuffleShowsEveryPhotoOnceBeforeRepeating(t *testing.T) {
	dir := t.TempDir()
	for _, n := range []string{"a.jpg", "b.JPG", "c.png", "d.jpeg", "e.jpg", ".hidden.jpg", "notes.txt"} {
		os.WriteFile(filepath.Join(dir, n), nil, 0o644)
	}
	cfg := DefaultConfig()
	cfg.PhotoDir, cfg.StateDir = dir, t.TempDir()
	p, err := NewPlaylist(cfg)
	if err != nil {
		t.Fatal(err)
	}
	if len(p.Deck) != 5 {
		t.Fatalf("deck %v", p.Deck)
	}
	seen := map[string]bool{filepath.Base(p.Current()): true}
	for i := 0; i < 4; i++ {
		n := filepath.Base(p.Next())
		if seen[n] {
			t.Fatalf("%s repeated within one pass", n)
		}
		seen[n] = true
	}
	last := filepath.Base(p.Current())
	if filepath.Base(p.Next()) == last {
		t.Fatal("new shuffle opened with the photo just shown")
	}
	// the position survives a restart
	cur := p.Current()
	p2, _ := NewPlaylist(cfg)
	if p2.Current() != cur {
		t.Fatalf("restart moved from %s to %s", cur, p2.Current())
	}
	if prev := p2.Prev(); prev != filepath.Join(dir, last) {
		t.Fatalf("prev went to %s, want %s", prev, last)
	}
}

func TestGestures(t *testing.T) {
	t0 := time.Now()
	at := func(ms int) time.Time { return t0.Add(time.Duration(ms) * time.Millisecond) }
	g := &Gestures{LongPress: 3 * time.Second}
	g.Feed(Touch{TouchDown, 500, 700, at(0)})
	if got := g.Feed(Touch{TouchUp, 510, 705, at(120)}); got != Tap {
		t.Fatalf("tap: got %v", got)
	}
	g.Feed(Touch{TouchDown, 900, 700, at(1000)})
	g.Feed(Touch{TouchMove, 600, 710, at(1100)})
	if got := g.Feed(Touch{TouchUp, 300, 720, at(1200)}); got != SwipeLeft {
		t.Fatalf("swipe left: got %v", got)
	}
	g.Feed(Touch{TouchDown, 500, 700, at(2000)})
	if got := g.Poll(at(4000)); got != NoGesture {
		t.Fatalf("long press fired early: %v", got)
	}
	if got := g.Poll(at(5100)); got != LongPress {
		t.Fatalf("long press: got %v", got)
	}
	if got := g.Feed(Touch{TouchUp, 500, 700, at(5200)}); got != NoGesture {
		t.Fatalf("lift after long press made %v", got)
	}
	// a finger that lands during a fade does nothing when it lifts afterwards
	g.Muted = true
	g.Feed(Touch{TouchDown, 500, 700, at(6000)})
	g.Muted = false
	if got := g.Feed(Touch{TouchUp, 500, 700, at(6100)}); got != NoGesture {
		t.Fatalf("muted touch made %v", got)
	}
}

func TestConfigParses(t *testing.T) {
	p := filepath.Join(t.TempDir(), "c.conf")
	os.WriteFile(p, []byte("# comment\norder = random\nphoto_minutes = 45 # inline\nhold_seconds=7.5\nunits = f\nclock = 12h\n"), 0o644)
	c, err := LoadConfig(p)
	if err != nil {
		t.Fatal(err)
	}
	if c.Order != "random" || c.PhotoInterval != 45*time.Minute || c.Hold != 7500*time.Millisecond || !c.Fahrenheit || !c.Clock12h {
		t.Fatalf("%+v", c)
	}
	os.WriteFile(p, []byte("order = sideways\n"), 0o644)
	if _, err := LoadConfig(p); err == nil {
		t.Fatal("bad order accepted")
	}
}

func TestWeatherLine(t *testing.T) {
	if got := weatherLine(11.6, 2, false); got != "12°C · partly cloudy" {
		t.Fatalf("got %q", got)
	}
	if got := weatherLine(-0.4, 71, false); got != "0°C · light snow" {
		t.Fatalf("got %q", got)
	}
	if wmoIcon(2, true) != "cloud-sun" || wmoIcon(0, false) != "moon" || wmoIcon(95, true) != "cloud-lightning" {
		t.Fatal("icon mapping")
	}
}
