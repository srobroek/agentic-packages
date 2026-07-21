#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FORMULA_NAMES=(
  speckit-feature.formula.toml
  mol-speckit-fix-findings.formula.toml
  mol-speckit-iterate.formula.toml
)

find_formula_dir() {
  local cand
  for cand in \
    "${SPECKIT_FORMULA_DIR:-}" \
    "$HOME/.apm/apm_modules/srobroek/agentic-packages/packages/speckit/formulas" \
    "$HOME/.claude/plugins/agentic-packages-speckit/formulas" \
    "$SCRIPT_DIR/../../../../formulas"; do
    if [ -n "$cand" ] && [ -f "$cand/speckit-feature.formula.toml" ]; then
      printf '%s\n' "$cand"
      return 0
    fi
  done

  # Native plugin caches add marketplace, plugin, and version directories.
  # An unmatched glob remains literal and fails the file check safely.
  for cand in \
    "$HOME"/.claude/plugins/cache/*/speckit/*/formulas \
    "$HOME"/.codex/plugins/cache/*/speckit/*/formulas; do
    if [ -f "$cand/speckit-feature.formula.toml" ]; then
      printf '%s\n' "$cand"
      return 0
    fi
  done
  return 1
}

if [ "${1:-}" = "--print-source" ]; then
  find_formula_dir
  exit
fi

FORMULA_DIR="$(find_formula_dir)" || {
  echo "ERROR: packaged speckit formulas not found; install the speckit package with APM, then re-run" >&2
  exit 1
}

mkdir -p .beads/formulas
for FORMULA_NAME in "${FORMULA_NAMES[@]}"; do
  FORMULA_SRC="$FORMULA_DIR/$FORMULA_NAME"
  [ -f "$FORMULA_SRC" ] || {
    echo "ERROR: packaged formula missing: $FORMULA_SRC" >&2
    exit 1
  }
  FORMULA_DEST=".beads/formulas/$FORMULA_NAME"
  FORMULA_TMP="$(mktemp "$FORMULA_DEST.tmp.XXXXXX")"
  if cp "$FORMULA_SRC" "$FORMULA_TMP" && mv -f "$FORMULA_TMP" "$FORMULA_DEST"; then
    echo "    + $FORMULA_DEST"
  else
    rm -f "$FORMULA_TMP"
    echo "ERROR: failed to install $FORMULA_DEST" >&2
    exit 1
  fi
done

for FORMULA_ID in speckit-feature mol-speckit-fix-findings mol-speckit-iterate; do
  if ! bd formula show "$FORMULA_ID" --json >/dev/null 2>&1; then
    echo "ERROR: formula $FORMULA_ID is not parseable; bd >= 1.1.0 is required" >&2
    exit 1
  fi
done
if ! bd mol pour speckit-feature --var feature=000-setup-validation --dry-run >/dev/null 2>&1; then
  echo "ERROR: speckit-feature formula failed dry-run expansion" >&2
  exit 1
fi
echo "    formulas installed project-locally, parsed, and dry-run validated"
