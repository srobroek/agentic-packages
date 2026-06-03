#!/usr/bin/env bash
set -euo pipefail

if [ -f package.json ]; then
  if command -v pnpm >/dev/null 2>&1; then
    pnpm exec biome check --write .
    exit 0
  fi
  if command -v bun >/dev/null 2>&1; then
    bunx biome check --write .
    exit 0
  fi
  if command -v npx >/dev/null 2>&1; then
    npx --yes biome check --write .
    exit 0
  fi
fi

echo "No supported TypeScript fixer found." >&2
exit 1
