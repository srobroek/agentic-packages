#!/usr/bin/env bash
# _test_hooks.sh — smoke tests for the orchestrate hook scripts (N3 bead-as-brief).
#
# Tests universal-stop-net.sh and orchestrator-claim-deny.sh using synthetic
# fixture payloads (no live bd required for claim-deny; universal net tests use
# a stubbed bd binary). Exits non-zero on any failure.
#
# Usage: bash _test_hooks.sh
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
NET_SCRIPT="$HERE/universal-stop-net.sh"
DENY_SCRIPT="$HERE/orchestrator-claim-deny.sh"

pass=0
fail=0

# run <name> <want:allow|block> <script> <stdin_data> [VAR=val ...]
run() {
  local name="$1" want="$2" verdict out
  shift 2
  local script="$1"; shift
  local stdin_data="${1:-}"; shift  # shift stdin off so "$@" = env vars only

  out="$(printf '%s' "$stdin_data" | env "$@" bash "$script" 2>/dev/null || true)"
  if printf '%s' "$out" | jq -e '.decision == "block" or .decision == "deny"' >/dev/null 2>&1; then
    verdict=block
  else
    verdict=allow
  fi

  if [ "$verdict" = "$want" ]; then
    pass=$((pass+1))
    printf '  ok   %-52s -> %s\n' "$name" "$verdict"
  else
    fail=$((fail+1))
    printf '  FAIL %-52s -> got %s want %s\n     out: %s\n' "$name" "$verdict" "$want" "$out"
  fi
}

# ---------------------------------------------------------------------------
# Stub bd: returns a claimed bead for known actor names, [] otherwise.
# ---------------------------------------------------------------------------
TMP_BIN="$(mktemp -d)"
TMP_FAKE_PLUGIN="$(mktemp -d)"
mkdir -p "$TMP_FAKE_PLUGIN/.apm/rules"
# domain-specialist has a rules file -> universal net should yield to per-agent hook.
touch "$TMP_FAKE_PLUGIN/.apm/rules/domain-specialist.rules.yml"
trap 'rm -rf "$TMP_BIN" "$TMP_FAKE_PLUGIN"' EXIT

cat > "$TMP_BIN/bd" <<'BDSTUB'
#!/usr/bin/env bash
# Stub bd for hook smoke tests.
case "$*" in
  *"--assignee"*"--status in_progress"*"--json"*)
    actor=""
    prev=""
    for a in "$@"; do
      [ "$prev" = "--assignee" ] && actor="$a"
      prev="$a"
    done
    case "$actor" in
      "claimed-actor")
        printf '[{"id":"smoke-t1","status":"in_progress","labels":[],"metadata":{"execution_kind":"git","stop_attempts":0},"comments":[]}]\n'
        ;;
      "domain-specialist")
        printf '[{"id":"smoke-t3","status":"in_progress","labels":[],"metadata":{"execution_kind":"git","stop_attempts":0},"comments":[]}]\n'
        ;;
      *)
        printf '[]\n'
        ;;
    esac
    ;;
  "comments"*"--json")
    printf '[]\n'
    ;;
  "update"*|"comment"*)
    exit 0
    ;;
  "where")
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
BDSTUB
chmod +x "$TMP_BIN/bd"

echo ""
echo "=== universal-stop-net.sh smoke tests ==="

# 1. No claim (unknown actor) -> allow
run "no claim -> allow" allow \
  "$NET_SCRIPT" \
  '{"agent_type":"some-random-agent","agent_id":"some-random-agent"}' \
  "PATH=$TMP_BIN:$PATH" "BD_BIN=$TMP_BIN/bd" "PLUGIN_ROOT=$TMP_FAKE_PLUGIN"

# 2. Claim held, no rules file, no REPORTED comment -> block
run "claim held, no rules file, no REPORTED -> block" block \
  "$NET_SCRIPT" \
  '{"agent_type":"claimed-actor","agent_id":"claimed-actor"}' \
  "PATH=$TMP_BIN:$PATH" "BD_BIN=$TMP_BIN/bd" "PLUGIN_ROOT=$TMP_FAKE_PLUGIN"

# 3. domain-specialist claim held, rules file exists -> net yields (allow)
run "claim held, rules file exists -> net allows (per-agent owns it)" allow \
  "$NET_SCRIPT" \
  '{"agent_type":"domain-specialist","agent_id":"domain-specialist"}' \
  "PATH=$TMP_BIN:$PATH" "BD_BIN=$TMP_BIN/bd" "PLUGIN_ROOT=$TMP_FAKE_PLUGIN"

# 4. stop_hook_active=true -> re-entrancy guard -> allow
run "stop_hook_active=true -> allow (re-entrancy)" allow \
  "$NET_SCRIPT" \
  '{"agent_type":"claimed-actor","agent_id":"claimed-actor","stop_hook_active":"true"}' \
  "PATH=$TMP_BIN:$PATH" "BD_BIN=$TMP_BIN/bd" "PLUGIN_ROOT=$TMP_FAKE_PLUGIN"

echo ""
echo "=== orchestrator-claim-deny.sh smoke tests ==="

# 5. Not in a run -> allow (no ORCHESTRATE_RUN, no marker file)
run "no run marker -> allow" allow \
  "$DENY_SCRIPT" \
  '{"tool_name":"Bash","tool_input":{"command":"bd update orc-1 --claim --assignee me"}}' \
  "PATH=$TMP_BIN:$PATH"

# 6. In a run, bd --claim command -> deny
run "in run + bd --claim -> deny" block \
  "$DENY_SCRIPT" \
  '{"tool_name":"Bash","tool_input":{"command":"bd update orc-1 --claim --assignee me"}}' \
  "PATH=$TMP_BIN:$PATH" "ORCHESTRATE_RUN=run-abc"

# 7. In a run, non-claim bd command -> allow
run "in run + bd update (no --claim) -> allow" allow \
  "$DENY_SCRIPT" \
  '{"tool_name":"Bash","tool_input":{"command":"bd update orc-1 --metadata \"{}\" "}}' \
  "PATH=$TMP_BIN:$PATH" "ORCHESTRATE_RUN=run-abc"

# 8. In a run, non-bd command -> allow
run "in run + non-bd command -> allow" allow \
  "$DENY_SCRIPT" \
  '{"tool_name":"Bash","tool_input":{"command":"git status"}}' \
  "PATH=$TMP_BIN:$PATH" "ORCHESTRATE_RUN=run-abc"

# 9. Malformed input -> allow (fail open)
run "malformed input -> allow (fail open)" allow \
  "$DENY_SCRIPT" \
  'not-json-at-all' \
  "PATH=$TMP_BIN:$PATH" "ORCHESTRATE_RUN=run-abc"

# 10. In a run, marker file path -> deny
TMP_MARKER="$(mktemp)"
run "in run (marker file) + bd --claim -> deny" block \
  "$DENY_SCRIPT" \
  '{"tool_name":"Bash","tool_input":{"command":"bd update orc-2 --claim"}}' \
  "PATH=$TMP_BIN:$PATH" "ORCHESTRATE_MARKER_FILE=$TMP_MARKER"
rm -f "$TMP_MARKER"

echo ""
echo "hooks smoke tests: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
