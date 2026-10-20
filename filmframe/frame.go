package main

import (
	"image"
	"time"
)

// Frame owns what is on the panel: the current photo and the overlay drawn over it.
type Frame struct {
	disp    Display
	ov      *Overlay
	photo   *image.Gray // current photo, 8-bit
	work    *image.Gray // photo + overlay, 8-bit
	shown   *image.Gray // last image sent to the panel, dithered
	next    *image.Gray // scratch for the next dithered frame
	info    OverlayInfo
	visible bool
}

func NewFrame(d Display) (*Frame, error) {
	ov, err := NewOverlay()
	if err != nil {
		return nil, err
	}
	return &Frame{disp: d, ov: ov,
		work: image.NewGray(screenRect), shown: image.NewGray(screenRect), next: image.NewGray(screenRect)}, nil
}

// SetPhoto shows a new photo with a flashing full refresh and drops any overlay.
func (f *Frame) SetPhoto(img *image.Gray) error {
	f.photo = img
	f.visible = false
	Dither16(f.next, img, screenRect)
	if err := f.disp.Show(f.next, screenRect, Full); err != nil {
		return err
	}
	f.shown, f.next = f.next, f.shown
	return nil
}

// step renders one overlay state and sends only the pixels that changed, as a partial update.
func (f *Frame) step(st OverlayState) error {
	f.ov.Render(f.work, f.photo, f.info, st)
	copy(f.next.Pix, f.shown.Pix)
	Dither16(f.next, f.work, bandRect)
	r := DiffRect(f.shown, f.next, bandRect)
	if r.Empty() {
		return nil
	}
	if err := f.disp.Show(f.next, r, Partial); err != nil {
		return err
	}
	f.shown, f.next = f.next, f.shown
	return nil
}

// ShowOverlay runs the fade-in. minStep paces the steps so each one gets seen even when
// the panel finishes early.
func (f *Frame) ShowOverlay(info OverlayInfo, minStep time.Duration) error {
	f.info = info
	for _, st := range FadeIn {
		t := time.Now()
		if err := f.step(st); err != nil {
			return err
		}
		if d := minStep - time.Since(t); d > 0 {
			time.Sleep(d)
		}
	}
	f.visible = true
	return nil
}

// UpdateOverlay redraws a visible overlay with new text, e.g. when the minute turns.
func (f *Frame) UpdateOverlay(info OverlayInfo) error {
	if !f.visible || info == f.info {
		return nil
	}
	f.info = info
	return f.step(Shown)
}

// HideOverlay fades out, then a flashing full refresh restores the bare photo.
func (f *Frame) HideOverlay(minStep time.Duration) error {
	for _, st := range FadeOut {
		t := time.Now()
		if err := f.step(st); err != nil {
			return err
		}
		if d := minStep - time.Since(t); d > 0 {
			time.Sleep(d)
		}
	}
	f.visible = false
	return f.SetPhoto(f.photo)
}
