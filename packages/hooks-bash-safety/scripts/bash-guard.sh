#!/usr/bin/env bash
set -euo pipefail

# Read the hook payload from stdin. If Codex did not send a payload or if the
# payload does not contain a shell command, the hook has nothing to evaluate.
payload="$(cat)"
if [[ -z "$payload" ]]; then
  exit 0
fi

command="$(
  printf '%s' "$payload" | jq -r '
    if (.tool_input|type)=="string" then .tool_input
    else (.tool_input.command // empty) end
  ' 2>/dev/null || true
)"

if [[ -z "$command" || "$command" == "null" ]]; then
  exit 0
fi

# Normalize case once so the policy checks below can stay simple.
lowered="$(printf '%s' "$command" | tr '[:upper:]' '[:lower:]')"

deny() {
  jq -cn --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

# Regex fragments shared by the checks below.
curl_pipe_pattern='curl[[:space:]].*\|[[:space:]]*(sh|bash)'
wget_pipe_pattern='wget[[:space:]].*\|[[:space:]]*(sh|bash)'

# Block privilege escalation and explicit sandbox bypass attempts. Those should
# always require deliberate human intent instead of model autonomy.
if [[ "$lowered" =~ (^|[[:space:]]|[;\&|])sudo([[:space:]]|$) ]]; then
  deny "refusing sudo from Codex; request explicit approval instead"
fi

if [[ "$lowered" =~ --dangerously-bypass-approvals-and-sandbox ]]; then
  deny "refusing approval and sandbox bypass flags"
fi

# Block classic remote-code-execution shell patterns.
if [[ "$lowered" =~ $curl_pipe_pattern ]]; then
  deny "refusing curl pipe to shell"
fi

if [[ "$lowered" =~ $wget_pipe_pattern ]]; then
  deny "refusing wget pipe to shell"
fi

# Deny a small set of obviously destructive filesystem operations outright.
#
# Match the root target in its catastrophic forms: a bare `/`, the doubled `//`,
# and the glob `/*` (`rm -rf /*` wipes everything under root just like `rm -rf
# /`). The trailing `[/*]*` also tolerates `rm -rf /` followed by a slash/glob.
if [[ "$lowered" =~ (^|[[:space:]])rm[[:space:]]+-rf[[:space:]]+/[/*]*($|[[:space:]]) ]]; then
  deny "refusing rm -rf /"
fi

# Home directory in all the forms a model might emit: the literal `~`, and the
# un-expanded `$home`/`${home}` (lowercased from $HOME/${HOME} by tr above).
if [[ "$lowered" =~ (^|[[:space:]])rm[[:space:]]+-rf[[:space:]]+(~|\$home|\$\{home\})(/|$|[[:space:]]) ]]; then
  deny "refusing rm -rf on home"
fi

# mkfs and its filesystem-specific variants (mkfs.ext4, mkfs.xfs, ...).
if [[ "$lowered" =~ (^|[[:space:]])mkfs(\.[a-z0-9]+)?([[:space:]]|$) ]]; then
  deny "refusing mkfs"
fi

if [[ "$lowered" =~ dd[[:space:]].*of=/dev/ ]]; then
  deny "refusing dd to block device"
fi

if [[ "$lowered" =~ chmod[[:space:]]+(-r[[:space:]]+)?777([[:space:]]|$) ]]; then
  deny "refusing chmod 777"
fi

exit 0
