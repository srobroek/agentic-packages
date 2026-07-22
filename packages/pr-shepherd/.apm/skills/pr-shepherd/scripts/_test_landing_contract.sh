#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SCRIPT_DIR
readonly CONTRACT="$SCRIPT_DIR/landing-contract.sh"
readonly PROBE="$SCRIPT_DIR/merge-probe.sh"
readonly FIXTURE_BIN="$SCRIPT_DIR/test-fixtures/bin"
readonly SYSTEM_PATH="$PATH"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/pr-shepherd-test.XXXXXX")"
readonly TMP_ROOT
readonly EXPECTED_HEAD="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
readonly STALE_HEAD="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
readonly EXPECTED_MERGE="cccccccccccccccccccccccccccccccccccccccc"
readonly REMOTE_BASE="dddddddddddddddddddddddddddddddddddddddd"
readonly RECORDED_BASE="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
export EXPECTED_HEAD STALE_HEAD EXPECTED_MERGE REMOTE_BASE

trap 'rm -rf -- "$TMP_ROOT"' EXIT

tests=0
failures=0
last_output=""
last_rc=0

new_state() {
  local name="$1"
  state="$TMP_ROOT/$name"
  mkdir -p "$state"
  touch "$state/bd.log" "$state/gh.log" "$state/git.log"
}

run_contract() {
  set +e
  last_output="$(PATH="$FIXTURE_BIN:$SYSTEM_PATH" \
    FAKE_STATE="$state" FAKE_SCENARIO="$scenario" \
    "$CONTRACT" "$@" 2>&1)"
  last_rc=$?
  set -e
}

assert_eq() {
  local expected="$1"
  local actual="$2"
  local message="$3"
  tests=$((tests + 1))
  if [[ "$expected" != "$actual" ]]; then
    printf 'not ok %s: expected %q, got %q\n' "$message" "$expected" "$actual" >&2
    failures=$((failures + 1))
  fi
}

assert_contains() {
  local expected="$1"
  local actual="$2"
  local message="$3"
  tests=$((tests + 1))
  if [[ "$actual" != *"$expected"* ]]; then
    printf 'not ok %s: output did not contain %q\n' "$message" "$expected" >&2
    failures=$((failures + 1))
  fi
}

assert_file() {
  local file="$1"
  local message="$2"
  tests=$((tests + 1))
  if [[ ! -f "$file" ]]; then
    printf 'not ok %s: missing %s\n' "$message" "$file" >&2
    failures=$((failures + 1))
  fi
}

assert_not_contains_file() {
  local needle="$1"
  local file="$2"
  local message="$3"
  tests=$((tests + 1))
  if grep -F -- "$needle" "$file" >/dev/null 2>&1; then
    printf 'not ok %s: %s contained %q\n' "$message" "$file" "$needle" >&2
    failures=$((failures + 1))
  fi
}

new_state stale-run
scenario=stale-run
run_contract check-run owner/repo 101 "$EXPECTED_HEAD"
assert_eq 11 "$last_rc" "stale run is rejected"
assert_contains RUN_STALE "$last_output" "stale run is classified"

new_state ready-pr
scenario=ready-pr
run_contract check-pr owner/repo 7 "$EXPECTED_HEAD" main
assert_eq 0 "$last_rc" "live PR readiness does not depend on gh:pr gate resolution"
assert_not_contains_file "gate check" "$state/bd.log" "PR readiness does not consult a gate"

new_state changes-requested
scenario=changes-requested
run_contract check-pr owner/repo 7 "$EXPECTED_HEAD" main
assert_eq 12 "$last_rc" "requested changes are a bounce failure"
assert_contains PR_FAILED "$last_output" "requested changes are classified as failed"

new_state external-approval
scenario=external-approval
run_contract check-pr owner/repo 7 "$EXPECTED_HEAD" main
assert_eq 10 "$last_rc" "standalone readiness requires GitHub approval by default"
run_contract check-pr owner/repo 7 "$EXPECTED_HEAD" main external
assert_eq 0 "$last_rc" "orchestrated readiness can consume prior independent approval"
assert_contains "approval=external" "$last_output" "external approval mode is explicit"

new_state slot-contention
scenario=slot-contention
run_contract acquire-slot stable-holder 3 0
assert_eq 0 "$last_rc" "queued slot acquisition retries"
assert_contains SLOT_OWNED "$last_output" "queued slot eventually acquires"
wait_calls="$(grep -c -- '--wait' "$state/bd.log" || true)"
assert_eq 1 "$wait_calls" "slot waiter is enqueued once"
assert_file "$state/waiter-cleaned" "acquired waiter is removed from persisted queue"

