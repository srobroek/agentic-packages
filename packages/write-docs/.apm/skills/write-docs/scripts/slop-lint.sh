#!/usr/bin/env bash
# Prose gate. Runs Vale against the WriteDocs house style plus the pinned
# vale-ai-tells package.
#
# Usage: slop-lint.sh [--genre consumer|change|internal] <file> [<file>...]
# Exit:  0 clean (warnings alone stay 0) · 1 any error · 2 usage or missing tool.
#
# The exit contract is this script's own, not Vale's: Vale exits non-zero on any
# alert at or above MinAlertLevel, which would fail on warnings too. We read the
# JSON and map severities ourselves.
#
# Genre selects the config, it does not filter. Per-path rules live in the
# section globs of vale/.vale.ini, which Vale applies from each file's own path.
# `--genre change` exists because commit messages and PR bodies have no stable
# path for a section glob to match.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
vale_dir="$here/../vale"
genre=""
files=()

while [ $# -gt 0 ]; do
  case "$1" in
    --genre)
      genre="${2:-}"
      case "$genre" in
        consumer | change | internal) ;;
        *)
          echo "slop-lint: --genre must be consumer, change, or internal" >&2
          exit 2
          ;;
      esac
      shift 2
      ;;
    -h | --help)
      sed -n '2,15p' "$0"
      exit 0
      ;;
    -*)
      echo "slop-lint: unknown option $1" >&2
      exit 2
      ;;
    *)
      files+=("$1")
      shift
      ;;
  esac
done

if [ "${#files[@]}" -eq 0 ]; then
  echo "slop-lint: no files given" >&2
  exit 2
fi

if ! command -v vale >/dev/null 2>&1; then
  echo "slop-lint: vale not found on PATH." >&2
  echo "  install: mise use -g vale   (or: brew install vale)" >&2
  echo "  then:    vale --config='$vale_dir/.vale.ini' sync" >&2
  exit 2
fi

config="$vale_dir/.vale.ini"
if [ "$genre" = "change" ] && [ -f "$vale_dir/.vale-change.ini" ]; then
  config="$vale_dir/.vale-change.ini"
fi

if [ ! -f "$config" ]; then
  echo "slop-lint: config not found at $config" >&2
  exit 2
fi

# The house style is committed; the packaged style is fetched by `vale sync`.
# Fail with an actionable message rather than silently linting half a config.
if [ ! -d "$vale_dir/styles/ai-tells" ]; then
  echo "slop-lint: packaged styles missing. Run:" >&2
  echo "  vale --config='$config' sync" >&2
  exit 2
fi

vale --config="$config" --output=JSON --no-exit "${files[@]}" 2>/dev/null |
  python3 "$here/vale-report.py"
