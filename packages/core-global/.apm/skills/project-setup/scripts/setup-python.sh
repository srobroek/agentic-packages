#!/usr/bin/env bash
# shellcheck shell=bash
# setup-python — Python project overlay
#
# Adds Python tooling to a project scaffolded by project-setup.sh.
# Uses uv as package manager.
#
# Usage:
#   setup-python.sh [options]
#
# Options:
#   --python    Python version (default: 3.13)
#   --help      Show this help

set -euo pipefail

PYTHON_VERSION="3.13"

while [[ $# -gt 0 ]]; do
    case $1 in
        --python) PYTHON_VERSION="$2"; shift 2 ;;
        --help)
            sed -n '3,/^$/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

echo "=== Python Setup ==="
echo "Python version: $PYTHON_VERSION"

# --- Step 1: uv init ---
if [ ! -f pyproject.toml ]; then
    echo "Initializing uv project..."
    uv init --python "$PYTHON_VERSION"
else
    echo "pyproject.toml already exists"
fi

# --- Step 2: Create src layout ---
PROJECT_NAME="$(basename "$(pwd)")"
SRC_DIR="src/${PROJECT_NAME//-/_}"
if [ ! -d "$SRC_DIR" ]; then
    echo "Creating src layout..."
    mkdir -p "$SRC_DIR"
    [ -f "$SRC_DIR/__init__.py" ] || touch "$SRC_DIR/__init__.py"
fi

# --- Step 3: Ruff config ---
if ! grep -q 'ruff' pyproject.toml 2>/dev/null; then
    echo "Adding ruff config to pyproject.toml..."
    cat >> pyproject.toml <<'TOML'

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "TCH"]

[tool.ruff.format]
quote-style = "double"
TOML
fi

# --- Step 4: Add dev dependencies ---
echo "Adding dev dependencies..."
uv add --dev ruff pytest

# --- Step 5: Append Python gitignore via gitnr ---
if ! grep -q '__pycache__' .gitignore 2>/dev/null; then
    echo "Appending Python gitignore..."
    if command -v gitnr >/dev/null 2>&1; then
        echo "" >> .gitignore
        gitnr create gh:Python >> .gitignore
    else
        cat >> .gitignore <<'GITIGNORE'

# Python
__pycache__
*.py[cod]
*.egg-info
dist
build
.venv
.pytest_cache
.ruff_cache
GITIGNORE
    fi
fi

echo ""
echo "=== Python setup complete ==="