new_state slot-fairness
scenario=slot-fairness
run_contract acquire-slot later-holder 2 0
assert_eq 75 "$last_rc" "available slot does not bypass an earlier persisted waiter"
assert_not_contains_file "merge-slot acquire" "$state/bd.log" "later waiter never attempts acquisition"
SHEPHERD_SLOT_ATTEMPTS=1 run_contract with-slot later-holder -- touch "$state/command-ran"
assert_eq 75 "$last_rc" "slot wrapper stops when an earlier waiter owns priority"
tests=$((tests + 1))
if [[ -f "$state/command-ran" ]]; then
  printf 'not ok queued slot wrapper: protected command ran without ownership\n' >&2
  failures=$((failures + 1))
fi

new_state slot-queued-restart
scenario=slot-queued-restart
run_contract acquire-slot stable-holder 1 0
assert_eq 75 "$last_rc" "contended pass leaves one durable waiter"
assert_contains "persisted=true" "$last_output" "queued receipt is reported"
touch "$state/make-available"
run_contract acquire-slot stable-holder 1 0
assert_eq 0 "$last_rc" "restart resumes from the durable waiter"
wait_calls="$(grep -c -- '--wait' "$state/bd.log" || true)"
assert_eq 1 "$wait_calls" "restart does not enqueue a duplicate waiter"
assert_file "$state/waiter-cleaned" "resumed waiter is cleaned after acquisition"

new_state slot-restart
scenario=slot-restart
run_contract acquire-slot stable-holder 2 0
assert_eq 0 "$last_rc" "restart recognizes stable holder ownership"
assert_contains resumed=true "$last_output" "restart is reported"
assert_not_contains_file "merge-slot acquire" "$state/bd.log" "restart does not enqueue a duplicate waiter"

new_state slot-failure
scenario=slot-failure
run_contract with-slot stable-holder -- bash -c 'exit 23'
assert_eq 23 "$last_rc" "transaction preserves merge failure exit"
assert_file "$state/released" "transaction releases slot after failure"

new_state recover-slot
scenario=recover-slot
run_contract recover-slot merge-1 dead-holder session-registry:dead
assert_eq 0 "$last_rc" "dead slot holder recovery succeeds with evidence"
assert_file "$state/released" "dead holder recovery releases slot"
assert_contains "pr-shepherd.recover-slot" "$(<"$state/bd.log")" "dead holder recovery is audited"

new_state recover-waiter
scenario=recover-waiter
run_contract recover-waiter merge-1 dead-waiter session-registry:dead
assert_eq 0 "$last_rc" "dead queued waiter recovery succeeds with evidence"
assert_file "$state/waiter-cleaned" "dead waiter is removed from persisted queue"
assert_contains "pr-shepherd.recover-waiter" "$(<"$state/bd.log")" "dead waiter recovery is audited"

new_state recover-claim
scenario=recover-claim
run_contract recover-claim merge-1 dead-actor session-registry:dead
assert_eq 0 "$last_rc" "dead claim recovery succeeds with evidence"
assert_contains "--assignee  --status open" "$(<"$state/bd.log")" "dead claim is released"

new_state duplicate-bounce
scenario=duplicate-bounce
run_contract ensure-bounce merge-1 key-1 agent:coder "Fix CI" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 0 "$last_rc" "first bounce reuses matching fix bead"
assert_contains BOUNCE_PARKED "$last_output" "first bounce parks merge bead"
assert_not_contains_file "create" "$state/bd.log" "matching fix bead prevents duplicate creation"
run_contract ensure-bounce merge-1 key-1 agent:coder "Fix CI" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 0 "$last_rc" "second bounce is idempotent"
assert_contains BOUNCE_REUSED "$last_output" "second bounce reports reuse"

new_state bounce-crash-dep
scenario=bounce-crash-dep
run_contract ensure-bounce merge-1 key-1 agent:coder "Fix CI" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 2 "$last_rc" "dependency-write crash is surfaced"
assert_eq fix_ready "$(<"$state/bounce-phase")" "dependency crash leaves a durable fix receipt"
run_contract ensure-bounce merge-1 key-1 agent:coder "Fix CI" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 0 "$last_rc" "dependency-write crash resumes idempotently"
assert_eq complete "$(<"$state/bounce-phase")" "dependency recovery reaches a complete receipt"
dep_calls="$(grep -c -- '^dep add ' "$state/bd.log" || true)"
assert_eq 2 "$dep_calls" "failed dependency write is retried exactly once"

