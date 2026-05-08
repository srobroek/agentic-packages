#!/usr/bin/env bash
set -euo pipefail

if [ -f package.json ]; then
  if command -v pnpm >/dev/null 2>&1; then
    pnpm exec biome check . && pnpm exec tsc --noEmit
    exit 0
  fi
  if command -v bun >/dev/null 2>&1; then
    bunx biome check . && bunx tsc --noEmit
    exit 0
  fi
  if command -v npx >/dev/null 2>&1; then
    npx --yes biome check . && npx --yes tsc --noEmit
    exit 0
  fi
fi

echo "No supported TypeScript quality toolchain found." >&2
exit 1
