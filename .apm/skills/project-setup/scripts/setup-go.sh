#!/usr/bin/env bash
# shellcheck shell=bash
# setup-go — Go project overlay
#
# Adds Go tooling to a project scaffolded by project-setup.sh.
#
# Usage:
#   setup-go.sh [options]
#
# Options:
#   --module    Go module path (default: derived from git remote)
#   --help      Show this help

set -euo pipefail

MODULE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --module) MODULE="$2"; shift 2 ;;
        --help)
            sed -n '3,/^$/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# Derive module from git remote if not provided
if [ -z "$MODULE" ]; then
    REMOTE="$(git remote get-url origin 2>/dev/null || echo "")"
    if [ -n "$REMOTE" ]; then
        MODULE="$(echo "$REMOTE" | sed 's|https://||; s|\.git$||')"
    else
        MODULE="example.com/$(basename "$(pwd)")"
        echo "  WARN: No git remote, using $MODULE"
    fi
fi

echo "=== Go Setup ==="
echo "Module: $MODULE"

# --- Step 1: go mod init ---
if [ ! -f go.mod ]; then
    echo "Initializing Go module..."
    go mod init "$MODULE"
else
    echo "go.mod already exists"
fi

# --- Step 2: Standard Go layout ---
echo "Creating Go directory structure..."
mkdir -p cmd internal pkg

if [ ! -f cmd/main.go ]; then
    PROJECT_NAME="$(basename "$(pwd)")"
    cat > cmd/main.go <<GO
package main

import "fmt"

func main() {
	fmt.Println("$PROJECT_NAME")
}
GO
fi

# --- Step 3: golangci-lint config ---
if [ ! -f .golangci.yml ]; then
    echo "Creating .golangci.yml..."
    cat > .golangci.yml <<'YAML'
run:
  timeout: 5m

linters:
  enable:
    - errcheck
    - govet
    - ineffassign
    - staticcheck
    - unused
    - gosimple
    - gocritic
    - gofmt
    - goimports

linters-settings:
  gocritic:
    enabled-tags:
      - diagnostic
      - style
      - performance
YAML
fi

# --- Step 4: Append Go gitignore via gitnr ---
if ! grep -q '*.test' .gitignore 2>/dev/null; then
    echo "Appending Go gitignore..."
    if command -v gitnr >/dev/null 2>&1; then
        echo "" >> .gitignore
        gitnr create gh:Go >> .gitignore
    else
        cat >> .gitignore <<'GITIGNORE'

# Go
*.exe
*.exe~
*.dll
*.so
*.dylib
*.test
*.out
/vendor/
GITIGNORE
    fi
fi

echo ""
echo "=== Go setup complete ==="
