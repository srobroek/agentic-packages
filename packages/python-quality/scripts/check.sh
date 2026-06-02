#!/usr/bin/env bash
set -euo pipefail

ruff check .
ruff format --check .

if command -v pyright >/dev/null 2>&1; then
  pyright
fi

if [ -f pyproject.toml ] || [ -d tests ]; then
  if command -v pytest >/dev/null 2>&1; then
    pytest
  fi
fi

