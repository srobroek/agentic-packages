#!/usr/bin/env bash
set -euo pipefail

payload="$(cat 2>/dev/null || true)"
command -v jq >/dev/null 2>&1 || exit 0

command="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
if ! printf '%s' "$command" | grep -Eq '(^|[[:space:]])git([[:space:]][^;&|]*)?[[:space:]]+commit($|[[:space:]])'; then
  exit 0
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$repo_root" ]] || exit 0
cd "$repo_root"

deny() {
  local reason="$1"
  jq -cn --arg reason "$reason" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

selected_file=".agents/hooks/quality-languages"
selected=""
if [[ -f "$selected_file" ]]; then
  selected="$(tr '\n' ' ' < "$selected_file" | tr ',' ' ')"
elif [[ -n "${AGENTIC_QUALITY_LANGS:-}" ]]; then
  selected="${AGENTIC_QUALITY_LANGS//,/ }"
else
  # Conservative fallback for older projects. Only enable when clear project
  # markers exist; unknown projects should not be blocked by this hook.
  [[ -f go.mod ]] && selected="$selected go"
  [[ -f pyproject.toml ]] && selected="$selected python"
  [[ -f Cargo.toml ]] && selected="$selected rust"
  [[ -f package.json ]] && selected="$selected ts"
fi

has_lang() {
  local wanted="$1"
  printf ' %s ' "$selected" | grep -Eq " (all|$wanted) "
}

# Compute once: every language block reuses this, instead of re-running
# git diff per block (the hook fires on every commit attempt).
all_changed="$(
  git diff --cached --name-only --diff-filter=ACMR
  git diff --name-only --diff-filter=ACMR
)"

changed_files() {
  printf '%s\n' "$all_changed"
}

if has_lang go; then
  if command -v gofmt >/dev/null 2>&1; then
    mapfile -t go_files < <(changed_files | grep -E '\.go$' | sort -u)
    if [[ "${#go_files[@]}" -gt 0 ]]; then
      bad="$(gofmt -l "${go_files[@]}" 2>/dev/null || true)"
      [[ -z "$bad" ]] || deny "Go formatting is required before commit. Run: gofmt -w ${bad//$'\n'/ }"
    fi
  fi
fi

if has_lang python; then
  mapfile -t py_files < <(changed_files | grep -E '\.pyi?$' | sort -u)
  if [[ "${#py_files[@]}" -gt 0 ]]; then
    if command -v uv >/dev/null 2>&1 && [[ -f pyproject.toml ]]; then
      uv run ruff check "${py_files[@]}" >/tmp/agentic-ruff-check.log 2>&1 || deny "Python Ruff check failed before commit. Run: uv run ruff check --fix"
      uv run ruff format --check "${py_files[@]}" >/tmp/agentic-ruff-format.log 2>&1 || deny "Python Ruff format failed before commit. Run: uv run ruff format"
    elif command -v ruff >/dev/null 2>&1; then
      ruff check "${py_files[@]}" >/tmp/agentic-ruff-check.log 2>&1 || deny "Python Ruff check failed before commit. Run: ruff check --fix"
      ruff format --check "${py_files[@]}" >/tmp/agentic-ruff-format.log 2>&1 || deny "Python Ruff format failed before commit. Run: ruff format"
    fi
  fi
fi

if has_lang rust; then
  if command -v cargo >/dev/null 2>&1 && [[ -f Cargo.toml ]]; then
    if changed_files | grep -qE '\.rs$|Cargo\.toml$'; then
      cargo fmt --all -- --check >/tmp/agentic-cargo-fmt.log 2>&1 || deny "Rust formatting is required before commit. Run: cargo fmt --all"
    fi
  fi
fi

if has_lang ts || has_lang javascript || has_lang typescript; then
  mapfile -t js_files < <(changed_files | grep -E '\.(ts|tsx|js|jsx|mjs|cjs|vue|svelte)$' | sort -u)
  if [[ "${#js_files[@]}" -gt 0 ]]; then
    if [[ -f biome.json || -f biome.jsonc ]] || grep -q '"@biomejs/biome"\|"biome"' package.json 2>/dev/null; then
      if command -v bunx >/dev/null 2>&1; then
        bunx --bun biome check "${js_files[@]}" >/tmp/agentic-biome.log 2>&1 || deny "Biome check failed before commit. Run: bunx --bun biome check --write"
      elif command -v pnpm >/dev/null 2>&1; then
        pnpm exec biome check "${js_files[@]}" >/tmp/agentic-biome.log 2>&1 || deny "Biome check failed before commit. Run: pnpm exec biome check --write"
      elif command -v npx >/dev/null 2>&1; then
        npx biome check "${js_files[@]}" >/tmp/agentic-biome.log 2>&1 || deny "Biome check failed before commit. Run: npx biome check --write"
      fi
    fi
  fi
fi

exit 0
