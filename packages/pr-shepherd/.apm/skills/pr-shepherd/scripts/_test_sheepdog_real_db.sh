#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SCRIPT_DIR
readonly CONTRACT="$SCRIPT_DIR/landing-contract.py"
readonly REPO="owner/repo"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/pr-shepherd-sheepdog.XXXXXX")"
readonly TMP_ROOT
trap 'rm -rf -- "$TMP_ROOT"' EXIT

fail() {
  printf 'real-db sheepdog test: %s\n' "$*" >&2
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

record() {
  BD_JSON_ENVELOPE=1 bd show "$wisp" --json | jq -ce '.data[0]'
}

assert_owner() {
  local status="$1"
  local assignee="$2"
  local actual

  actual="$(record)"
  [[ "$(printf '%s' "$actual" | jq -r '.status')" == "$status" ]] ||
    fail "expected status $status"
  [[ "$(printf '%s' "$actual" | jq -r '.assignee // ""')" == "$assignee" ]] ||
    fail "expected assignee ${assignee:-empty}"
  [[ "$(printf '%s' "$actual" | jq -r '.wisp_type')" == patrol ]] ||
    fail "expected patrol wisp"
}

command -v bd >/dev/null 2>&1 || fail "bd not found"
command -v gh >/dev/null 2>&1 || fail "gh not found"
command -v git >/dev/null 2>&1 || fail "git not found"
command -v jq >/dev/null 2>&1 || fail "jq not found"
git -C "$TMP_ROOT" init -q
cd "$TMP_ROOT"
export BEADS_DIR="$TMP_ROOT/.beads"
bd init --quiet --prefix tst --non-interactive --skip-agents --skip-hooks
audit_bead="$(bd create "Sheepdog recovery audit" --id tst-audit --silent)"

digest="$(printf 'sheepdog\0%s\0' "$REPO" | git hash-object --stdin)"
wisp="tst-wisp-${digest:0:12}"

run_contract actor-a acquire-sheepdog "Owner/Repo"
[[ $rc -eq 0 && "$output" == *"SHEEPDOG_ACQUIRED"* ]] ||
  fail "initial acquire failed: $output"
assert_owner in_progress actor-a

run_contract actor-b acquire-sheepdog "$REPO"
[[ $rc -eq 75 && "$output" == *"SHEEPDOG_HELD"* ]] ||
  fail "foreign acquire was not refused: $output"
assert_owner in_progress actor-a
[[ "$(bd merge-slot check --json | jq -r '.available')" == true ]] ||
  fail "refused acquire stranded the transition slot"

run_contract actor-b touch-sheepdog "$REPO"
[[ $rc -eq 2 && "$output" == *"is not owned by actor-b"* ]] ||
  fail "foreign touch was not refused: $output"
[[ "$(bd merge-slot check --json | jq -r '.available')" == true ]] ||
  fail "foreign touch stranded the transition slot"

run_contract actor-a touch-sheepdog "$REPO"
[[ $rc -eq 0 && "$output" == *"SHEEPDOG_TOUCHED"* ]] ||
  fail "owner touch failed: $output"
assert_owner in_progress actor-a

run_contract actor-a release-sheepdog "$REPO"
[[ $rc -eq 0 && "$output" == *"SHEEPDOG_RELEASED"* ]] ||
  fail "owner release failed: $output"
assert_owner closed ""

run_contract actor-b acquire-sheepdog "$REPO"
[[ $rc -eq 0 ]] || fail "next generation acquire failed: $output"
assert_owner in_progress actor-b

BEADS_ACTOR=actor-b bd close "$wisp" --reason "simulated crash after close" >/dev/null
assert_owner closed actor-b
run_contract actor-c acquire-sheepdog "$REPO"
[[ $rc -eq 0 ]] || fail "terminal crash recovery failed: $output"
assert_owner in_progress actor-c

run_contract actor-d recover-sheepdog "$REPO" wrong-actor dead-session "$audit_bead"
[[ $rc -eq 2 && "$output" == *"no longer belongs to wrong-actor"* ]] ||
  fail "wrong-holder recovery was not refused: $output"
assert_owner in_progress actor-c
[[ "$(bd merge-slot check --json | jq -r '.available')" == true ]] ||
  fail "wrong-holder recovery stranded the transition slot"

run_contract actor-d recover-sheepdog "$REPO" actor-c dead-session "$audit_bead"
[[ $rc -eq 0 && "$output" == *"SHEEPDOG_RECOVERED"* ]] ||
  fail "evidence-gated recovery failed: $output"
assert_owner in_progress actor-d
bd comments "$audit_bead" --json | jq -e \
  'any(.[]; .text | contains("kind=sheepdog"))' >/dev/null ||
  fail "recovery evidence was not written to the audit bead"

bd merge-slot acquire --holder external-test >/dev/null
run_contract actor-d release-sheepdog "$REPO"
[[ $rc -eq 75 && "$output" == *"SHEEPDOG_WAITING"* ]] ||
  fail "transition contention was not reported: $output"
assert_owner in_progress actor-d
bd merge-slot release --holder external-test >/dev/null

run_contract actor-d release-sheepdog "$REPO"
[[ $rc -eq 0 ]] || fail "final release failed: $output"
assert_owner closed ""

count="$(bd mol wisp list --all --json | jq \
  --arg title "[wisp:patrol] sheepdog $REPO" \
  '[.wisps[] | select(.title == $title)] | length')"
[[ "$count" -eq 1 ]] || fail "expected one deterministic sheepdog, found $count"

printf 'PASS: sheepdog lease contention, touch, release, recovery, and slot safety\n'