new_state bounce-crash-comment
scenario=bounce-crash-comment
run_contract ensure-bounce merge-1 key-1 agent:reviewer "Fix review" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 2 "$last_rc" "comment-write crash is surfaced"
assert_eq parked "$(<"$state/bounce-phase")" "comment crash leaves a durable parked receipt"
run_contract ensure-bounce merge-1 key-1 agent:reviewer "Fix review" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 0 "$last_rc" "comment-write crash resumes idempotently"
assert_eq complete "$(<"$state/bounce-phase")" "comment recovery reaches a complete receipt"
dep_calls="$(grep -c -- '^dep add ' "$state/bd.log" || true)"
assert_eq 1 "$dep_calls" "comment recovery does not duplicate the dependency"

new_state verify-content
scenario=verify-content
run_contract verify-landed owner/repo 7 main "$RECORDED_BASE" "$EXPECTED_HEAD" "$EXPECTED_MERGE"
assert_eq 0 "$last_rc" "stacked squash landing passes exact content proof"
assert_contains LANDED_CONTENT "$last_output" "stacked landing reports content proof"

new_state verify-commit
scenario=verify-commit
run_contract verify-landed owner/repo 7 main "$RECORDED_BASE" "$EXPECTED_HEAD" "$EXPECTED_MERGE"
assert_eq 0 "$last_rc" "base ancestry proves exact merge commit"
assert_contains LANDED_COMMIT "$last_output" "commit landing reports commit proof"

new_state land-restart
scenario=land-restart
run_contract land merge-1 owner/repo 7 stack/base main "$RECORDED_BASE" "$EXPECTED_HEAD" squash external
assert_eq 0 "$last_rc" "stacked restart closes after eventual main proof"
assert_contains LANDING_COMPLETE "$last_output" "merged restart is recovered"
assert_file "$state/released" "recovered landing releases slot"
assert_contains "close merge-1" "$(<"$state/bd.log")" "recovered landing closes only after proof"

new_state land-waiting
scenario=land-waiting
run_contract land merge-1 owner/repo 7 main main "$RECORDED_BASE" "$EXPECTED_HEAD" squash
assert_eq 10 "$last_rc" "pending PR exits without merging"
assert_file "$state/released" "pending PR releases the slot"
assert_not_contains_file "pr merge" "$state/gh.log" "pending PR does not continue into merge"

new_state land-release-failure
scenario=land-release-failure
run_contract land merge-1 owner/repo 7 main main "$RECORDED_BASE" "$EXPECTED_HEAD" squash
assert_eq 2 "$last_rc" "slot release failure keeps landing non-successful"
assert_not_contains_file "close merge-1" "$state/bd.log" "slot release failure prevents bead close"

new_state land-head-race
scenario=land-head-race
run_contract land merge-1 owner/repo 7 main main "$RECORDED_BASE" "$EXPECTED_HEAD" squash
assert_eq 12 "$last_rc" "atomic head mismatch rejects the merge transaction"
assert_file "$state/atomic-head-guard" "merge command carries the exact expected head"
assert_not_contains_file "close merge-1" "$state/bd.log" "head race cannot close the merge bead"

new_state land-stack-hold
scenario=land-stack-hold
run_contract land merge-1 owner/repo 7 stack/base main "$RECORDED_BASE" "$EXPECTED_HEAD" squash external
assert_eq 10 "$last_rc" "stacked merge remains open until its content reaches main"
assert_contains LANDING_HOLD "$last_output" "stacked merge emits a durable hold state"
assert_contains "landing_state=waiting_base" "$(<"$state/bd.log")" "stacked hold is persisted"
assert_not_contains_file "close merge-1" "$state/bd.log" "stacked merge does not close before main proof"

new_state ready-order
scenario=ready-order
run_contract ready-ids
assert_eq $'merge-second\nmerge-first' "$last_output" "ready queue order is preserved"

set +e
PATH="$SYSTEM_PATH" "$PROBE" conflicts refs/heads/not-a-base refs/heads/not-a-branch \
  >"$TMP_ROOT/probe.out" 2>"$TMP_ROOT/probe.err"
probe_rc=$?
set -e
assert_eq 2 "$probe_rc" "unknown conflict probe does not become clean"

if [[ $failures -gt 0 ]]; then
  printf 'FAIL: %s assertions, %s failures\n' "$tests" "$failures" >&2
  exit 1
fi
printf 'PASS: %s assertions\n' "$tests"
