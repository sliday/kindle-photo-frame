// Command filmframe turns a jailbroken Kindle Paperwhite 4 into a photo frame for film scans:
// a bare photo on screen, and on touch a clock and weather that fade in, hold, and fade out.
//
//go:debug x509usefallbackroots=1
package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"strings"
	"time"
	_ "time/tzdata"

	// Mozilla roots baked in: the Kindle's own CA bundle is years out of date
	_ "golang.org/x/crypto/x509roots/fallback"
)

var version = "dev"

func main() {
	cfgPath := flag.String("config", "/mnt/us/filmframe/filmframe.conf", "config file")
	preview := flag.String("preview", "", "render the touch sequence into this directory and exit")
	photo := flag.String("photo", "", "photo for -preview")
	at := flag.String("at", "18:42", "clock text for -preview")
	line := flag.String("line", "12°C · Partly cloudy", "weather line for -preview")
	icon := flag.String("icon", "cloud", "icon for -preview")
	showVersion := flag.Bool("version", false, "print version")
	flag.Parse()
	if *showVersion {
		fmt.Println("filmframe", version)
		return
	}
	cfg, err := LoadConfig(*cfgPath)
	if err != nil {
		log.Fatal(err)
	}
	if *preview != "" {
		if err := runPreview(*preview, *photo, OverlayInfo{Clock: *at, Line: *line, Icon: *icon}); err != nil {
			log.Fatal(err)
		}
		return
	}
	log.SetFlags(log.LstdFlags)
	if err := runDevice(cfg); err != nil {
		log.Fatal(err)
	}
}

// runPreview plays one touch: bare photo, fade in, hold, fade out, full refresh.
func runPreview(dir, photo string, info OverlayInfo) error {
	if photo == "" {
		return fmt.Errorf("-preview needs -photo")
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	img, err := LoadPhoto(photo)
	if err != nil {
		return err
	}
	pd := NewPreviewDisplay(dir)
	fr, err := NewFrame(pd)
	if err != nil {
		return err
	}
	t := time.Now()
	if err := fr.SetPhoto(img); err != nil {
		return err
	}
	if err := fr.ShowOverlay(info, 0); err != nil {
		return err
	}
	if err := fr.HideOverlay(0); err != nil {
		return err
	}
	pd.Log = append(pd.Log, fmt.Sprintf("render time on this machine: %v", time.Since(t).Round(time.Millisecond)))
	fmt.Println(strings.Join(pd.Log, "\n"))
	return nil
}
