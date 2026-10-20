//go:build linux

package main

import (
	"encoding/binary"
	"os"
	"unsafe"
)

const (
	fbioGetVScreenInfo    = 0x4600
	grayscale8BitInverted = 0x2 // mxcfb.h: the kernel's hardware night mode
)

// panelInverted reports whether the system Dark Mode has the e-ink controller inverting
// everything (fb_var_screeninfo.grayscale == GRAYSCALE_8BIT_INVERTED, as KOReader reads it).
// Read-only: the frame never changes the setting, it just sends negatives while it's on.
func panelInverted() bool {
	f, err := os.Open("/dev/fb0")
	if err != nil {
		return false
	}
	defer f.Close()
	var v [160]byte // struct fb_var_screeninfo; grayscale is the 8th u32
	if err := ioctl(f.Fd(), fbioGetVScreenInfo, unsafe.Pointer(&v[0])); err != nil {
		return false
	}
	return binary.LittleEndian.Uint32(v[28:]) == grayscale8BitInverted
}
