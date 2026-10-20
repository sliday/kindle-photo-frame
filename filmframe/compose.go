package main

import (
	"image"
	"image/draw"
	_ "image/jpeg"
	_ "image/png"
	"math"
	"os"

	xdraw "golang.org/x/image/draw"
)

// Kindle Paperwhite 4 panel, portrait, 300 ppi.
const (
	ScreenW = 1072
	ScreenH = 1448
)

var screenRect = image.Rect(0, 0, ScreenW, ScreenH)

// LoadPhoto decodes a photo and fits it to the screen the same way tools/prep-photos.sh does
// (fill when cropping loses at most 12%, otherwise fit on a black mat), so files that skipped
// the prep step still look right. Prepared files take the fast path.
func LoadPhoto(path string) (*image.Gray, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	src, _, err := image.Decode(f)
	if err != nil {
		return nil, err
	}
	out := image.NewGray(screenRect)
	b := src.Bounds()
	if b.Dx() == ScreenW && b.Dy() == ScreenH {
		draw.Draw(out, screenRect, src, b.Min, draw.Src)
		return out, nil
	}
	sw, sh := float64(b.Dx()), float64(b.Dy())
	a, t := sw/sh, float64(ScreenW)/float64(ScreenH)
	loss := 1 - a/t
	if a > t {
		loss = 1 - t/a
	}
	scale := math.Min(ScreenW/sw, ScreenH/sh)
	if loss <= 0.12 {
		scale = math.Max(ScreenW/sw, ScreenH/sh)
	}
	dw, dh := int(math.Round(sw*scale)), int(math.Round(sh*scale))
	x0, y0 := (ScreenW-dw)/2, (ScreenH-dh)/2
	xdraw.CatmullRom.Scale(out, image.Rect(x0, y0, x0+dw, y0+dh), src, b, draw.Src, nil)
	return out, nil
}

// 8x8 Bayer threshold matrix.
var bayer8 = [64]uint8{
	0, 32, 8, 40, 2, 34, 10, 42,
	48, 16, 56, 24, 50, 18, 58, 26,
	12, 44, 4, 36, 14, 46, 6, 38,
	60, 28, 52, 20, 62, 30, 54, 22,
	3, 35, 11, 43, 1, 33, 9, 41,
	51, 19, 59, 27, 49, 17, 57, 25,
	15, 47, 7, 39, 13, 45, 5, 37,
	63, 31, 55, 23, 61, 29, 53, 21,
}

// Dither16 maps r of src onto the panel's 16 gray levels (multiples of 17) with an ordered
// dither. The pattern depends only on pixel position, so a pixel that did not change between
// two fade steps dithers to the same value and the partial update leaves no seam.
// Exact levels such as pure black and white pass through untouched.
func Dither16(dst, src *image.Gray, r image.Rectangle) {
	r = r.Intersect(src.Bounds()).Intersect(dst.Bounds())
	for y := r.Min.Y; y < r.Max.Y; y++ {
		si, di := src.PixOffset(r.Min.X, y), dst.PixOffset(r.Min.X, y)
		row := bayer8[(y&7)*8 : (y&7)*8+8]
		for x := r.Min.X; x < r.Max.X; x++ {
			v := int(src.Pix[si]) * 15
			lvl := v / 255
			// round up when the remainder beats this position's threshold (b+0.5)/64
			if (v-lvl*255)*128 > (2*int(row[x&7])+1)*255 {
				lvl++
			}
			dst.Pix[di] = uint8(lvl * 17)
			si++
			di++
		}
	}
}

// DiffRect returns the bounding box of pixels that differ between a and b inside r,
// or an empty rectangle when nothing changed.
func DiffRect(a, b *image.Gray, r image.Rectangle) image.Rectangle {
	minX, minY, maxX, maxY := r.Max.X, r.Max.Y, r.Min.X-1, r.Min.Y-1
	for y := r.Min.Y; y < r.Max.Y; y++ {
		ai, bi := a.PixOffset(r.Min.X, y), b.PixOffset(r.Min.X, y)
		for x := r.Min.X; x < r.Max.X; x++ {
			if a.Pix[ai] != b.Pix[bi] {
				minX, maxX = min(minX, x), max(maxX, x)
				minY, maxY = min(minY, y), max(maxY, y)
			}
			ai++
			bi++
		}
	}
	if maxX < minX {
		return image.Rectangle{}
	}
	return image.Rect(minX, minY, maxX+1, maxY+1)
}
