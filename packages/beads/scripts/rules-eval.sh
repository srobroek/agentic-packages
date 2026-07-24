#!/usr/bin/env bash
# rules-eval.sh — bead-as-brief contract evaluator (spec 002-bead-as-brief).
#
# Shared SubagentStop evaluator for the claim⟺contract enforcement layer. One
# script, many per-agent rules files. Reads a hook payload on stdin, resolves
# the bead the stopping actor claims, loads that agent's rules file, evaluates
# the completion checklist + authority matrix + escape + bounce, and emits the
# hook decision JSON on stdout.
#
# CONTRACT (specs/002-bead-as-brief/contracts/):
#   stdin  = SubagentStop hook payload JSON (agent_type, agent_id, ...)
#           OR, for the conformance suite, a synthetic {"_bead": {...}} fixture.
#   stdout = {} (allow) | {"decision":"block","reason":"<json>"} (block)
#   exit   = 0 always (block is signalled in the body; caller maps to exit 2
#            on Claude where required). Fail OPEN on any error (constitution III).
#
# Predicate vocabulary (closed): metadata.<key> | label ~ "<regex>" |
#   comment.verb in [A,B] | state in [A,B] | wisp(<sel>).open|.closed
#
# Portability: bash 3.2, BSD/GNU tolerant, jq required, yq for rules files.

set -uo pipefail   # NOT -e: this hook must fail open, never abort mid-eval.

# ---------------------------------------------------------------------------
# Resolution of rules-file search roots. Rules files live at
# <package>/.apm/rules/<agent>.rules.yml and are deployed next to agents.
# Override with RULES_DIR (conformance suite points it at fixtures).
# ---------------------------------------------------------------------------
RULES_DIR="${RULES_DIR:-}"
BD_BIN="${BD_BIN:-bd}"

emit_allow() { printf '{}\n'; exit 0; }

emit_block() {
  # $1 = compact JSON reason string
  jq -cn --arg r "$1" '{decision:"block", reason:$r}' 2>/dev/null \
    || printf '{"decision":"block","reason":%s}\n' "$(printf '%s' "$1" | jq -Rs . 2>/dev/null || printf '""')"
  exit 0
}

payload="$(cat 2>/dev/null || true)"
[ -z "$payload" ] && emit_allow

command -v jq >/dev/null 2>&1 || emit_allow   # no jq -> fail open

agent_type="$(printf '%s' "$payload" | jq -r '.agent_type // .agent // empty' 2>/dev/null || true)"
agent_id="$(printf '%s' "$payload" | jq -r '.agent_id // empty' 2>/dev/null || true)"

# ---------------------------------------------------------------------------
# Bead source. Two modes:
#   (a) fixture: payload carries ._bead (a full bd-show-shaped object) and
#       optionally ._rules_file — used by the conformance suite, no bd needed.
#   (b) live: resolve the claimed bead by assignee-name convention via bd.
# ---------------------------------------------------------------------------
bead_json=""
rules_file=""

fixture_bead="$(printf '%s' "$payload" | jq -c '._bead // empty' 2>/dev/null || true)"
if [ -n "$fixture_bead" ]; then
  bead_json="$fixture_bead"
  rules_file="$(printf '%s' "$payload" | jq -r '._rules_file // empty' 2>/dev/null || true)"
  [ -z "$agent_type" ] && agent_type="$(printf '%s' "$bead_json" | jq -r '.metadata.execution_agent // empty' 2>/dev/null || true)"
else
  # Live mode: no agent type -> nothing to enforce -> allow.
  [ -z "$agent_type" ] && emit_allow
  # Derive the actor name. Node-scoped actors embed the bead id; the assignee
  # query is the source of truth regardless.
  actor="${agent_id:-$agent_type}"
  command -v "$BD_BIN" >/dev/null 2>&1 || emit_allow
  claimed="$($BD_BIN list --assignee "$actor" --status in_progress --json 2>/dev/null || true)"
  # bd list returns an array; unwrap the first claim. No claim -> no contract
  # (claim⟺contract, no-claim direction) -> allow.
  n="$(printf '%s' "$claimed" | jq 'if type=="array" then length else 0 end' 2>/dev/null || printf '0')"
  [ "$n" = "0" ] || [ -z "$n" ] && emit_allow
  bead_json="$(printf '%s' "$claimed" | jq -c '.[0]' 2>/dev/null || true)"
  # bd show/list carry no comments (only comment_count). Fetch them separately
  # and splice into .comments so the accessors read one shape for both modes.
  cid="$(printf '%s' "$bead_json" | jq -r '.id // empty' 2>/dev/null)"
  if [ -n "$cid" ]; then
    cjson="$($BD_BIN comments "$cid" --json 2>/dev/null || true)"
    cjson="$(printf '%s' "$cjson" | jq -c 'if type=="array" then . else [] end' 2>/dev/null || printf '[]')"
    bead_json="$(printf '%s' "$bead_json" | jq -c --argjson c "${cjson:-[]}" '.comments = $c' 2>/dev/null || printf '%s' "$bead_json")"
  fi
