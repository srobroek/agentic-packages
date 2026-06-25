#!/usr/bin/env bash
# shellcheck shell=bash
# package-add — Add a package to a monorepo
#
# Creates a package directory, runs the language overlay inside it,
# and prints workspace registration steps.
#
# Usage:
#   package-add.sh --name <name> --lang <lang> [options]
#
# Options:
#   --name        Package name (required)
#   --lang        Language: ts, rust, python, go (required)
#   --dir         Packages directory (default: packages/)
#   --lang-args   Extra args for the language overlay (quoted string)
#   --help        Show this help
#
# Examples:
#   package-add.sh --name web --lang ts --lang-args "--framework nuxt --sst"
#   package-add.sh --name api --lang python
#   package-add.sh --name core --lang rust --dir crates/

set -euo pipefail

PKG_NAME=""
# Note: not named LANG to avoid clobbering the exported locale variable.
PKG_LANG=""
PKG_DIR="packages"
LANG_ARGS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --name)      PKG_NAME="${2:?--name needs a value}"; shift 2 ;;
        --lang)      PKG_LANG="${2:?--lang needs a value}"; shift 2 ;;
        --dir)       PKG_DIR="${2:?--dir needs a value}"; shift 2 ;;
        --lang-args) LANG_ARGS="${2:?--lang-args needs a value}"; shift 2 ;;
        --help)
            sed -n '3,/^$/p' "$0" | sed -E 's/^#[[:space:]]?//'
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$PKG_NAME" ]; then
    echo "Error: --name is required" >&2
    exit 1
fi

# Reject path-traversal / absolute names before any mkdir. The package name is
# later interpolated into "$ROOT/$PKG_DIR/$PKG_NAME"; a name containing a slash,
# a ".." component, or a leading "/" could escape the packages directory and
# create or overwrite files anywhere on disk.
case "$PKG_NAME" in
    */*|*\\*)
        echo "Error: --name must not contain a path separator: $PKG_NAME" >&2
        exit 1
        ;;
    ..|.|"")
        echo "Error: --name must be a plain package name: $PKG_NAME" >&2
        exit 1
        ;;
esac
case "$PKG_NAME" in
    *..*)
        echo "Error: --name must not contain '..': $PKG_NAME" >&2
        exit 1
        ;;
esac

if [ -z "$PKG_LANG" ]; then
    echo "Error: --lang is required (ts, rust, python, go)" >&2
    exit 1
fi

# Validate the language against the known overlay set before creating the dir,
# so an unknown --lang fails fast instead of leaving an empty package directory
# behind when the overlay script is missing.
case "$PKG_LANG" in
    ts|rust|python|go) ;;
    *)
        echo "Error: --lang must be one of: ts, rust, python, go (got: $PKG_LANG)" >&2
        exit 1
        ;;
esac

# --- Find monorepo root ---
# Walk up until we find a workspace marker
find_root() {
    local dir="$1"
    while [ "$dir" != "/" ]; do
        # JS/TS workspaces
        if [ -f "$dir/package.json" ] && grep -q '"workspaces"' "$dir/package.json" 2>/dev/null; then
            echo "$dir"; return
        fi
        # Cargo workspace
        if [ -f "$dir/Cargo.toml" ] && grep -q '\[workspace\]' "$dir/Cargo.toml" 2>/dev/null; then
            echo "$dir"; return
        fi
        # uv workspace
        if [ -f "$dir/pyproject.toml" ] && grep -q '\[tool.uv.workspace\]' "$dir/pyproject.toml" 2>/dev/null; then
            echo "$dir"; return
        fi
        # Go workspace
        if [ -f "$dir/go.work" ]; then
            echo "$dir"; return
        fi
        # Generic monorepo marker (justfile at root with packages/ dir)
        if [ -f "$dir/justfile" ] && [ -d "$dir/packages" ]; then
            echo "$dir"; return
        fi
        dir="$(dirname "$dir")"
    done
    echo ""
}

ROOT="$(find_root "$(pwd)")"
if [ -z "$ROOT" ]; then
    echo "WARN: No monorepo root detected. Using current directory."
    ROOT="$(pwd)"
fi

TARGET="$ROOT/$PKG_DIR/$PKG_NAME"

echo "=== Adding Package: $PKG_NAME ==="
echo "Root: $ROOT"
echo "Target: $TARGET"
echo "Language: $PKG_LANG"

# --- Create package directory ---
if [ -d "$TARGET" ]; then
    echo "Directory already exists: $TARGET"
else
    mkdir -p "$TARGET"
    echo "Created: $TARGET"
fi

# --- Run language overlay ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LANG_SCRIPT="$SCRIPT_DIR/setup-${PKG_LANG}.sh"

if [ ! -x "$LANG_SCRIPT" ]; then
    echo "Error: $LANG_SCRIPT not found or not executable" >&2
    exit 1
fi

echo ""
echo "Running setup-${PKG_LANG}.sh in $TARGET..."
cd "$TARGET"
# shellcheck disable=SC2086
"$LANG_SCRIPT" $LANG_ARGS

# --- Print workspace registration steps ---
echo ""
echo "=== Manual steps needed ==="
echo ""

REL_PATH="$PKG_DIR/$PKG_NAME"

case "$PKG_LANG" in
    ts)
        echo "Add to root package.json workspaces:"
        echo "  \"workspaces\": [\"$REL_PATH\"]"
        echo ""
        echo "Or if using bun:"
        echo "  \"workspaces\": [\"$PKG_DIR/*\"]"
        ;;
    rust)
        echo "Add to root Cargo.toml:"
        echo "  [workspace]"
        echo "  members = [\"$REL_PATH\"]"
        ;;
    python)
        echo "Add to root pyproject.toml:"
        echo "  [tool.uv.workspace]"
        echo "  members = [\"$REL_PATH\"]"
        ;;
    go)
        echo "Add to go.work (create with 'go work init' if needed):"
        echo "  use ./$REL_PATH"
        ;;
esac

echo ""
echo "Then update the root justfile to include $PKG_NAME targets."
echo ""
echo "=== Package $PKG_NAME added ==="
