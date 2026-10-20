//go:build linux

package main

import (
	"context"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"syscall"
	"time"
)

// Thin wrappers over the Kindle's lipc tools. Failures are logged by callers, never fatal:
// the frame should keep showing photos even if a property goes missing in some firmware.

func lipcSet(args ...string) error {
	return exec.Command("lipc-set-prop", args...).Run()
}

func lipcGet(args ...string) string {
	out, _ := exec.Command("lipc-get-prop", args...).Output()
	return strings.TrimSpace(string(out))
}

func preventScreenSaver(on bool) error {
	v := "0"
	if on {
		v = "1"
	}
	return lipcSet("com.lab126.powerd", "preventScreenSaver", v)
}

func wifiEnabled() bool { return lipcGet("com.lab126.cmd", "wirelessEnable") == "1" }

// wifiSet follows KOReader: radio first, then wifid when turning on; reverse when off.
func wifiSet(on bool) {
	if on {
		_ = lipcSet("com.lab126.cmd", "wirelessEnable", "1")
		_ = lipcSet("-i", "com.lab126.wifid", "enable", "1")
	} else {
		_ = lipcSet("-i", "com.lab126.wifid", "enable", "0")
		_ = lipcSet("com.lab126.cmd", "wirelessEnable", "0")
	}
}

func wifiConnected() bool { return lipcGet("com.lab126.wifid", "cmState") == "CONNECTED" }

func waitConnected(ctx context.Context) bool {
	for {
		if wifiConnected() {
			return true
		}
		select {
		case <-ctx.Done():
			return false
		case <-time.After(time.Second):
		}
	}
}

func setFrontlight(level int) error {
	return lipcSet("com.lab126.powerd", "flIntensity", strconv.Itoa(level))
}

// setClock moves the system clock (UTC) and the RTC. KOReader uses Amazon's setdate.
func setClock(t time.Time) error {
	if _, err := os.Stat("/usr/sbin/setdate"); err == nil {
		return exec.Command("/usr/sbin/setdate", strconv.FormatInt(t.Unix(), 10)).Run()
	}
	tv := syscall.NsecToTimeval(t.UnixNano())
	if err := syscall.Settimeofday(&tv); err != nil {
		return err
	}
	return exec.Command("hwclock", "-u", "-w").Run()
}
