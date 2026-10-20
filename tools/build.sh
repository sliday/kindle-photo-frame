#!/bin/bash
# Test, then cross-compile filmframe for the Kindle (static ARMv7, runs on soft- and hard-float firmware).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT/filmframe"
go vet .
GOOS=linux GOARCH=arm GOARM=7 CGO_ENABLED=0 go vet .
go test ./...
mkdir -p "$ROOT/dist"
GOOS=linux GOARCH=arm GOARM=7 CGO_ENABLED=0 \
	go build -trimpath -ldflags "-s -w -X main.version=$(date +%Y%m%d)-$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo dev)" \
	-o "$ROOT/dist/filmframe" .
file "$ROOT/dist/filmframe"
