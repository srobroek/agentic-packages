#!/usr/bin/env bash
set -euo pipefail

gofmt -l . | (! grep .)

if command -v golangci-lint >/dev/null 2>&1; then
  golangci-lint run
fi

go test ./...

