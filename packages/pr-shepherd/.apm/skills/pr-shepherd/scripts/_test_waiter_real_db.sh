#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SCRIPT_DIR
readonly CONTRACT="$SCRIPT_DIR/landing-contract.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/pr-shepherd-real-db.XXXXXX")"
readonly TMP_ROOT
trap 'rm -rf -- "$TMP_ROOT"' EXIT

fail() {
  printf 'real-db waiter test: %s\n' "$*" >&2
  exit 1
}

run_contract() {
  local actor="$1"
  shift
  set +e
  output="$(BEADS_ACTOR="$actor" "$CONTRACT" "$@" 2>&1)"
  rc=$?
  set -e
}

waiter_records() {
  local slot_id="$1"
  local holder="$2"

  bd list --label gt:slot-waiter --all --metadata-field "slot_id=$slot_id" \
    --metadata-field "holder=$holder" --limit 0 --json
}

assert_record() {
  local slot_id="$1"
  local holder="$2"
  local generation="$3"
  local status="$4"
  local assignee="$5"
  local actor="$6"
  local record waiter

  record="$(waiter_records "$slot_id" "$holder" | jq -ce \
    --argjson generation "$generation" \
    '[.[] | select(.metadata.generation == $generation)] | select(length == 1) | .[0]')" ||
    fail "missing generation $generation for $holder"
  [[ "$(printf '%s' "$record" | jq -r '.status')" == "$status" ]] ||
    fail "$holder generation $generation status mismatch"
  [[ "$(printf '%s' "$record" | jq -r '.assignee // ""')" == "$assignee" ]] ||
    fail "$holder generation $generation assignee mismatch"
  [[ "$(printf '%s' "$record" | jq -r '.metadata.lease_actor')" == "$actor" ]] ||
    fail "$holder generation $generation lease mismatch"
  printf '%s' "$record" | jq -e --arg slot "$slot_id" \
    '[.dependencies[]? | select(.type == "parent-child" and .depends_on_id == $slot)] |
     length == 1' >/dev/null || fail "$holder generation $generation linkage mismatch"
  waiter="$(printf '%s' "$record" | jq -er '.id')" || fail "missing waiter id"
  bd show "$waiter" --json | jq -e --arg slot "$slot_id" \
    '[.[0].dependencies[]? |
      select(.dependency_type == "parent-child" and .id == $slot)] | length == 1' \
    >/dev/null || fail "$holder generation $generation show linkage mismatch"
}

command -v bd >/dev/null 2>&1 || fail "bd not found"
command -v jq >/dev/null 2>&1 || fail "jq not found"
git -C "$TMP_ROOT" init -q
cd "$TMP_ROOT"
export BEADS_DIR="$TMP_ROOT/.beads"
bd init --quiet --prefix tst --non-interactive --skip-agents --skip-hooks
bd merge-slot create >/dev/null
slot_id="$(bd merge-slot check --json | jq -er '.id')"

run_contract actor-a acquire-slot stable-holder 1 0
[[ $rc -eq 0 ]] || fail "initial acquire failed: $output"
assert_record "$slot_id" stable-holder 1 in_progress actor-a actor-a
run_contract actor-a release-slot stable-holder retryable
[[ $rc -eq 0 ]] || fail "retryable release failed: $output"
assert_record "$slot_id" stable-holder 1 open "" actor-a

run_contract actor-b acquire-slot stable-holder 1 0
[[ $rc -eq 2 && "$output" == *"leased to another actor"* ]] ||
  fail "foreign actor was not rejected: $output"
[[ "$(bd merge-slot check --json | jq -r '.available')" == true ]] ||
  fail "foreign actor entered the native slot"

run_contract actor-a acquire-slot stable-holder 1 0
[[ $rc -eq 0 ]] || fail "same actor retry failed: $output"
run_contract actor-a release-slot stable-holder terminal
[[ $rc -eq 0 ]] || fail "terminal release failed: $output"
assert_record "$slot_id" stable-holder 1 closed actor-a actor-a
run_contract actor-a acquire-slot stable-holder 1 0
[[ $rc -eq 2 && "$output" == *"explicit requeue"* ]] ||
  fail "terminal attempt restarted without requeue: $output"
