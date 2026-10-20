package main

import (
	"bytes"
	"embed"
	"image"
	"image/color"
	"math"
	"strconv"

	"github.com/srwiley/oksvg"
	"github.com/srwiley/rasterx"
	"golang.org/x/image/font"
	"golang.org/x/image/font/opentype"
	"golang.org/x/image/math/fixed"
)

//go:embed assets/InterDisplay-Light.ttf assets/Inter-Regular.ttf assets/icons/*.svg
var assets embed.FS

// Layout on the 1072x1448 panel, measured from the touch-state mockup.
const (
	bandH         = 600 // height of the darkened band at the top
	clockSize     = 204
	clockBaseline = 296
	lineSize      = 44
	lineBaseline  = 380
	iconSize      = 54
	iconGap       = 18
	ruleY         = 428
	ruleThick     = 2
	ruleHalfW     = 328
	ruleLevel     = 205 // light gray, quieter than the text
	scrimDarkest  = 0.74
	scrimTone     = 26 // the band blends toward this deep gray, muting photo detail behind text
	shadowRadius  = 5
	shadowAlpha   = 0.45
)

var bandRect = image.Rect(0, 0, ScreenW, bandH)

// OverlayState is one frame of the fade: each value runs 0..1.
type OverlayState struct {
	Scrim float64 // strength of the dark band behind the text
	Text  float64 // opacity of clock, weather line and rule
	Rule  float64 // share of the rule drawn, growing from the center out
}

// OverlayInfo is what the overlay says.
type OverlayInfo struct {
	Clock string // "18:42"
	Line  string // "12°C · partly cloudy"
	Icon  string // icon file name without .svg, or ""
}

type Overlay struct {
	clockFace, lineFace font.Face
	key                 string
	text                *image.Alpha // coverage of clock, line and icon
	shadow              *image.Alpha // blurred copy of text, shifted down
	scrim               [bandH]float64
}

func NewOverlay() (*Overlay, error) {
	cf, err := loadFace("assets/InterDisplay-Light.ttf", clockSize)
	if err != nil {
		return nil, err
	}
	lf, err := loadFace("assets/Inter-Regular.ttf", lineSize)
	if err != nil {
		return nil, err
	}
	o := &Overlay{clockFace: cf, lineFace: lf}
	// full strength down past the rule, then a smooth falloff to nothing
	for y := range o.scrim {
		t := (float64(y) - 0.45*bandH) / (0.55 * bandH)
		t = math.Max(0, math.Min(1, t))
		o.scrim[y] = scrimDarkest * (1 - t*t*(3-2*t))
	}
	return o, nil
}

func loadFace(name string, size float64) (font.Face, error) {
	b, err := assets.ReadFile(name)
	if err != nil {
		return nil, err
	}
	f, err := opentype.Parse(b)
	if err != nil {
		return nil, err
	}
	return opentype.NewFace(f, &opentype.FaceOptions{Size: size, DPI: 72, Hinting: font.HintingNone})
}

// prepare renders the text masks once per distinct OverlayInfo.
func (o *Overlay) prepare(info OverlayInfo) {
	key := info.Clock + "\x00" + info.Line + "\x00" + info.Icon
	if key == o.key {
		return
	}
	o.key = key
	o.text = image.NewAlpha(bandRect)

	cw := font.MeasureString(o.clockFace, info.Clock).Round()
	d := font.Drawer{Dst: o.text, Src: image.Opaque, Face: o.clockFace,
		Dot: fixed.P((ScreenW-cw)/2, clockBaseline)}
	d.DrawString(info.Clock)

	lw := font.MeasureString(o.lineFace, info.Line).Round()
	icon := o.icon(info.Icon)
	total := lw
	if icon != nil {
		total += iconGap + iconSize
	}
	x := (ScreenW - total) / 2
	d = font.Drawer{Dst: o.text, Src: image.Opaque, Face: o.lineFace,
		Dot: fixed.P(x, lineBaseline)}
	d.DrawString(info.Line)
	if icon != nil {
		// center the icon on the line's cap height
		cy := lineBaseline - lineSize*36/100
		ix, iy := x+lw+iconGap, cy-iconSize/2
		for yy := 0; yy < iconSize; yy++ {
			for xx := 0; xx < iconSize; xx++ {
				a := icon.AlphaAt(xx, yy).A
				if a > o.text.AlphaAt(ix+xx, iy+yy).A {
					o.text.SetAlpha(ix+xx, iy+yy, color.Alpha{A: a})
				}
			}
		}
	}
	o.shadow = blurShift(o.text, shadowRadius, 2)
}

