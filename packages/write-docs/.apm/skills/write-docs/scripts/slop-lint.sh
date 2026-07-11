#!/usr/bin/env bash
# Thin wrapper so the skill can say `scripts/slop-lint.sh [--genre g] <file>` uniformly.
exec python3 "$(dirname "$0")/slop-lint.py" "$@"
