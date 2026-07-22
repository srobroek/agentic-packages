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
  actor="actor-a"
  touch "$state/bd.log" "$state/gh.log" "$state/git.log" "$state/interactions.jsonl"
}

run_contract() {
  set +e
  last_output="$(PATH="$FIXTURE_BIN:$SYSTEM_PATH" \
    FAKE_STATE="$state" FAKE_SCENARIO="$scenario" BEADS_ACTOR="$actor" \
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

assert_not_file() {
  local file="$1"
  local message="$2"
  tests=$((tests + 1))
  if [[ -e "$file" ]]; then
    printf 'not ok %s: unexpected %s\n' "$message" "$file" >&2
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

assert_waiter_status() {
  local holder="$1"
  local expected="$2"
  local message="$3"
  local generation="${4:-1}"
  local digest waiter actual

  digest="$(printf 'slot-1\0%s\0%s\0' "$holder" "$generation" | sha1sum | awk '{print $1}')"
  waiter="slot-1-waiter-${digest:0:12}"
  actual="missing"
  [[ ! -f "$state/waiters/$waiter/status" ]] || actual="$(<"$state/waiters/$waiter/status")"
  assert_eq "$expected" "$actual" "$message"
}

waiter_path() {
  local holder="$1"
  local generation="${2:-1}"
  local digest

  digest="$(printf 'slot-1\0%s\0%s\0' "$holder" "$generation" | sha1sum | awk '{print $1}')"
  printf '%s/waiters/slot-1-waiter-%s\n' "$state" "${digest:0:12}"
}

native_holder_for() {
  local holder="$1"
  local generation="$2"
  local lease_actor="$3"
  local waiter digest

  waiter="$(waiter_path "$holder" "$generation")"
  waiter="${waiter##*/}"
  digest="$(printf '%s\0%s\0%s\0%s\0' "$holder" "$generation" "$lease_actor" "$waiter" |
    sha1sum | awk '{print $1}')"
  printf 'pr-shepherd:%s\n' "$digest"
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
waiter_creates="$(grep -c -- '^create Merge-slot waiter:' "$state/bd.log" || true)"
assert_eq 1 "$waiter_creates" "slot waiter record is created once"
assert_waiter_status stable-holder in_progress "acquired waiter record is owned"
assert_not_contains_file "--wait" "$state/bd.log" "native shared waiter queue is never used"

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

new_state slot-fairness-tie
scenario=slot-fairness-tie
run_contract acquire-slot tie-b 1 0
assert_eq 75 "$last_rc" "equal-time waiter records use id as the deterministic tie-break"
assert_not_contains_file "merge-slot acquire" "$state/bd.log" \
  "higher waiter id cannot bypass the equal-time lower id"

new_state slot-queued-restart
scenario=slot-queued-restart
run_contract acquire-slot stable-holder 1 0
assert_eq 75 "$last_rc" "contended pass leaves one durable waiter"
assert_contains "persisted=true" "$last_output" "queued receipt is reported"
touch "$state/make-available"
run_contract acquire-slot stable-holder 1 0
assert_eq 0 "$last_rc" "restart resumes from the durable waiter"
waiter_creates="$(grep -c -- '^create Merge-slot waiter:' "$state/bd.log" || true)"
assert_eq 1 "$waiter_creates" "restart does not create a duplicate waiter record"
assert_waiter_status stable-holder in_progress "restart claims its durable waiter record"

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

new_state slot-cleanup-failure
scenario=slot-cleanup-failure
run_contract acquire-slot stable-holder 1 0
assert_eq 2 "$last_rc" "waiter claim failure is surfaced"
assert_not_contains_file "merge-slot acquire" "$state/bd.log" \
  "claim failure is rejected before native slot entry"
assert_waiter_status stable-holder open "claim failure leaves its waiter recoverable"

new_state slot-cleanup-signal
scenario=slot-cleanup-signal
run_contract acquire-slot stable-holder 1 0
assert_eq 143 "$last_rc" "signal during waiter claim is surfaced"
assert_not_contains_file "merge-slot acquire" "$state/bd.log" \
  "claim signal occurs before native slot entry"
assert_waiter_status stable-holder open "claim signal leaves its waiter recoverable"

new_state slot-record-eligibility-interleave
scenario=slot-record-eligibility-interleave
run_contract with-slot stable-holder -- touch "$state/command-ran"
assert_eq 0 "$last_rc" "front waiter acquires across a concurrent later enqueue"
assert_file "$state/command-ran" "eligible waiter runs its protected command"
assert_waiter_status stable-holder closed "normal completion closes only the owned waiter"
assert_waiter_status later-holder open "waiter created before acquire survives completion"

new_state slot-record-holder-race
scenario=slot-record-holder-race
run_contract acquire-slot stable-holder 2 0
assert_eq 75 "$last_rc" "atomic holder race preserves the queued request"
assert_waiter_status stable-holder open "losing acquisition keeps its waiter open"
assert_waiter_status successor in_progress "concurrent holder record survives acquisition race"

new_state slot-record-close-interleave
scenario=slot-record-close-interleave
run_contract with-slot stable-holder -- touch "$state/command-ran"
assert_eq 0 "$last_rc" "target close tolerates a concurrent waiter creation"
assert_waiter_status stable-holder closed "target close is atomic to the owned waiter"
assert_waiter_status later-holder open "concurrent waiter survives target close"

new_state slot-retryable-release
scenario=slot-retryable-release
run_contract with-slot stable-holder -- bash -c 'exit 10'
assert_eq 10 "$last_rc" "retryable protected outcome is preserved"
assert_file "$state/released" "retryable outcome releases the native slot"
assert_waiter_status stable-holder open "retryable release keeps the same waiter open"
retry_waiter="$(waiter_path stable-holder)"
assert_eq actor-a "$(<"$retry_waiter/lease-actor")" \
  "retryable waiter retains its exact actor lease"
assert_eq "" "$(<"$retry_waiter/assignee")" \
  "retryable waiter becomes claimable by its leased actor"
run_contract with-slot stable-holder -- touch "$state/retry-ran"
assert_eq 0 "$last_rc" "same actor reacquires the retryable waiter"
assert_file "$state/retry-ran" "reacquired waiter runs the protected command"
waiter_creates="$(grep -c -- '^create Merge-slot waiter:' "$state/bd.log" || true)"
assert_eq 1 "$waiter_creates" "retryable reacquisition does not create a generation"
assert_waiter_status stable-holder closed "terminal completion closes the retryable attempt"
run_contract acquire-slot stable-holder 1 0
assert_eq 2 "$last_rc" "closed attempt cannot restart without explicit requeue"
run_contract acquire-slot stable-holder 1 0 requeue
assert_eq 0 "$last_rc" "explicit requeue creates the next deterministic generation"
assert_waiter_status stable-holder in_progress "requeue owns generation two" 2
run_contract release-slot stable-holder terminal
assert_eq 0 "$last_rc" "generation two releases terminally"

new_state slot-foreign-lease
scenario=slot-foreign-lease
run_contract acquire-slot stable-holder 1 0
assert_eq 0 "$last_rc" "lease owner acquires the slot"
acquire_calls="$(grep -c -- '^merge-slot acquire' "$state/bd.log" || true)"
actor="actor-b"
run_contract acquire-slot stable-holder 1 0
assert_eq 2 "$last_rc" "foreign live actor is rejected for the same holder"
assert_contains "leased to another actor" "$last_output" "foreign lease rejection is explicit"
assert_eq "$acquire_calls" "$(grep -c -- '^merge-slot acquire' "$state/bd.log" || true)" \
  "foreign actor is rejected before native slot entry"
release_calls="$(grep -c -- '^merge-slot release' "$state/bd.log" || true)"
run_contract release-slot stable-holder terminal
assert_eq 2 "$last_rc" "foreign actor cannot release another actor's slot"
assert_eq "$release_calls" "$(grep -c -- '^merge-slot release' "$state/bd.log" || true)" \
  "foreign actor is rejected before native slot release"
actor="actor-a"
run_contract release-slot stable-holder terminal
assert_eq 0 "$last_rc" "lease owner can terminate its waiter"

new_state recover-claim-waiter
scenario=recover-claim-waiter
actor="actor-b"
run_contract recover-claim merge-1 dead-actor session-registry:dead stable-holder
assert_eq 0 "$last_rc" "evidence-gated dead claim transfers the waiter lease"
takeover_waiter="$(waiter_path stable-holder)"
assert_eq closed "$(<"$takeover_waiter/status")" \
  "takeover closes the dead waiter generation"
takeover_waiter="$(waiter_path stable-holder 2)"
assert_eq actor-b "$(<"$takeover_waiter/lease-actor")" \
  "takeover creates a successor-leased generation"
assert_eq actor-b "$(<"$takeover_waiter/assignee")" \
  "successor atomically claims its fresh generation"
run_contract acquire-slot stable-holder 1 0
assert_eq 0 "$last_rc" "successor reacquires after durable dead-claim recovery"
run_contract release-slot stable-holder terminal
assert_eq 0 "$last_rc" "successor terminally releases the recovered waiter"

new_state recover-claim-waiter-competitor-before-acquire
scenario=recover-claim-waiter-competitor-before-acquire
actor="actor-c"
run_contract recover-claim merge-1 dead-actor session-registry:winner stable-holder
assert_eq 2 "$last_rc" "blocked first successor leaves its fresh generation retryable"
assert_waiter_status stable-holder open "blocked successor keeps generation two queued" 2
queued_successor="$(waiter_path stable-holder 2)"
assert_eq actor-c "$(<"$queued_successor/lease-actor")" \
  "queued successor owns the generation lease"
actor="actor-b"
run_contract recover-claim merge-1 dead-actor session-registry:loser stable-holder
assert_eq 2 "$last_rc" "competitor cannot take a queued successor generation"
assert_eq actor-c "$(<"$queued_successor/lease-actor")" \
  "loser leaves the queued successor lease unchanged"
assert_not_file "$state/recovery-key" "competitors before acquire record no recovery receipt"
assert_waiter_status stable-holder closed "first successor closes the dead generation before queueing" 1
assert_not_file "$state/claim-released" "competitors before acquire leave the merge claim untouched"
release_calls="$(grep -c -- '^merge-slot release' "$state/bd.log" || true)"
assert_eq 1 "$release_calls" "later competitor does not repeat dead-token release"

new_state recover-claim-waiter-delayed-loser
scenario=recover-claim-waiter-delayed-loser
actor="actor-b"
run_contract recover-claim merge-1 dead-actor session-registry:loser stable-holder
assert_eq 2 "$last_rc" "delayed loser cannot release a newly acquired successor token"
winner_waiter="$(waiter_path stable-holder 2)"
assert_eq actor-c "$(<"$winner_waiter/lease-actor")" \
  "delayed loser preserves the winner lease"
assert_eq in_progress "$(<"$winner_waiter/status")" \
  "delayed loser preserves the winner waiter state"
assert_not_contains_file "recovery_key=" "$state/bd.log" \
  "delayed loser records no recovery receipt"
assert_waiter_status stable-holder closed "interleaved winner closes the dead generation" 1
assert_not_file "$state/claim-released" "delayed loser leaves the merge claim untouched"
assert_eq "$(native_holder_for stable-holder 2 actor-c)" "$(<"$state/holder")" \
  "delayed loser preserves the winner native holder token"

new_state recover-claim-waiter-release-before-close
scenario=recover-claim-waiter-release-before-close
actor="actor-b"
run_contract recover-claim merge-1 dead-actor session-registry:loser stable-holder
assert_eq 2 "$last_rc" "release-before-close loser cannot take the successor generation"
assert_waiter_status stable-holder closed "exact cleanup leaves the dead generation closed" 1
winner_waiter="$(waiter_path stable-holder 2)"
assert_eq actor-c "$(<"$winner_waiter/lease-actor")" \
  "exact cleanup preserves the concurrent successor lease"
assert_eq in_progress "$(<"$winner_waiter/status")" \
  "exact cleanup preserves the concurrent successor waiter"
assert_eq "$(native_holder_for stable-holder 2 actor-c)" "$(<"$state/holder")" \
  "exact cleanup preserves the concurrent successor holder"
assert_eq winner-receipt "$(<"$state/recovery-key")" \
  "exact cleanup preserves the concurrent successor receipt"
assert_eq complete "$(<"$state/recovery-phase")" \
  "exact cleanup preserves the concurrent successor receipt phase"
assert_eq actor-c "$(<"$state/claim-assignee")" \
  "exact cleanup preserves the concurrent successor claim"

new_state recover-claim-waiter-after-release
scenario=recover-claim-waiter-after-release
actor="actor-c"
run_contract recover-claim merge-1 dead-actor session-registry:winner stable-holder
assert_eq 0 "$last_rc" "first successor completes recovery after dead release"
winner_receipt="$(<"$state/recovery-key")"
actor="actor-b"
run_contract recover-claim merge-1 dead-actor session-registry:loser stable-holder
assert_eq 2 "$last_rc" "later competitor cannot replace the winning successor"
assert_eq "$winner_receipt" "$(<"$state/recovery-key")" \
  "later competitor preserves the winner receipt"
winner_waiter="$(waiter_path stable-holder 2)"
assert_eq actor-c "$(<"$winner_waiter/lease-actor")" \
  "later competitor preserves the winner generation"
assert_eq actor-c "$(<"$state/claim-assignee")" \
  "later competitor preserves the winner merge claim"
assert_eq complete "$(<"$state/recovery-phase")" \
  "later competitor preserves the completed winner receipt"

new_state slot-link-crash
scenario=slot-link-crash
run_contract acquire-slot stable-holder 1 0
assert_eq 2 "$last_rc" "create-before-link crash fails closed"
assert_not_contains_file "merge-slot acquire" "$state/bd.log" \
  "unlinked waiter is never eligible for native slot entry"
run_contract acquire-slot stable-holder 1 0
assert_eq 0 "$last_rc" "restart reconciles the missing parent-child link"
linked_waiter="$(waiter_path stable-holder)"
assert_eq true "$(<"$linked_waiter/linked")" "reconciled parent-child link persists"
run_contract release-slot stable-holder terminal
assert_eq 0 "$last_rc" "reconciled waiter releases normally"

new_state slot-wrong-link
scenario=slot-wrong-link
run_contract acquire-slot stable-holder 1 0
assert_eq 2 "$last_rc" "wrong-parent waiter fails closed"
assert_not_contains_file "merge-slot acquire" "$state/bd.log" \
  "wrong-parent waiter never enters the native slot"

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
assert_file "$state/waiter-cleaned" "dead waiter record transitions to closed"
assert_waiter_status dead-waiter closed "dead waiter recovery closes its stable record"
assert_contains "pr-shepherd.recover-waiter" "$(<"$state/bd.log")" "dead waiter recovery is audited"
run_contract recover-waiter merge-1 dead-waiter session-registry:dead
assert_eq 0 "$last_rc" "completed waiter cancellation is restart-idempotent"
waiter_closes="$(grep -c -- '^close slot-1-waiter-' "$state/bd.log" || true)"
assert_eq 1 "$waiter_closes" "waiter cancellation closes the target exactly once"

new_state recover-waiter-successor-interleave
scenario=recover-waiter-successor-interleave
run_contract recover-waiter merge-1 dead-waiter session-registry:dead
assert_eq 0 "$last_rc" "waiter recovery survives a concurrent successor slot acquisition"
assert_file "$state/concurrent-state-preserved" \
  "waiter recovery preserves successor ownership and its queued waiter"
assert_waiter_status dead-waiter closed "stale cleanup closes only the stale target"
assert_waiter_status successor in_progress "successor holder record survives stale cleanup"
assert_waiter_status concurrent-waiter open "concurrent queued record survives stale cleanup"

new_state recover-claim
scenario=recover-claim
run_contract recover-claim merge-1 dead-actor session-registry:dead
assert_eq 0 "$last_rc" "dead claim recovery succeeds with evidence"
assert_contains "--assignee  --status open" "$(<"$state/bd.log")" "dead claim is released"

for recovery_kind in slot waiter claim; do
  new_state "recover-$recovery_kind-crash-mutation"
  scenario="recover-$recovery_kind-crash-mutation"
  recovery_subject="dead-$recovery_kind"
  [[ "$recovery_kind" != "slot" ]] || recovery_subject="dead-holder"
  [[ "$recovery_kind" != "waiter" ]] || recovery_subject="dead-waiter"
  [[ "$recovery_kind" != "claim" ]] || recovery_subject="dead-actor"
  run_contract "recover-$recovery_kind" merge-1 "$recovery_subject" session-registry:dead
  assert_eq 2 "$last_rc" "$recovery_kind mutation crash is surfaced"
  assert_eq prepared "$(<"$state/recovery-phase")" "$recovery_kind mutation retains its prepared receipt"
  run_contract "recover-$recovery_kind" merge-1 "$recovery_subject" session-registry:dead
  assert_eq 0 "$last_rc" "$recovery_kind mutation resumes idempotently"
  assert_eq complete "$(<"$state/recovery-phase")" "$recovery_kind recovery receipt completes"
  comment_calls="$(grep -c -- '^comment merge-1 RECOVERED ' "$state/bd.log" || true)"
  audit_calls="$(grep -c -- '^audit record .*pr-shepherd.recover-' "$state/bd.log" || true)"
  assert_eq 1 "$comment_calls" "$recovery_kind recovery emits one durable comment"
  assert_eq 1 "$audit_calls" "$recovery_kind recovery emits one durable audit event"
done

for recovery_kind in slot claim; do
  new_state "recover-$recovery_kind-successor"
  scenario="recover-$recovery_kind-successor"
  recovery_subject="dead-holder"
  [[ "$recovery_kind" != "claim" ]] || recovery_subject="dead-actor"
  run_contract "recover-$recovery_kind" merge-1 "$recovery_subject" session-registry:dead
  assert_eq 2 "$last_rc" "$recovery_kind successor fixture crashes after mutation"
  touch "$state/successor"
  run_contract "recover-$recovery_kind" merge-1 "$recovery_subject" session-registry:dead
  assert_eq 0 "$last_rc" "$recovery_kind recovery accepts valid successor progress"
  run_contract "recover-$recovery_kind" merge-1 "$recovery_subject" session-registry:dead
  assert_eq 0 "$last_rc" "$recovery_kind successor recovery remains idempotent"
  comment_calls="$(grep -c -- '^comment merge-1 RECOVERED ' "$state/bd.log" || true)"
  audit_calls="$(grep -c -- '^audit record .*pr-shepherd.recover-' "$state/bd.log" || true)"
  assert_eq 1 "$comment_calls" "$recovery_kind successor recovery emits one comment"
  assert_eq 1 "$audit_calls" "$recovery_kind successor recovery emits one audit event"
done

new_state recover-slot-crash-comment
scenario=recover-slot-crash-comment
run_contract recover-slot merge-1 dead-holder session-registry:dead
assert_eq 2 "$last_rc" "crash after recovery comment is surfaced"
run_contract recover-slot merge-1 dead-holder session-registry:dead
assert_eq 0 "$last_rc" "recovery resumes after its durable comment"
comment_calls="$(grep -c -- '^comment merge-1 RECOVERED ' "$state/bd.log" || true)"
assert_eq 1 "$comment_calls" "recovery comment marker prevents duplicates"

new_state recover-slot-crash-audit
scenario=recover-slot-crash-audit
run_contract recover-slot merge-1 dead-holder session-registry:dead
assert_eq 2 "$last_rc" "crash after recovery audit is surfaced"
run_contract recover-slot merge-1 dead-holder session-registry:dead
assert_eq 0 "$last_rc" "recovery resumes after its durable audit"
audit_calls="$(grep -c -- '^audit record .*pr-shepherd.recover-' "$state/bd.log" || true)"
assert_eq 1 "$audit_calls" "recovery audit marker prevents duplicates"

new_state recover-receipt-query-error
scenario=recover-receipt-query-error
run_contract recover-slot merge-1 dead-holder session-registry:dead
assert_eq 2 "$last_rc" "recovery receipt query failure is surfaced"
assert_not_contains_file "merge-slot release" "$state/bd.log" \
  "recovery receipt query failure prevents mutation"

new_state recover-comment-query-error
scenario=recover-comment-query-error
run_contract recover-slot merge-1 dead-holder session-registry:dead
assert_eq 2 "$last_rc" "recovery comment query failure is surfaced"
run_contract recover-slot merge-1 dead-holder session-registry:dead
assert_eq 2 "$last_rc" "recovery comment query failure remains fail closed on resume"
assert_not_contains_file "comment merge-1 RECOVERED" "$state/bd.log" \
  "recovery comment query failure cannot emit a duplicate"

new_state recover-audit-query-error
scenario=recover-audit-query-error
run_contract recover-slot merge-1 dead-holder session-registry:dead
assert_eq 2 "$last_rc" "recovery audit query failure is surfaced"
run_contract recover-slot merge-1 dead-holder session-registry:dead
assert_eq 2 "$last_rc" "recovery audit query failure remains fail closed on resume"
comment_calls="$(grep -c -- '^comment merge-1 RECOVERED ' "$state/bd.log" || true)"
assert_eq 1 "$comment_calls" "audit query failure does not duplicate the durable comment"
assert_not_contains_file "audit record" "$state/bd.log" \
  "audit query failure never emits a possibly duplicate audit event"

new_state duplicate-bounce
scenario=duplicate-bounce
run_contract ensure-bounce merge-1 key-1 agent:coder "Fix CI" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 0 "$last_rc" "first bounce reuses matching fix bead"
assert_contains BOUNCE_PARKED "$last_output" "first bounce parks merge bead"
assert_not_contains_file "create" "$state/bd.log" "matching fix bead prevents duplicate creation"
run_contract ensure-bounce merge-1 key-1 agent:coder "Fix CI" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 0 "$last_rc" "second bounce is idempotent"
assert_contains BOUNCE_REUSED "$last_output" "second bounce reports reuse"

new_state bounce-receipt-query-error
scenario=bounce-receipt-query-error
run_contract ensure-bounce merge-1 key-1 agent:coder "Fix CI" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 2 "$last_rc" "bounce receipt query failure is surfaced"
assert_not_contains_file "create" "$state/bd.log" \
  "bounce receipt query failure prevents duplicate fix creation"

new_state bounce-comment-query-error
scenario=bounce-comment-query-error
run_contract ensure-bounce merge-1 key-1 agent:coder "Fix CI" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 2 "$last_rc" "bounce comment query failure is surfaced"
run_contract ensure-bounce merge-1 key-1 agent:coder "Fix CI" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 2 "$last_rc" "bounce comment query failure remains fail closed on resume"
assert_not_contains_file "comment merge-1 BOUNCED" "$state/bd.log" \
  "bounce comment query failure cannot emit a duplicate"

new_state bounce-dependency-query-error
scenario=bounce-dependency-query-error
run_contract ensure-bounce merge-1 key-1 agent:coder "Fix CI" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 2 "$last_rc" "bounce dependency receipt query failure is surfaced"
run_contract ensure-bounce merge-1 key-1 agent:coder "Fix CI" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 2 "$last_rc" "bounce dependency query failure remains fail closed on resume"
assert_not_contains_file "dep add" "$state/bd.log" \
  "bounce dependency query failure cannot emit a duplicate dependency"

new_state bounce-preexisting-duplicates
scenario=bounce-preexisting-duplicates
run_contract ensure-bounce merge-1 key-1 agent:coder "Fix CI" '{"repo":"owner/repo"}' "exact diagnosis"
assert_eq 0 "$last_rc" "pre-existing duplicate fixes reconcile"
assert_contains "close fix-newer --reason Duplicate of fix-oldest" "$(<"$state/bd.log")" \
  "newer duplicate is deterministically closed"
assert_contains "dep add merge-1 fix-oldest" "$(<"$state/bd.log")" \
  "canonical oldest fix becomes the blocker"
assert_not_contains_file "close fix-oldest" "$state/bd.log" "canonical oldest fix remains open"

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
bounce_merge_comments="$(grep -c -- '^comment merge-1 BOUNCED ' "$state/bd.log" || true)"
bounce_fix_comments="$(<"$state/bounce-fix-comment-count")"
assert_eq 1 "$bounce_merge_comments" "crash after first bounce comment does not duplicate it"
assert_eq 1 "$bounce_fix_comments" "bounce recovery writes the missing correlation once"

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

tests=$((tests + 1))
if grep -R -F -- "update slot-1 --metadata" "$TMP_ROOT" >/dev/null 2>&1; then
  printf 'not ok queue isolation: a scenario rewrote shared slot metadata\n' >&2
  failures=$((failures + 1))
fi

if [[ $failures -gt 0 ]]; then
  printf 'FAIL: %s assertions, %s failures\n' "$tests" "$failures" >&2
  exit 1
fi
printf 'PASS: %s assertions\n' "$tests"