// icon rasterizes an embedded Lucide SVG at iconSize, slightly thinner than stock
// so it sits with the Regular weight of the line.
func (o *Overlay) icon(name string) *image.Alpha {
	if name == "" {
		return nil
	}
	b, err := assets.ReadFile("assets/icons/" + name + ".svg")
	if err != nil {
		return nil
	}
	b = bytes.ReplaceAll(b, []byte("currentColor"), []byte("#ffffff"))
	b = bytes.ReplaceAll(b, []byte(`stroke-width="2"`), []byte(`stroke-width="1.6"`))
	ic, err := oksvg.ReadIconStream(bytes.NewReader(b), oksvg.IgnoreErrorMode)
	if err != nil {
		return nil
	}
	ic.SetTarget(0, 0, iconSize, iconSize)
	rgba := image.NewRGBA(image.Rect(0, 0, iconSize, iconSize))
	sc := rasterx.NewScannerGV(iconSize, iconSize, rgba, rgba.Bounds())
	ic.Draw(rasterx.NewDasher(iconSize, iconSize, sc), 1)
	m := image.NewAlpha(rgba.Bounds())
	for i := range m.Pix {
		m.Pix[i] = rgba.Pix[i*4+3]
	}
	return m
}

// Render writes photo + overlay into dst (full screen, 8-bit) for the band only;
// rows below the band are copied from the photo unchanged.
func (o *Overlay) Render(dst, photo *image.Gray, info OverlayInfo, st OverlayState) {
	o.prepare(info)
	copy(dst.Pix, photo.Pix)
	if st.Scrim <= 0 && st.Text <= 0 {
		return
	}
	ruleHalf := int(math.Round(st.Rule * ruleHalfW))
	for y := 0; y < bandH; y++ {
		k := o.scrim[y] * st.Scrim
		inRule := y >= ruleY && y < ruleY+ruleThick && ruleHalf > 0
		p := dst.PixOffset(0, y)
		m := o.text.PixOffset(0, y)
		for x := 0; x < ScreenW; x++ {
			v := float64(photo.Pix[p+x])
			v += (scrimTone - v) * k
			if s := o.shadow.Pix[m+x]; s != 0 {
				v *= 1 - shadowAlpha*st.Text*float64(s)/255
			}
			if t := o.text.Pix[m+x]; t != 0 {
				v += (255 - v) * st.Text * float64(t) / 255
			}
			if inRule && x >= ScreenW/2-ruleHalf && x < ScreenW/2+ruleHalf {
				v += (ruleLevel - v) * st.Text
			}
			dst.Pix[p+x] = uint8(math.Round(math.Max(0, math.Min(255, v))))
		}
	}
}

// blurShift returns a box-blurred (two passes) copy of m moved down by dy pixels.
func blurShift(m *image.Alpha, r, dy int) *image.Alpha {
	b := m.Bounds()
	w, h := b.Dx(), b.Dy()
	buf := make([]float64, w*h)
	for y := 0; y < h; y++ {
		sy := y - dy
		if sy < 0 {
			continue
		}
		for x := 0; x < w; x++ {
			buf[y*w+x] = float64(m.Pix[sy*m.Stride+x])
		}
	}
	tmp := make([]float64, w*h)
	for pass := 0; pass < 2; pass++ {
		boxH(buf, tmp, w, h, r)
		boxV(tmp, buf, w, h, r)
	}
	out := image.NewAlpha(b)
	for i, v := range buf {
		out.Pix[i] = uint8(math.Min(255, v))
	}
	return out
}

func boxH(src, dst []float64, w, h, r int) {
	n := float64(2*r + 1)
	for y := 0; y < h; y++ {
		row := src[y*w : (y+1)*w]
		var sum float64
		for x := -r; x <= r; x++ {
			sum += row[clampInt(x, 0, w-1)]
		}
		for x := 0; x < w; x++ {
			dst[y*w+x] = sum / n
			sum += row[clampInt(x+r+1, 0, w-1)] - row[clampInt(x-r, 0, w-1)]
		}
	}
}

func boxV(src, dst []float64, w, h, r int) {
	n := float64(2*r + 1)
	for x := 0; x < w; x++ {
		var sum float64
		for y := -r; y <= r; y++ {
			sum += src[clampInt(y, 0, h-1)*w+x]
		}
		for y := 0; y < h; y++ {
			dst[y*w+x] = sum / n
			sum += src[clampInt(y+r+1, 0, h-1)*w+x] - src[clampInt(y-r, 0, h-1)*w+x]
		}
	}
}

func clampInt(v, lo, hi int) int { return max(lo, min(hi, v)) }

// FadeIn and FadeOut are the touch sequence. Text first at low opacity, settling to full
// contrast, then the rule draws out from the center. Out reverses it; the caller ends with a
// flashing full refresh of the bare photo to clear ghosting.
var (
	FadeIn = []OverlayState{
		{Scrim: 0.5, Text: 0.35},
		{Scrim: 0.8, Text: 0.7},
		{Scrim: 1, Text: 1},
		{Scrim: 1, Text: 1, Rule: 0.45},
		{Scrim: 1, Text: 1, Rule: 1},
	}
	FadeOut = []OverlayState{
		{Scrim: 0.7, Text: 0.55, Rule: 1},
		{Scrim: 0.35, Text: 0.2, Rule: 1},
	}
	Shown = OverlayState{Scrim: 1, Text: 1, Rule: 1}
)

// weatherLine formats "12°C · partly cloudy".
func weatherLine(tempC float64, code int, fahrenheit bool) string {
	t, u := tempC, "C"
	if fahrenheit {
		t, u = tempC*9/5+32, "F"
	}
	return strconv.Itoa(int(math.Round(t))) + "°" + u + " · " + wmoText(code)
}
