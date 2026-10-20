package main

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

// Config holds every knob from filmframe.conf. Unknown keys are reported, not fatal.
type Config struct {
	PhotoDir      string
	StateDir      string
	Order         string // shuffle | random | name
	PhotoInterval time.Duration
	Hold          time.Duration
	Latitude      float64
	Longitude     float64
	Timezone      string
	Fahrenheit    bool
	Clock12h      bool
	WeatherEvery  time.Duration
	WifiPowerSave bool
	SyncClock     bool
	Frontlight    int // -1 leaves the light alone
	FBInk         string
	FadeWaveform  string
	TouchDevice   string
	TouchSwapXY   bool
	TouchMirrorX  bool
	TouchMirrorY  bool
	LongPress     time.Duration
}

func DefaultConfig() Config {
	return Config{
		PhotoDir:      "/mnt/us/filmframe/photos",
		StateDir:      "/mnt/us/filmframe/state",
		Order:         "shuffle",
		PhotoInterval: 30 * time.Minute,
		Hold:          6 * time.Second,
		Latitude:      51.5072,
		Longitude:     -0.1276,
		Timezone:      "Europe/London",
		WeatherEvery:  30 * time.Minute,
		WifiPowerSave: true,
		SyncClock:     true,
		Frontlight:    -1,
		FBInk:         "auto",
		FadeWaveform:  "GC16",
		TouchDevice:   "auto",
		LongPress:     3 * time.Second,
	}
}

// LoadConfig reads "key = value" lines; '#' starts a comment. A missing file means defaults.
func LoadConfig(path string) (Config, error) {
	c := DefaultConfig()
	f, err := os.Open(path)
	if os.IsNotExist(err) {
		return c, nil
	}
	if err != nil {
		return c, err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	for n := 1; sc.Scan(); n++ {
		line := sc.Text()
		if i := strings.IndexByte(line, '#'); i >= 0 {
			line = line[:i]
		}
		k, v, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		k, v = strings.TrimSpace(strings.ToLower(k)), strings.TrimSpace(v)
		if err := c.set(k, v); err != nil {
			return c, fmt.Errorf("%s:%d: %s: %w", path, n, k, err)
		}
	}
	return c, sc.Err()
}

func (c *Config) set(k, v string) error {
	var err error
	switch k {
	case "photo_dir":
		c.PhotoDir = v
	case "state_dir":
		c.StateDir = v
	case "order":
		switch v {
		case "shuffle", "random", "name":
			c.Order = v
		default:
			return fmt.Errorf("want shuffle, random or name, got %q", v)
		}
	case "photo_minutes":
		c.PhotoInterval, err = minutes(v)
	case "hold_seconds":
		var s float64
		s, err = strconv.ParseFloat(v, 64)
		c.Hold = time.Duration(s * float64(time.Second))
	case "latitude":
		c.Latitude, err = strconv.ParseFloat(v, 64)
	case "longitude":
		c.Longitude, err = strconv.ParseFloat(v, 64)
	case "timezone":
		_, err = time.LoadLocation(v)
		c.Timezone = v
	case "units":
		c.Fahrenheit = strings.HasPrefix(strings.ToLower(v), "f")
	case "clock":
		c.Clock12h = strings.HasPrefix(v, "12")
	case "weather_minutes":
		c.WeatherEvery, err = minutes(v)
	case "wifi_power_save":
		c.WifiPowerSave, err = strconv.ParseBool(v)
	case "sync_clock":
		c.SyncClock, err = strconv.ParseBool(v)
	case "frontlight":
		c.Frontlight, err = strconv.Atoi(v)
	case "fbink":
		c.FBInk = v
	case "fade_waveform":
		c.FadeWaveform = strings.ToUpper(v)
	case "touch_device":
		c.TouchDevice = v
	case "touch_swap_xy":
		c.TouchSwapXY, err = strconv.ParseBool(v)
	case "touch_mirror_x":
		c.TouchMirrorX, err = strconv.ParseBool(v)
	case "touch_mirror_y":
		c.TouchMirrorY, err = strconv.ParseBool(v)
	case "long_press_seconds":
		var s float64
		s, err = strconv.ParseFloat(v, 64)
		c.LongPress = time.Duration(s * float64(time.Second))
	default:
		fmt.Fprintf(os.Stderr, "config: unknown key %q ignored\n", k)
	}
	return err
}

func minutes(v string) (time.Duration, error) {
	m, err := strconv.ParseFloat(v, 64)
	return time.Duration(m * float64(time.Minute)), err
}
