//go:build !linux

package main

import "errors"

func runDevice(Config) error {
	return errors.New("device mode runs on the Kindle only; use -preview here")
}
