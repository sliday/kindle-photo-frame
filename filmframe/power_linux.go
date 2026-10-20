//go:build linux

package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
)

// Sleeper suspends the Kindle to RAM until an RTC alarm or the power button, the way
// PW4 kiosk projects do (wakealarm in relative form, then "mem" into /sys/power/state).
// The PW4 has two RTCs (the i.MX SNVS one and the BD71827 PMIC's); we arm every one that
// offers a wakealarm, so whichever can wake the SoC does.
type Sleeper struct {
	alarms []string
}

var (
	errTooSoon        = errors.New("next wake-up too close to bother sleeping")
	errNoAlarm        = errors.New("no RTC wake alarm on this device")
	errSuspendAborted = errors.New("kernel returned from suspend at once")
)

func NewSleeper() *Sleeper {
	s := &Sleeper{}
	for _, n := range []string{"rtc1", "rtc0"} {
		p := "/sys/class/rtc/" + n + "/wakealarm"
		if _, err := os.Stat(p); err == nil {
			s.alarms = append(s.alarms, p)
		}
	}
	return s
}

// Describe lists the RTCs for the log, so a failed wake can be traced to the right one.
func (s *Sleeper) Describe() string {
	dirs, _ := filepath.Glob("/sys/class/rtc/rtc*")
	var parts []string
	for _, d := range dirs {
		name, _ := os.ReadFile(filepath.Join(d, "name"))
		_, alarmErr := os.Stat(filepath.Join(d, "wakealarm"))
		parts = append(parts, fmt.Sprintf("%s=%s(wakealarm:%v)", filepath.Base(d),
			strings.TrimSpace(string(name)), alarmErr == nil))
	}
	return strings.Join(parts, " ")
}

// SuspendUntil sleeps until t (the zero time: until the power button) and reports whether
// the alarm ended the sleep.
func (s *Sleeper) SuspendUntil(t time.Time) (timed bool, err error) {
	start := wallNow()
	secs := 0
	if !t.IsZero() {
		secs = int(t.Sub(start) / time.Second)
		if secs < 10 {
			return false, errTooSoon
		}
		if len(s.alarms) == 0 {
			return false, errNoAlarm
		}
	}
	armed := 0
	for _, a := range s.alarms {
		_ = writeSys(a, "0")
		if secs > 0 && writeSys(a, "+"+strconv.Itoa(secs)) == nil {
			armed++
		}
	}
	if secs > 0 && armed == 0 {
		// without an alarm the photo would stay until someone pressed the button
		return false, errNoAlarm
	}
	syscall.Sync()
	err = writeSys("/sys/power/state", "mem")
	end := wallNow()
	for _, a := range s.alarms {
		_ = writeSys(a, "0")
	}
	if err != nil {
		return false, err
	}
	timed = !t.IsZero() && !end.Before(t.Add(-5*time.Second))
	if !timed && end.Sub(start) < 3*time.Second {
		return false, errSuspendAborted
	}
	return timed, nil
}

func writeSys(path, v string) error {
	f, err := os.OpenFile(path, os.O_WRONLY, 0)
	if err != nil {
		return err
	}
	_, werr := f.WriteString(v)
	cerr := f.Close()
	if werr != nil {
		return werr
	}
	return cerr
}

func readSys(path string) string {
	b, _ := os.ReadFile(path)
	return strings.TrimSpace(string(b))
}

// onExternalPower: USB from a charger or a computer.
func onExternalPower() bool {
	if readSys("/sys/class/power_supply/bd71827_ac/online") == "1" {
		return true
	}
	switch readSys("/sys/class/power_supply/bd71827_bat/status") {
	case "Charging", "Full":
		return true
	case "":
		return lipcGet("com.lab126.powerd", "isCharging") == "1"
	}
	return false
}

// batteryPercent is 0..100, or -1 when unreadable.
func batteryPercent() int {
	if n, err := strconv.Atoi(readSys("/sys/class/power_supply/bd71827_bat/capacity")); err == nil {
		return n
	}
	if n, err := strconv.Atoi(strings.TrimSuffix(lipcGet("com.lab126.powerd", "battLevel"), "%")); err == nil {
		return n
	}
	return -1
}

// frontlight is powerd's current light level, or -1.
func frontlight() int {
	if n, err := strconv.Atoi(lipcGet("com.lab126.powerd", "flIntensity")); err == nil {
		return n
	}
	return -1
}