fi

[ -z "$bead_json" ] && emit_allow

# Locate the rules file if not supplied by a fixture.
if [ -z "$rules_file" ]; then
  [ -z "$RULES_DIR" ] && emit_allow   # nowhere to look -> fail open
  cand="$RULES_DIR/$agent_type.rules.yml"
  [ -f "$cand" ] && rules_file="$cand"
fi
# Unknown agent with no rules file -> generic fallback is applied by the
# universal net, not here; this per-agent evaluator allows.
[ -z "$rules_file" ] || [ ! -f "$rules_file" ] && emit_allow
command -v yq >/dev/null 2>&1 || emit_allow

# Convert the rules file to JSON once.
rules="$(yq -o=json '.' "$rules_file" 2>/dev/null || true)"
[ -z "$rules" ] && emit_allow

# ---------------------------------------------------------------------------
# Bead accessors.
# ---------------------------------------------------------------------------
bead_id="$(printf '%s' "$bead_json" | jq -r '.id // "?"' 2>/dev/null)"
bead_state="$(printf '%s' "$bead_json" | jq -r '.status // .state // empty' 2>/dev/null)"
# state may live in metadata.state (custom state) rather than status
meta_state="$(printf '%s' "$bead_json" | jq -r '.metadata.state // empty' 2>/dev/null)"
[ -n "$meta_state" ] && bead_state="$meta_state"

has_metadata_key() { printf '%s' "$bead_json" | jq -e --arg k "$1" '.metadata[$k] != null and .metadata[$k] != ""' >/dev/null 2>&1; }
label_matches()    { printf '%s' "$bead_json" | jq -e --arg re "$1" '((.labels // []) | map(test($re)) | any)' >/dev/null 2>&1; }
comment_verb_in()  {
  # $1 = comma list of verbs; comments carry a leading VERB token.
  printf '%s' "$bead_json" | jq -e --arg verbs "$1" '
    ($verbs | split(",") | map(ascii_upcase)) as $v
    | ((.comments // []) | map(.text // .body // "") | map(ascii_upcase | ltrimstr(" ") | split(" ")[0]) | any(. as $t | $v | index($t)))
  ' >/dev/null 2>&1
}
state_in() { printf '%s' "$1" | tr ',' '\n' | grep -qx "$bead_state"; }

# escape hatch first: failed/blocked + FAILED|BLOCKED comment -> always allow.
escape_state="$(printf '%s' "$rules" | jq -r '.escape.state // empty' 2>/dev/null)"
if [ -n "$escape_state" ] && [ "$bead_state" = "$escape_state" ]; then
  escape_verbs="$(printf '%s' "$rules" | jq -r '(.escape.require // "") | capture("in \\[(?<v>[^\\]]*)\\]").v // ""' 2>/dev/null | tr -d ' ')"
  if [ -z "$escape_verbs" ] || comment_verb_in "$escape_verbs"; then
    emit_allow
  fi
fi

# ---------------------------------------------------------------------------
# Completion checklist. Collect failures (respecting per-check `when: <kind>`).
# ---------------------------------------------------------------------------
node_kind="$(printf '%s' "$bead_json" | jq -r '.metadata.execution_kind // empty' 2>/dev/null)"
failed="[]"
n_checks="$(printf '%s' "$rules" | jq '(.completion // []) | length' 2>/dev/null || printf '0')"
i=0
while [ "$i" -lt "${n_checks:-0}" ]; do
  chk="$(printf '%s' "$rules" | jq -c --argjson i "$i" '.completion[$i]' 2>/dev/null)"
  i=$((i+1))
  [ -z "$chk" ] && continue
  when="$(printf '%s' "$chk" | jq -r '.when // empty' 2>/dev/null)"
  [ -n "$when" ] && [ -n "$node_kind" ] && [ "$when" != "$node_kind" ] && continue
  slug="$(printf '%s' "$chk" | jq -r '.check // "?"' 2>/dev/null)"
  req="$(printf '%s' "$chk" | jq -r '.require // empty' 2>/dev/null)"
  ok=1
  case "$req" in
    metadata.*)        has_metadata_key "${req#metadata.}" || ok=0 ;;
    "label ~ "*)       pat="${req#label ~ }"; pat="${pat#\"}"; pat="${pat%\"}"; label_matches "$pat" || ok=0 ;;
    "comment.verb in "*) verbs="$(printf '%s' "$req" | sed -E 's/.*\[(.*)\].*/\1/' | tr -d ' ')"; comment_verb_in "$verbs" || ok=0 ;;
    "state in "*)      sts="$(printf '%s' "$req" | sed -E 's/.*\[(.*)\].*/\1/' | tr -d ' ')"; state_in "$sts" || ok=0 ;;
    *)                 ok=1 ;;   # unknown predicate -> do not fail (fail open)
  esac
  if [ "$ok" = "0" ]; then
    failed="$(printf '%s' "$failed" | jq -c --arg c "$slug" --arg d "unsatisfied: $req" '. + [{check:$c, detail:$d}]' 2>/dev/null)"
  fi
