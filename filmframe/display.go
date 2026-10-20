package main

import (
	"fmt"
	"image"
	"image/png"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// Refresh picks how the panel redraws.
type Refresh int

const (
	Partial Refresh = iota // no flash, only the changed rectangle
	Full                   // flashing full-screen refresh, clears ghosting
)

// Display pushes the screen image (already dithered to 16 levels) to the panel.
// r is the part of img that changed; Full ignores r and redraws everything.
type Display interface {
	Show(img *image.Gray, r image.Rectangle, mode Refresh) error
}

// FBInk drives the panel through NiLuJe's fbink CLI: the region is written as a PNG on tmpfs
// and drawn at its screen position; fbink limits the e-ink update to that rectangle.
type FBInk struct {
	Bin      string
	Waveform string // waveform for partial updates, e.g. GC16 or REAGL
	// Inverted reports whether the system Dark Mode has the panel inverting in hardware.
	// While it does, frames go out as negatives so they land on screen as positives.
	Inverted func() bool
	inv      bool
	tmp      string
}

func NewFBInk(bin, waveform string) (*FBInk, error) {
	if bin == "" || bin == "auto" {
		bin = findFBInk()
	}
	if bin == "" {
		return nil, fmt.Errorf("fbink not found; set fbink = /path/to/fbink in filmframe.conf")
	}
	tmp := "/tmp/filmframe"
	if err := os.MkdirAll(tmp, 0o755); err != nil {
		return nil, err
	}
	return &FBInk{Bin: bin, Waveform: waveform, tmp: tmp}, nil
}

// fbinkCandidates lists where jailbreak bundles put fbink, ours first.
var fbinkCandidates = []string{
	"/mnt/us/extensions/filmframe/bin/fbink",
	"/mnt/us/libkh/bin/fbink",
	"/usr/bin/fbink",
	"/mnt/us/koreader/fbink",
	"/mnt/us/extensions/MRInstaller/bin/K5/fbink",
}

func findFBInk() string {
	for _, p := range fbinkCandidates {
		if fi, err := os.Stat(p); err == nil && !fi.IsDir() {
			return p
		}
	}
	if p, err := exec.LookPath("fbink"); err == nil {
		return p
	}
	return ""
}

func (f *FBInk) Show(img *image.Gray, r image.Rectangle, mode Refresh) error {
	if mode == Full {
		r = screenRect
		if f.Inverted != nil {
			f.inv = f.Inverted()
		}
	}
	r = r.Intersect(screenRect)
	if r.Empty() {
		return nil
	}
	var src image.Image = img.SubImage(r)
	if f.inv {
		src = negative(img, r)
	}
	path := filepath.Join(f.tmp, "frame.png")
	if err := writePNG(path, src); err != nil {
		return err
	}
	// -q quiet, -g image at its pixel position, -W waveform, -f flash, -w wait for the
	// update to finish so fade steps don't pile up in the EPDC queue
	args := []string{"-q", "-w", "-g", fmt.Sprintf("file=%s,x=%d,y=%d", path, r.Min.X, r.Min.Y)}
	if mode == Full {
		args = append(args, "-W", "GC16", "-f")
	} else {
		args = append(args, "-W", f.Waveform)
	}
	out, err := exec.Command(f.Bin, args...).CombinedOutput()
	if err != nil {
		return fmt.Errorf("fbink %s: %v: %s", strings.Join(args, " "), err, out)
	}
	return nil
}

// negative copies r of img with every level flipped; panel levels stay on the 16-step palette.
func negative(img *image.Gray, r image.Rectangle) *image.Gray {
	out := image.NewGray(r)
	for y := r.Min.Y; y < r.Max.Y; y++ {
		s := img.Pix[img.PixOffset(r.Min.X, y):img.PixOffset(r.Max.X, y)]
		d := out.Pix[out.PixOffset(r.Min.X, y):out.PixOffset(r.Max.X, y)]
		for i, v := range s {
			d[i] = 255 - v
		}
	}
	return out
}

// Clear blanks the panel with a flashing white refresh.
func (f *FBInk) Clear() error {
	return exec.Command(f.Bin, "-q", "-c", "-f", "-w").Run()
}

func writePNG(path string, img image.Image) error {
	tmp := path + ".tmp"
	fh, err := os.Create(tmp)
	if err != nil {
		return err
	}
	enc := png.Encoder{CompressionLevel: png.BestSpeed}
	if err := enc.Encode(fh, img); err != nil {
		fh.Close()
		return err
	}
	if err := fh.Close(); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

// PreviewDisplay keeps a virtual panel and saves it as a numbered PNG after every update,
// with a log of what a real panel would have refreshed.
type PreviewDisplay struct {
	Dir   string
	panel *image.Gray
	n     int
	Log   []string
	start time.Time
}

func NewPreviewDisplay(dir string) *PreviewDisplay {
	return &PreviewDisplay{Dir: dir, panel: image.NewGray(screenRect), start: time.Now()}
}

func (p *PreviewDisplay) Show(img *image.Gray, r image.Rectangle, mode Refresh) error {
	if mode == Full {
		r = screenRect
	}
	r = r.Intersect(screenRect)
	for y := r.Min.Y; y < r.Max.Y; y++ {
		copy(p.panel.Pix[p.panel.PixOffset(r.Min.X, y):p.panel.PixOffset(r.Max.X, y)],
			img.Pix[img.PixOffset(r.Min.X, y):img.PixOffset(r.Max.X, y)])
	}
	kind := "partial"
	if mode == Full {
		kind = "FULL+flash"
	}
	p.n++
	name := fmt.Sprintf("%02d.png", p.n)
	p.Log = append(p.Log, fmt.Sprintf("%s %-10s %4dx%-4d at %d,%d", name, kind, r.Dx(), r.Dy(), r.Min.X, r.Min.Y))
	return writePNG(filepath.Join(p.Dir, name), p.panel)
}
