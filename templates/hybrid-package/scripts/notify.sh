#!/usr/bin/env bash
# HOOK script -> package ROOT (scripts/notify.sh) because the hook JSON
# references it via ${PLUGIN_ROOT}/scripts/notify.sh. In the SAME hybrid the
# skill's script lives at .apm/skills/example-hybrid/scripts/run.sh. Two
# scripts/ directories, two rules:
#   - hook scripts -> package root scripts/   (${PLUGIN_ROOT}/scripts/x.sh)
#   - skill scripts -> nested under skill dir (file-relative scripts/x.sh)
#
# Self-gating, no `if` filter (the if matcher can silently no-match). The broad
# "Bash" matcher fires for every Bash call; this script decides scope itself.
set -u

payload="$(cat 2>/dev/null || true)"
[[ -z "$payload" ]] && exit 0

# Best-effort, read-only PostToolUse side effect. Exit 0 regardless so a failure
# here never blocks the tool result.
echo "example-hybrid hook: observed a Bash command" >&2
exit 0
