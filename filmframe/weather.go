package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

// Weather is the cached current conditions from Open-Meteo (no API key needed).
type Weather struct {
	TempC   float64   `json:"temp_c"`
	Code    int       `json:"code"`
	IsDay   bool      `json:"is_day"`
	Fetched time.Time `json:"fetched"`
}

// weatherStale is how old a reading may get before the overlay shows the date instead.
const weatherStale = 3 * time.Hour

// FetchWeather asks Open-Meteo for current conditions. It also returns the server's Date
// header so a Kindle with a drifted clock can correct itself.
func FetchWeather(ctx context.Context, lat, lon float64) (Weather, time.Time, error) {
	url := fmt.Sprintf("https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f"+
		"&current=temperature_2m,weather_code,is_day&timezone=auto", lat, lon)
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return Weather{}, time.Time{}, err
	}
	req.Header.Set("User-Agent", "filmframe/1 (Kindle photo frame)")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return Weather{}, time.Time{}, err
	}
	defer resp.Body.Close()
	date, _ := http.ParseTime(resp.Header.Get("Date"))
	if resp.StatusCode != 200 {
		return Weather{}, date, fmt.Errorf("open-meteo: %s", resp.Status)
	}
	var body struct {
		Current struct {
			Temp  float64 `json:"temperature_2m"`
			Code  int     `json:"weather_code"`
			IsDay int     `json:"is_day"`
		} `json:"current"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		return Weather{}, date, err
	}
	return Weather{TempC: body.Current.Temp, Code: body.Current.Code,
		IsDay: body.Current.IsDay == 1, Fetched: wallNow()}, date, nil
}

func loadWeather(stateDir string) (w Weather) {
	b, err := os.ReadFile(filepath.Join(stateDir, "weather.json"))
	if err == nil {
		_ = json.Unmarshal(b, &w)
	}
	return w
}

func saveWeather(stateDir string, w Weather) error {
	b, _ := json.Marshal(w)
	return writeFileAtomic(filepath.Join(stateDir, "weather.json"), b)
}

// wmoText turns a WMO weather code into the short sentence-case phrase the overlay shows.
func wmoText(code int) string {
	switch code {
	case 0:
		return "Clear"
	case 1:
		return "Mostly clear"
	case 2:
		return "Partly cloudy"
	case 3:
		return "Cloudy"
	case 45, 48:
		return "Fog"
	case 51, 53, 55:
		return "Drizzle"
	case 56, 57:
		return "Freezing drizzle"
	case 61:
		return "Light rain"
	case 63:
		return "Rain"
	case 65:
		return "Heavy rain"
	case 66, 67:
		return "Freezing rain"
	case 71:
		return "Light snow"
	case 73:
		return "Snow"
	case 75:
		return "Heavy snow"
	case 77:
		return "Snow grains"
	case 80, 81:
		return "Showers"
	case 82:
		return "Heavy showers"
	case 85, 86:
		return "Snow showers"
	case 95:
		return "Thunderstorm"
	case 96, 99:
		return "Thunderstorm, hail"
	}
	return "—"
}

// wmoIcon picks the Lucide icon for a WMO code.
func wmoIcon(code int, day bool) string {
	switch {
	case code <= 1 && day:
		return "sun"
	case code <= 1:
		return "moon"
	case code == 2 && day:
		return "cloud-sun"
	case code == 2:
		return "cloud-moon"
	case code == 3:
		return "cloud"
	case code == 45 || code == 48:
		return "cloud-fog"
	case code >= 51 && code <= 57:
		return "cloud-drizzle"
	case code >= 61 && code <= 67, code >= 80 && code <= 82:
		return "cloud-rain"
	case code >= 71 && code <= 77, code == 85 || code == 86:
		return "cloud-snow"
	case code >= 95:
		return "cloud-lightning"
	}
	return "cloud"
}

func writeFileAtomic(path string, b []byte) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, b, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}
