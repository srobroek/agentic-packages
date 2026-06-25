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
        --module) MODULE="${2:?--module needs a value}"; shift 2 ;;
        --help)
            sed -n '3,/^$/p' "$0" | sed -E 's/^#[[:space:]]?//'
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# Derive module from git remote if not provided
if [ -z "$MODULE" ]; then
    REMOTE="$(git remote get-url origin 2>/dev/null || echo "")"
    if [ -n "$REMOTE" ]; then
        # Normalize https://, ssh://git@, and git@host:path remotes to host/path
        MODULE="$(echo "$REMOTE" | sed -e 's|^https://||' -e 's|^ssh://git@||' -e 's|^git@\([^:]*\):|\1/|' -e 's|\.git$||')"
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
write_go_gitignore_fallback() {
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
}

if ! grep -q '\*\.test' .gitignore 2>/dev/null; then
    echo "Appending Go gitignore..."
    # gitnr may be installed but still fail (network, template lookup). Capture
    # its output to a temp file and only append on success; otherwise fall back
    # to a static block so a present-but-failing gitnr never leaves a broken or
    # truncated .gitignore.
    _gi_tmp="$(mktemp "${TMPDIR:-/tmp}/gitignore.XXXXXX")"
    if command -v gitnr >/dev/null 2>&1 && gitnr create gh:Go > "$_gi_tmp" && [ -s "$_gi_tmp" ]; then
        printf '\n' >> .gitignore
        cat "$_gi_tmp" >> .gitignore
    else
        echo "  WARN: gitnr unavailable or failed; using static Go .gitignore"
        write_go_gitignore_fallback
    fi
    rm -f "$_gi_tmp"
fi

echo ""
echo "=== Go setup complete ==="