run_contract actor-a acquire-slot stable-holder 1 0 requeue
[[ $rc -eq 0 ]] || fail "generation two acquire failed: $output"
assert_record "$slot_id" stable-holder 2 in_progress actor-a actor-a
run_contract actor-a release-slot stable-holder terminal
[[ $rc -eq 0 ]] || fail "generation two release failed: $output"

run_contract actor-a acquire-slot takeover-holder 1 0
[[ $rc -eq 0 ]] || fail "takeover fixture acquire failed: $output"
dead_native_holder="$(bd merge-slot check --json | jq -er '.holder')"
run_contract actor-b release-slot takeover-holder terminal
[[ $rc -eq 2 ]] || fail "foreign actor released a live actor's slot: $output"
[[ "$(bd merge-slot check --json | jq -r '.holder')" == "$dead_native_holder" ]] ||
  fail "foreign release changed the native holder"
merge_bead="$(BEADS_ACTOR=actor-a bd create 'Dead integrator claim' \
  --labels agent:integrator --silent)"
BEADS_ACTOR=actor-a bd update "$merge_bead" --claim >/dev/null
run_contract actor-b recover-claim "$merge_bead" actor-a session-registry:dead takeover-holder
[[ $rc -eq 0 ]] || fail "dead actor takeover failed: $output"
assert_record "$slot_id" takeover-holder 1 closed actor-a actor-a
assert_record "$slot_id" takeover-holder 2 in_progress actor-b actor-b
successor_native_holder="$(bd merge-slot check --json | jq -er '.holder')"
[[ "$successor_native_holder" != "$dead_native_holder" ]] ||
  fail "successor reused the dead native holder token"
set +e
bd merge-slot release --holder "$dead_native_holder" >/dev/null 2>&1
stale_release_rc=$?
set -e
[[ $stale_release_rc -ne 0 ]] || fail "delayed dead-token release succeeded"
[[ "$(bd merge-slot check --json | jq -er '.holder')" == "$successor_native_holder" ]] ||
  fail "delayed dead-token release changed successor ownership"
winner_receipt="$(bd show "$merge_bead" --json | jq -er '.[0].metadata.recovery_key')"
run_contract actor-c recover-claim "$merge_bead" actor-a session-registry:competitor takeover-holder
[[ $rc -eq 2 ]] || fail "competing successor replaced the winner: $output"
[[ "$(bd show "$merge_bead" --json | jq -er '.[0].metadata.recovery_key')" == "$winner_receipt" ]] ||
  fail "competing successor overwrote the winner receipt"
assert_record "$slot_id" takeover-holder 2 in_progress actor-b actor-b
run_contract actor-b acquire-slot takeover-holder 1 0
[[ $rc -eq 0 ]] || fail "successor could not resume recovered waiter: $output"
run_contract actor-b release-slot takeover-holder terminal
[[ $rc -eq 0 ]] || fail "successor release failed: $output"

partial_holder=partial-holder
partial_generation=1
partial_digest="$(printf '%s\0%s\0%s\0' "$slot_id" "$partial_holder" \
  "$partial_generation" | git hash-object --stdin)"
partial_waiter="$slot_id-waiter-${partial_digest:0:12}"
partial_metadata="$(jq -cn --arg slot "$slot_id" --arg holder "$partial_holder" \
  --arg actor actor-a --arg waiter "$partial_waiter" \
  --argjson generation "$partial_generation" \
  '{slot_id: $slot, holder: $holder, lease_actor: $actor,
    generation: $generation, waiter_id: $waiter}')"
bd create "Merge-slot waiter: $partial_holder" --id "$partial_waiter" \
  --labels gt:slot-waiter --metadata "$partial_metadata" --silent >/dev/null
run_contract actor-a acquire-slot "$partial_holder" 1 0
[[ $rc -eq 0 ]] || fail "create-before-link reconciliation failed: $output"
assert_record "$slot_id" "$partial_holder" 1 in_progress actor-a actor-a
run_contract actor-a release-slot "$partial_holder" terminal
[[ $rc -eq 0 ]] || fail "reconciled waiter release failed: $output"

printf 'PASS: real Beads retry, lease takeover, generations, and parent-child reconciliation\n'
