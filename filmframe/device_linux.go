//go:build linux

package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"
)

// Step pacing: each fade step stays on screen at least this long.
const minStep = 220 * time.Millisecond

// runDevice is the frame's main loop on the Kindle. The launcher (run.sh) has already paused
// the stock UI and restores it after we return, whatever the reason.
func runDevice(cfg Config) error {
	log.Printf("filmframe %s starting", version)
	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM)
	signal.Ignore(syscall.SIGHUP)

	loc, err := time.LoadLocation(cfg.Timezone)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(cfg.StateDir, 0o755); err != nil {
		return err
	}
	fb, err := NewFBInk(cfg.FBInk, cfg.FadeWaveform)
	if err != nil {
		return err
	}
	log.Printf("fbink: %s", fb.Bin)
	fb.Inverted = panelInverted
	if panelInverted() {
		log.Printf("system Dark Mode is on: sending frames as negatives so photos show as positives")
	}
	fr, err := NewFrame(fb)
	if err != nil {
		return err
	}
	pl, err := NewPlaylist(cfg)
	if err != nil {
		return fmt.Errorf("photos in %s: %w", cfg.PhotoDir, err)
	}
	log.Printf("%d photos, order %s", len(pl.Deck), cfg.Order)

	ts, err := OpenTouch(cfg)
	if err != nil {
		return err
	}
	defer ts.Close()
	log.Printf("touch: %s %s", ts.Name, ts.Range())
	// room for a few seconds of dragging during a blocking fade, so the kernel buffer never overflows
	touches := make(chan Touch, 1024)
	go func() { log.Printf("touch reader stopped: %v", ts.Run(touches)) }()
	power := make(chan struct{}, 1)
	WatchPower(power)

	if err := preventScreenSaver(true); err != nil {
		log.Printf("preventScreenSaver: %v", err)
	}
	defer preventScreenSaver(false)
	if cfg.Frontlight >= 0 {
		_ = setFrontlight(cfg.Frontlight)
	}
	wifiWasOn := wifiEnabled()
	defer func() {
		if cfg.WifiPowerSave && wifiEnabled() != wifiWasOn {
			wifiSet(wifiWasOn)
		}
	}()

	show := func(path string) bool {
		for tries := 0; tries < 5; tries++ {
			img, err := LoadPhoto(path)
			if err == nil {
				if err := fr.SetPhoto(img); err != nil {
					log.Printf("display: %v", err)
				}
				log.Printf("photo %s (battery %s%%)", path, battery())
				return true
			}
			log.Printf("skip %s: %v", path, err)
			path = pl.Next()
		}
		return false
	}
	if !show(pl.Current()) {
		return fmt.Errorf("could not load any photo from %s", cfg.PhotoDir)
	}

	weather := loadWeather(cfg.StateDir)
	weatherDone := make(chan Weather, 1)
	fetching := false
	firstFetch := 5 * time.Second
	if age := time.Since(weather.Fetched); age < cfg.WeatherEvery {
		firstFetch = cfg.WeatherEvery - age
	}
	weatherTimer := time.NewTimer(firstFetch)
	fetch := func() {
		if fetching {
			return
		}
		fetching = true
		go func() {
			w, err := fetchWeatherOnline(cfg)
			if err != nil {
				log.Printf("weather: %v", err)
			}
			weatherDone <- w
		}()
	}

	photoTimer := time.NewTimer(cfg.PhotoInterval)
	if cfg.PhotoInterval <= 0 {
		photoTimer.Stop()
	}
	resetPhotoTimer := func() {
		if cfg.PhotoInterval > 0 {
			photoTimer.Reset(cfg.PhotoInterval)
		}
	}
	holdTimer := time.NewTimer(time.Hour)
	holdTimer.Stop()
	g := &Gestures{LongPress: cfg.LongPress}
	// the ticker runs only while a finger is down or the overlay is up, so an idle frame sleeps
	tick := time.NewTicker(250 * time.Millisecond)
	tick.Stop()
	defer tick.Stop()
	ticking := false
	syncTick := func() {
		if want := g.down || fr.visible; want != ticking {
			ticking = want
			if want {
				tick.Reset(250 * time.Millisecond)
			} else {
				tick.Stop()
			}
		}
	}

	info := func() OverlayInfo {
		now := time.Now().In(loc)
		clock := now.Format("15:04")
		if cfg.Clock12h {
			clock = now.Format("3:04")
		}
		if weather.Fetched.IsZero() || time.Since(weather.Fetched) > weatherStale {
			return OverlayInfo{Clock: clock, Line: strings.ToLower(now.Format("Monday, 2 January"))}
		}
		return OverlayInfo{Clock: clock, Line: weatherLine(weather.TempC, weather.Code, cfg.Fahrenheit),
			Icon: wmoIcon(weather.Code, weather.IsDay)}
	}

	// drain swallows touches that queued up during a blocking fade
	drain := func() {
		g.Muted = true
		for len(touches) > 0 {
			g.Feed(<-touches)
		}
		g.Muted = false
	}
	showOverlay := func() {
		if err := fr.ShowOverlay(info(), minStep); err != nil {
			log.Printf("overlay: %v", err)
		}
		holdTimer.Reset(cfg.Hold)
		drain()
	}
	hideOverlay := func() {
		holdTimer.Stop()
		if err := fr.HideOverlay(minStep); err != nil {
			log.Printf("overlay: %v", err)
		}
		drain()
	}
	changePhoto := func(path string) {
		holdTimer.Stop()
		show(path)
		resetPhotoTimer()
		drain()
	}
	act := func(gs Gesture) bool {
		switch gs {
		case Tap:
			if fr.visible {
				hideOverlay()
			} else {
				showOverlay()
			}
		case SwipeLeft:
			changePhoto(pl.Next())
		case SwipeRight:
			changePhoto(pl.Prev())
		case LongPress:
			log.Printf("long press: leaving")
			return false
		}
		return true
	}

	for {
		syncTick()
		select {
		case s := <-sigs:
			log.Printf("signal %v: leaving", s)
			return nil
		case t := <-touches:
			if !act(g.Feed(t)) {
				return nil
			}
		case <-power:
			if !act(Tap) {
				return nil
			}
		case now := <-tick.C:
			if !act(g.Poll(now)) {
				return nil
			}
			if fr.visible {
				if err := fr.UpdateOverlay(info()); err != nil {
					log.Printf("overlay: %v", err)
				}
			}
		case <-holdTimer.C:
			hideOverlay()
		case <-photoTimer.C:
			if fr.visible {
				photoTimer.Reset(10 * time.Second)
				continue
			}
			changePhoto(pl.Next())
		case <-weatherTimer.C:
			fetch()
		case w := <-weatherDone:
			fetching = false
			if w.Fetched.IsZero() {
				weatherTimer.Reset(5 * time.Minute)
				continue
			}
			weather = w
			if err := saveWeather(cfg.StateDir, w); err != nil {
				log.Printf("save weather: %v", err)
			}
			weatherTimer.Reset(cfg.WeatherEvery)
		}
	}
}

// fetchWeatherOnline brings Wi-Fi up when power-saving, fetches, fixes a drifted clock from
// the server's Date header, and drops Wi-Fi again.
func fetchWeatherOnline(cfg Config) (Weather, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 75*time.Second)
	defer cancel()
	if cfg.WifiPowerSave && !wifiEnabled() {
		wifiSet(true)
		defer wifiSet(false)
	}
	if !waitConnected(ctx) {
		return Weather{}, fmt.Errorf("no Wi-Fi connection")
	}
	w, date, err := FetchWeather(ctx, cfg.Latitude, cfg.Longitude)
	if cfg.SyncClock && !date.IsZero() {
		if d := time.Since(date); d > 2*time.Minute || d < -2*time.Minute {
			log.Printf("clock off by %v, setting from server", d.Round(time.Second))
			if err := setClock(date); err != nil {
				log.Printf("set clock: %v", err)
			}
		}
	}
	return w, err
}
