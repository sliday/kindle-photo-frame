//go:build linux

package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"
)

const (
	// Step pacing: each fade step stays on screen at least this long.
	minStep = 220 * time.Millisecond
	// At this charge on battery the frame shows a note and sleeps until the power button.
	lowBatteryPercent = 4
)

// runDevice is the frame's main loop on the Kindle. The launcher (run.sh) has already paused
// the stock UI and restores it after we return, whatever the reason.
//
// Deadlines are wall-clock times (see wallNow): in sleep mode the Kindle suspends between
// photos, and Go's monotonic timers don't count that time.
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
		was := frontlight()
		_ = setFrontlight(cfg.Frontlight)
		if was >= 0 {
			defer setFrontlight(was)
		}
	}
	wifiWasOn := wifiEnabled()
	defer func() {
		if wifiEnabled() != wifiWasOn {
			wifiSet(wifiWasOn)
		}
	}()
	sl := NewSleeper()
	log.Printf("power: mode %s, external power %v, battery %d%%, rtc %s",
		cfg.PowerMode, onExternalPower(), batteryPercent(), sl.Describe())

	show := func(path string) bool {
		for tries := 0; tries < 5; tries++ {
			img, err := LoadPhoto(path)
			if err == nil {
				if err := fr.SetPhoto(img); err != nil {
					log.Printf("display: %v", err)
				}
				log.Printf("photo %s (battery %d%%, external power %v)", path, batteryPercent(), onExternalPower())
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

	now := wallNow()
	var nextPhoto, nextWeather, holdUntil, ignorePowerUntil time.Time
	if cfg.PhotoInterval > 0 {
		nextPhoto = now.Add(cfg.PhotoInterval)
	}
	nextWeather = weather.Fetched.Round(0).Add(cfg.WeatherEvery)
	if nextWeather.Before(now.Add(5 * time.Second)) {
		nextWeather = now.Add(5 * time.Second)
	}
	awakeUntil := now.Add(cfg.AwakeAfter)
	refusals := 0

	fetch := func() {
		if fetching {
			return
		}
		fetching = true
		nextWeather = time.Time{} // set again when the result arrives
		go func() {
			w, err := fetchWeatherOnline(cfg)
			if err != nil {
				log.Printf("weather: %v", err)
			}
			weatherDone <- w
		}()
	}

	timer := time.NewTimer(time.Hour)
	defer timer.Stop()
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
		if weather.Fetched.IsZero() || time.Since(weather.Fetched.Round(0)) > weatherStale {
			return OverlayInfo{Clock: clock, Line: now.Format("Monday, 2 January")}
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
		holdUntil = wallNow().Add(cfg.Hold)
		drain()
	}
	hideOverlay := func() {
		holdUntil = time.Time{}
		if err := fr.HideOverlay(minStep); err != nil {
			log.Printf("overlay: %v", err)
		}
		drain()
	}
	changePhoto := func(path string) {
		holdUntil = time.Time{}
		show(path)
		if cfg.PhotoInterval > 0 {
			nextPhoto = wallNow().Add(cfg.PhotoInterval)
		}
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

	// woke handles the moments right after a suspend ends. Timing alone can't tell a press
	// near the alarm from the alarm, so a power key event right after resume wins.
	woke := func(timed bool, slept time.Duration) {
		select {
		case <-power:
			timed = false
		case <-time.After(400 * time.Millisecond):
		}
		now := wallNow()
		if timed {
			log.Printf("woke by alarm after %v", slept.Round(time.Second))
			awakeUntil = now // do the scheduled work, then sleep again
			return
		}
		log.Printf("woke by button after %v", slept.Round(time.Second))
		awakeUntil = now.Add(cfg.AwakeAfter)
		// the press that woke us may still arrive as an event; don't let it hide the clock
		ignorePowerUntil = now.Add(2 * time.Second)
		for len(power) > 0 {
			<-power
		}
		drain()
		showOverlay()
	}
	suspend := func() {
		if wifiEnabled() {
			wifiSet(false)
		}
		start := wallNow()
		if !nextPhoto.IsZero() {
			log.Printf("sleeping until %s", nextPhoto.In(loc).Format("15:04:05"))
		} else {
			log.Printf("sleeping until the power button")
		}
		timed, err := sl.SuspendUntil(nextPhoto)
		switch {
		case errors.Is(err, errTooSoon):
			awakeUntil = nextPhoto
		case err != nil:
			refusals++
			log.Printf("suspend failed (%d in a row): %v", refusals, err)
			awakeUntil = wallNow().Add(refusalBackoff(refusals))
		default:
			refusals = 0
			woke(timed, wallNow().Sub(start))
		}
	}
	lowBattery := func(p int) {
		log.Printf("battery %d%% on battery power: charge note, then sleep until the power button", p)
		if fr.visible {
			hideOverlay()
		}
		if err := fr.ShowOverlay(OverlayInfo{Clock: fmt.Sprintf("%d%%", p), Line: "Battery low · Please charge"}, minStep); err != nil {
			log.Printf("overlay: %v", err)
		}
		if wifiEnabled() {
			wifiSet(false)
		}
		start := wallNow()
		if _, err := sl.SuspendUntil(time.Time{}); err != nil {
			log.Printf("suspend failed: %v", err)
			awakeUntil = wallNow().Add(5 * time.Minute)
			return
		}
		log.Printf("woke after %v", wallNow().Sub(start).Round(time.Second))
		for len(power) > 0 {
			<-power
		}
		ignorePowerUntil = wallNow().Add(2 * time.Second)
		awakeUntil = wallNow().Add(cfg.AwakeAfter)
		hideOverlay()
	}

	for {
		// work that is due, in order: the overlay's hold, the photo, the weather
		now := wallNow()
		if due(holdUntil, now) {
			hideOverlay()
		}
		if due(nextPhoto, now) {
			if fr.visible {
				nextPhoto = now.Add(10 * time.Second)
			} else {
				changePhoto(pl.Next())
			}
		}
		if due(nextWeather, now) {
			fetch()
		}

		// then sleep, if this power mode wants it and nothing is in flight
		now = wallNow()
		sleepy := wantSleep(cfg.PowerMode, onExternalPower())
		// queued input first: a press or touch made during a fade must not be slept through.
		// Weather never wakes the Kindle by itself; it refreshes on photo and button wakes.
		idle := !fr.visible && !g.down && !fetching && len(power) == 0 && len(touches) == 0
		if sleepy && due(awakeUntil, now) && idle {
			if p := batteryPercent(); p >= 0 && p <= lowBatteryPercent && batteryPercent() <= lowBatteryPercent {
				lowBattery(p)
			} else {
				suspend()
			}
			continue
		}

		syncTick()
		next := earliest(nextPhoto, nextWeather, holdUntil)
		if sleepy {
			next = earliest(next, future(awakeUntil, now))
		}
		wait := time.Hour
		if !next.IsZero() {
			wait = max(0, min(time.Hour, next.Sub(now)))
		}
		timer.Reset(wait)

		select {
		case s := <-sigs:
			log.Printf("signal %v: leaving", s)
			return nil
		case t := <-touches:
			awakeUntil = wallNow().Add(cfg.AwakeAfter)
			if !act(g.Feed(t)) {
				return nil
			}
		case <-power:
			if wallNow().Before(ignorePowerUntil) {
				continue
			}
			awakeUntil = wallNow().Add(cfg.AwakeAfter)
			if !act(Tap) {
				return nil
			}
		case t := <-tick.C:
			if !act(g.Poll(t)) {
				return nil
			}
			if fr.visible {
				if err := fr.UpdateOverlay(info()); err != nil {
					log.Printf("overlay: %v", err)
				}
			}
		case w := <-weatherDone:
			fetching = false
			if w.Fetched.IsZero() {
				nextWeather = wallNow().Add(5 * time.Minute)
				continue
			}
			weather = w
			if err := saveWeather(cfg.StateDir, w); err != nil {
				log.Printf("save weather: %v", err)
			}
			nextWeather = wallNow().Add(cfg.WeatherEvery)
			if fr.visible {
				if err := fr.UpdateOverlay(info()); err != nil {
					log.Printf("overlay: %v", err)
				}
			}
		case <-timer.C:
			// the loop's top runs whatever came due
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
