#!/usr/bin/env bash
# rules-eval-test.sh — conformance suite for rules-eval.sh (spec 002 SC-002).
# Fixture-driven: no bd/live state needed. Each case feeds a synthetic payload
# (._bead + ._rules_file) and asserts the verdict. Exits non-zero on any fail.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
EVAL="$HERE/rules-eval.sh"
RULES="$(cd "$HERE/../../orchestrate/.apm/rules" && pwd)"
DS="$RULES/domain-specialist.rules.yml"

pass=0; fail=0
run() { # $1=name $2=expected(allow|block) $3=payload
  local name="$1" want="$2" payload="$3" out verdict
  out="$(printf '%s' "$payload" | RULES_DIR="$RULES" bash "$EVAL" 2>/dev/null)"
  if printf '%s' "$out" | jq -e '.decision=="block"' >/dev/null 2>&1; then verdict=block; else verdict=allow; fi
  if [ "$verdict" = "$want" ]; then
    pass=$((pass+1)); printf '  ok   %-42s -> %s\n' "$name" "$verdict"
  else
    fail=$((fail+1)); printf '  FAIL %-42s -> got %s want %s\n     out: %s\n' "$name" "$verdict" "$want" "$out"
  fi
}

bead() { # helper builds a fixture payload; args are jq --argjson/--arg pairs baked below
  :
}

# --- complete git node: all checks satisfied -> allow ---
run "git complete" allow "$(jq -cn --arg rf "$DS" '{
  agent_type:"domain-specialist", _rules_file:$rf,
  _bead:{id:"t1", status:"reported", labels:["orc-node","agent:reviewer"],
    metadata:{execution_kind:"git", branch:"node-t1", push:"abc123"},
    comments:[{text:"BRIEF do the thing"},{text:"REPORTED done, verified"}]}}')"

# --- git node missing push -> block, only push fails ---
run "git missing push" block "$(jq -cn --arg rf "$DS" '{
  agent_type:"domain-specialist", _rules_file:$rf,
  _bead:{id:"t2", status:"reported", labels:["agent:reviewer"],
    metadata:{execution_kind:"git", branch:"node-t2"},
    comments:[{text:"REPORTED done"}]}}')"

# --- git node missing handoff label -> block ---
run "git missing handoff label" block "$(jq -cn --arg rf "$DS" '{
  agent_type:"domain-specialist", _rules_file:$rf,
  _bead:{id:"t3", status:"reported", labels:["orc-node"],
    metadata:{execution_kind:"git", branch:"n", push:"sha"},
    comments:[{text:"REPORTED done"}]}}')"

# --- no REPORTED comment -> block ---
run "git no reported comment" block "$(jq -cn --arg rf "$DS" '{
  agent_type:"domain-specialist", _rules_file:$rf,
  _bead:{id:"t4", status:"working", labels:["agent:reviewer"],
    metadata:{execution_kind:"git", branch:"n", push:"sha"},
    comments:[{text:"CHECKPOINT step 1"}]}}')"

# --- escape hatch: failed + FAILED comment -> allow despite missing everything ---
run "escape failed+FAILED" allow "$(jq -cn --arg rf "$DS" '{
  agent_type:"domain-specialist", _rules_file:$rf,
  _bead:{id:"t5", status:"failed", labels:[],
    metadata:{execution_kind:"git"},
    comments:[{text:"FAILED repo is broken, cannot proceed"}]}}')"

# --- failed state but NO failed comment -> still block (escape not satisfied) ---
run "failed state no FAILED comment" block "$(jq -cn --arg rf "$DS" '{
  agent_type:"domain-specialist", _rules_file:$rf,
  _bead:{id:"t6", status:"failed", labels:[],
    metadata:{execution_kind:"git"},
    comments:[{text:"CHECKPOINT partial"}]}}')"

# --- authority violation: specialist left bead in approved -> block ---
run "authority deny approved" block "$(jq -cn --arg rf "$DS" '{
  agent_type:"domain-specialist", _rules_file:$rf,
  _bead:{id:"t7", status:"approved", labels:["agent:reviewer"],
    metadata:{execution_kind:"git", branch:"n", push:"sha"},
    comments:[{text:"REPORTED done"}]}}')"

# --- authority violation: wrote merge_sha -> block even if checklist ok ---
run "authority deny merge_sha" block "$(jq -cn --arg rf "$DS" '{
  agent_type:"domain-specialist", _rules_file:$rf,
  _bead:{id:"t8", status:"reported", labels:["agent:reviewer"],
    metadata:{execution_kind:"git", branch:"n", push:"sha", merge_sha:"deadbeef"},
    comments:[{text:"REPORTED done"}]}}')"

# --- artifact kind: output_ref present, push NOT required -> allow ---
run "artifact complete" allow "$(jq -cn --arg rf "$DS" '{
  agent_type:"domain-specialist", _rules_file:$rf,
  _bead:{id:"t9", status:"reported", labels:["agent:reviewer"],
    metadata:{execution_kind:"artifact", output_ref:"/run/artifacts/report.md"},
    comments:[{text:"REPORTED done"}]}}')"

# --- artifact kind missing output_ref -> block ---
run "artifact missing output_ref" block "$(jq -cn --arg rf "$DS" '{
  agent_type:"domain-specialist", _rules_file:$rf,
  _bead:{id:"t10", status:"reported", labels:["agent:reviewer"],
    metadata:{execution_kind:"artifact"},
    comments:[{text:"REPORTED done"}]}}')"

# --- bounce: 3rd attempt on an incomplete bead -> force ALLOW ---
run "bounce at max_attempts" allow "$(jq -cn --arg rf "$DS" '{
  agent_type:"domain-specialist", _rules_file:$rf,
  _bead:{id:"t11", status:"working", labels:[],
    metadata:{execution_kind:"git", stop_attempts:2},
    comments:[{text:"CHECKPOINT stuck"}]}}')"

# --- no claim / no agent_type -> allow (claim<->contract, no-claim direction) ---
run "no agent_type" allow '{"session_id":"x"}'

# --- unknown agent, no rules file -> allow (per-agent evaluator defers to net) ---
run "unknown agent" allow "$(jq -cn '{agent_type:"totally-unknown-agent",
  _bead:{id:"t12", status:"working", metadata:{}, comments:[]}}')"

echo
echo "rules-eval conformance: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
