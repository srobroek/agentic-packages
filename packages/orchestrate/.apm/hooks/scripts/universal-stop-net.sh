#!/usr/bin/env bash
# universal-stop-net.sh — SubagentStop hook: universal net (matcher-less).
#
# Fires for EVERY stopping subagent. Two cases handled:
#
#   (a) No claim held  -> silent allow (claim<->contract, no-claim direction).
#   (b) Claim held + rules file exists for this agent_type
#                      -> per-agent hook owns evaluation; this net yields (allow).
#   (c) Claim held + NO rules file for this agent_type (unlisted/unknown agent)
#                      -> generic fallback checklist: block unless the bead
#                         carries a REPORTED comment, a valid escape indicator
#                         (FAILED/BLOCKED + blocked status), OR stop_attempts
#                         has reached the bounce threshold (3).
#
# Contract (hook-io.md):
#   stdin  = SubagentStop payload JSON
#   stdout = {} (allow) | {"decision":"block","reason":"..."} (block)
#   exit   = 0 always (fail open on any error)
#
# Portability: bash 3.2, BSD/GNU tolerant, jq required.
set -uo pipefail   # NOT -e: must fail open.

emit_allow() { printf '{}\n'; exit 0; }
emit_block() {
  jq -cn --arg r "$1" '{decision:"block", reason:$r}' 2>/dev/null \
    || printf '{"decision":"block","reason":""}\n'
  exit 0
}

payload="$(cat 2>/dev/null || true)"
[ -z "$payload" ] && emit_allow

command -v jq >/dev/null 2>&1 || emit_allow
command -v bd >/dev/null 2>&1  || emit_allow

# Re-entrancy guard (Codex): if stop_hook_active is set another hook already
# evaluated this stop; yield immediately.
stop_hook_active="$(printf '%s' "$payload" | jq -r '.stop_hook_active // empty' 2>/dev/null || true)"
[ "$stop_hook_active" = "true" ] && emit_allow

agent_type="$(printf '%s' "$payload" | jq -r '.agent_type // .agent // empty' 2>/dev/null || true)"
agent_id="$(printf '%s' "$payload"   | jq -r '.agent_id // empty'             2>/dev/null || true)"

[ -z "$agent_type" ] && [ -z "$agent_id" ] && emit_allow

actor="${agent_id:-$agent_type}"

# Resolve the claimed bead.
claimed="$(bd list --assignee "$actor" --status in_progress --json 2>/dev/null || true)"
n="$(printf '%s' "$claimed" | jq 'if type=="array" then length else 0 end' 2>/dev/null || printf '0')"
# No claim -> no contract.
[ "${n:-0}" = "0" ] && emit_allow

bead_json="$(printf '%s' "$claimed" | jq -c '.[0]' 2>/dev/null || true)"
[ -z "$bead_json" ] && emit_allow

bead_id="$(printf '%s' "$bead_json" | jq -r '.id // empty' 2>/dev/null || true)"

# Check if a rules file exists for this agent type; if so, the per-agent hook
# owns evaluation — allow here (avoid double-block and double bounce-increment).
_script_dir="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
_plugin_root="${PLUGIN_ROOT:-}"
if [ -n "$_plugin_root" ]; then
  _rules_dir="${_plugin_root}/.apm/rules"
else
  _rules_dir="${_script_dir}/../../rules"
fi
[ -f "${_rules_dir}/${agent_type}.rules.yml" ] && emit_allow

# Unknown agent with a claim: generic fallback checklist.
# Fetch comments.
cjson="$(bd comments "$bead_id" --json 2>/dev/null || true)"
cjson="$(printf '%s' "$cjson" | jq -c 'if type=="array" then . else [] end' 2>/dev/null || printf '[]')"

# Check for a REPORTED comment (the minimum evidence of completion).
has_reported="$(printf '%s' "$cjson" | jq '
  [.[].text // ""] | map(ascii_upcase | ltrimstr(" ") | split(" ")[0]) | any(. == "REPORTED")
' 2>/dev/null || printf 'false')"

# Check for FAILED/BLOCKED escape verb.
has_escape="$(printf '%s' "$cjson" | jq '
  [.[].text // ""] | map(ascii_upcase | ltrimstr(" ") | split(" ")[0]) | any(. == "FAILED" or . == "BLOCKED")
' 2>/dev/null || printf 'false')"

# Check bead status for escape.
bead_status="$(printf '%s' "$bead_json" | jq -r '.status // empty' 2>/dev/null || true)"

# Check bounce threshold.
attempts="$(printf '%s' "$bead_json" | jq -r '.metadata.stop_attempts // 0' 2>/dev/null || printf '0')"
next_attempts=$((${attempts:-0} + 1))

# Escape: blocked status + FAILED/BLOCKED comment.
if [ "$bead_status" = "blocked" ] && [ "$has_escape" = "true" ]; then
  emit_allow
fi

# Complete: has REPORTED comment.
if [ "$has_reported" = "true" ]; then
  emit_allow
fi

# Bounce threshold reached: force-allow with side effects.
if [ "$next_attempts" -ge 3 ]; then
  reason="$(jq -cn --arg b "$bead_id" --arg a "${agent_type:-unknown}" --argjson at "$next_attempts" \
    '{bead:$b, agent:$a, attempt:$at, bounce:true,
      failed_checks:[{check:"generic_reported",detail:"REPORTED comment missing (generic fallback)"}]}' \
    2>/dev/null || printf '{}')"
  bd comment "$bead_id" "BOUNCE agent=${agent_type:-unknown} attempt=$next_attempts reason=$reason" >/dev/null 2>&1 || true
  bd update "$bead_id" --assignee "" --metadata '{"stop_attempts":0,"review_round":0}' >/dev/null 2>&1 || true
  emit_allow
fi

# Block: increment attempts and emit generic failure.
bd update "$bead_id" --metadata "{\"stop_attempts\":$next_attempts}" >/dev/null 2>&1 || true

reason="$(jq -cn --arg b "$bead_id" --arg a "${agent_type:-unknown}" --argjson at "$next_attempts" \
  '{bead:$b, agent:$a, attempt:$at,
    failed_checks:[{check:"generic_reported",detail:"REPORTED comment missing (generic fallback — no rules file for this agent type)"}]}' \
  2>/dev/null || printf '{}')"
emit_block "$reason"