done

# ---------------------------------------------------------------------------
# Authority violations: deny_states / deny_metadata.
# ---------------------------------------------------------------------------
violations="[]"
# deny_states: the bead is currently in a state this agent may never set.
while IFS= read -r ds; do
  [ -z "$ds" ] && continue
  if [ "$bead_state" = "$ds" ]; then
    violations="$(printf '%s' "$violations" | jq -c --arg s "$ds" '. + [{check:"state_authority", detail:("state=" + $s + " set by an agent forbidden to set it")}]' 2>/dev/null)"
  fi
done <<EOF
$(printf '%s' "$rules" | jq -r '(.authority.deny_states // [])[]' 2>/dev/null)
EOF
# deny_metadata: the bead carries a metadata key this agent may never write.
while IFS= read -r dm; do
  [ -z "$dm" ] && continue
  if has_metadata_key "$dm"; then
    violations="$(printf '%s' "$violations" | jq -c --arg k "$dm" '. + [{check:"metadata_authority", detail:("wrote forbidden metadata." + $k)}]' 2>/dev/null)"
  fi
done <<EOF
$(printf '%s' "$rules" | jq -r '(.authority.deny_metadata // [])[]' 2>/dev/null)
EOF

nf="$(printf '%s' "$failed" | jq 'length' 2>/dev/null || printf '0')"
nv="$(printf '%s' "$violations" | jq 'length' 2>/dev/null || printf '0')"

if [ "${nf:-0}" = "0" ] && [ "${nv:-0}" = "0" ]; then
  emit_allow
fi

# ---------------------------------------------------------------------------
# Bounce: at max_attempts, force-allow with side effects.
# ---------------------------------------------------------------------------
attempts="$(printf '%s' "$bead_json" | jq -r '.metadata.stop_attempts // 0' 2>/dev/null)"
attempts="${attempts:-0}"
max="$(printf '%s' "$rules" | jq -r '.bounce.max_attempts // 3' 2>/dev/null)"
next=$((attempts + 1))

if [ "$next" -ge "${max:-3}" ]; then
  # In live mode, perform the bounce side effects; in fixture mode just report.
  reason="$(jq -cn --arg b "$bead_id" --arg a "$agent_type" --argjson f "$failed" --argjson v "$violations" \
    '{bead:$b, agent:$a, bounce:true, attempt:('"$next"'), failed_checks:$f, violations:$v}' 2>/dev/null)"
  if [ -z "$fixture_bead" ] && command -v "$BD_BIN" >/dev/null 2>&1; then
    $BD_BIN comment "$bead_id" "BOUNCE agent=$agent_type attempt=$next failed=$reason" >/dev/null 2>&1 || true
    $BD_BIN update "$bead_id" --assignee "" --metadata '{"stop_attempts":0,"review_round":0}' >/dev/null 2>&1 || true
  fi
  # Bounce force-ALLOWS the exit (agent stops; orchestrator investigates).
  emit_allow
fi

# ---------------------------------------------------------------------------
# Block: increment attempts (live) and emit the failure-specific report.
# ---------------------------------------------------------------------------
if [ -z "$fixture_bead" ] && command -v "$BD_BIN" >/dev/null 2>&1; then
  $BD_BIN update "$bead_id" --metadata "{\"stop_attempts\":$next}" >/dev/null 2>&1 || true
fi

reason="$(jq -cn --arg b "$bead_id" --arg a "$agent_type" --argjson at "$next" --argjson f "$failed" --argjson v "$violations" \
  '{bead:$b, agent:$a, attempt:$at, failed_checks:$f, violations:$v}' 2>/dev/null)"
emit_block "$reason"
