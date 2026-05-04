#!/usr/bin/env bash
set -euo pipefail

ran=0

run_cmd() {
  local label="$1"
  shift
  echo "==> $label"
  "$@"
  ran=1
}

if [ -f package.json ]; then
  if command -v pnpm >/dev/null 2>&1; then
    [ -f tsconfig.json ] && run_cmd "TypeScript check" pnpm exec tsc --noEmit || true
    run_cmd "Biome check" pnpm exec biome check . || true
    run_cmd "Tests" pnpm test || true
    if jq -e '.scripts.build' package.json >/dev/null 2>&1; then
      run_cmd "Build" pnpm build || true
    fi
  elif command -v bun >/dev/null 2>&1; then
    [ -f tsconfig.json ] && run_cmd "TypeScript check" bunx tsc --noEmit || true
    run_cmd "Biome check" bunx biome check . || true
    run_cmd "Tests" bun test || true
    if jq -e '.scripts.build' package.json >/dev/null 2>&1; then
      run_cmd "Build" bun run build || true
    fi
  elif command -v npm >/dev/null 2>&1; then
    [ -f tsconfig.json ] && run_cmd "TypeScript check" npm run typecheck || true
    run_cmd "Lint" npm run lint || true
    run_cmd "Tests" npm test || true
    if jq -e '.scripts.build' package.json >/dev/null 2>&1; then
      run_cmd "Build" npm run build || true
    fi
  fi
fi

if [ -f Cargo.toml ]; then
  run_cmd "cargo fmt" cargo fmt --check || true
  run_cmd "cargo clippy" cargo clippy --all-targets --all-features -- -D warnings || true
  run_cmd "cargo test" cargo test || true
fi

if [ -f go.mod ]; then
  command -v golangci-lint >/dev/null 2>&1 && run_cmd "golangci-lint" golangci-lint run || true
  run_cmd "go test" go test ./... || true
  run_cmd "go build" go build ./... || true
fi

if [ -f pyproject.toml ] || [ -f requirements.txt ]; then
  command -v ruff >/dev/null 2>&1 && run_cmd "ruff check" ruff check . || true
  command -v ruff >/dev/null 2>&1 && run_cmd "ruff format" ruff format --check . || true
  command -v pyright >/dev/null 2>&1 && run_cmd "pyright" pyright . || true
  command -v pytest >/dev/null 2>&1 && run_cmd "pytest" pytest || true
fi

if [ "$ran" -eq 0 ]; then
  echo "No supported verification workflow detected." >&2
  exit 1
fi
