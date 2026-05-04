#!/usr/bin/env bash
set -euo pipefail
exec "${XDG_CONFIG_HOME:-$HOME/.config}/agentic-tools/hooks/bash-guard.sh" "$@"
