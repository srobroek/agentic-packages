#!/usr/bin/env bash
set -Eeuo pipefail

readonly EXIT_UNKNOWN=2
readonly EXIT_WAITING=10
readonly EXIT_STALE=11
readonly EXIT_FAILED=12
readonly EXIT_SLOT_QUEUED=75
readonly QUERY_FOUND=0
readonly QUERY_ABSENT=1
readonly QUERY_ERROR=2
readonly WAITER_LABEL=gt:slot-waiter
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SCRIPT_DIR

fail() {
  printf 'landing-contract: %s\n' "$*" >&2
  exit "$EXIT_UNKNOWN"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 not found"
}

require_sha() {
  local value="$1"
  local name="$2"

  if [[ ${#value} -ne 40 || "$value" == *[!0-9a-fA-F]* ]]; then
    fail "$name must be a 40-character hexadecimal SHA"
  fi
}

slot_state() {
  bd merge-slot check --json
}

slot_holder() {
  jq -r '.holder // empty'
}

slot_available() {
  jq -e '.available == true' >/dev/null
}

arm_slot_release() {
  local holder="$1"
  local release_trap

  printf -v release_trap 'release_slot %q >/dev/null || true' "$holder"
  # Capture the holder value before the caller's local scope unwinds.
  # shellcheck disable=SC2064
  trap "$release_trap" EXIT
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
}

disarm_slot_release() {
  trap - HUP INT TERM EXIT
}

waiter_id() {
  local slot_id="$1"
  local holder="$2"
  local generation="$3"
  local digest

  digest="$(printf '%s\0%s\0%s\0' "$slot_id" "$holder" "$generation" | git hash-object --stdin)" ||
    fail "cannot derive waiter identity"
  printf '%s-waiter-%s\n' "$slot_id" "${digest:0:12}"
}

native_holder_token() {
  local holder="$1"
  local record="$2"
  local waiter generation lease digest

  waiter="$(printf '%s' "$record" | jq -er '.id')" || return "$QUERY_ERROR"
  generation="$(printf '%s' "$record" | jq -er '.metadata.generation')" ||
    return "$QUERY_ERROR"
  lease="$(printf '%s' "$record" | jq -er '.metadata.lease_actor | select(length > 0)')" ||
    return "$QUERY_ERROR"
  digest="$(printf '%s\0%s\0%s\0%s\0' "$holder" "$generation" "$lease" "$waiter" |
    git hash-object --stdin)" || return "$QUERY_ERROR"
  printf 'pr-shepherd:%s\n' "$digest"
}

current_actor() {
  [[ -n "${BEADS_ACTOR:-}" ]] || fail "BEADS_ACTOR is required for merge-slot waiters"
  printf '%s\n' "$BEADS_ACTOR"
}

waiter_link_state() {
  local record="$1"
  local slot_id="$2"
  local parent_count parent_id

  parent_count="$(printf '%s' "$record" | jq -er \
    '[.dependencies[]? | select(.type == "parent-child")] | length')" ||
    return "$QUERY_ERROR"
  if [[ $parent_count -eq 0 ]]; then
    return "$QUERY_ABSENT"
  fi
  [[ $parent_count -eq 1 ]] || return "$QUERY_ERROR"
  parent_id="$(printf '%s' "$record" | jq -er \
    '[.dependencies[]? | select(.type == "parent-child")][0].depends_on_id')" ||
    return "$QUERY_ERROR"
  [[ "$parent_id" == "$slot_id" ]] || return "$QUERY_ERROR"
}

waiter_record_state() {
  local waiter="$1"
  local slot_id="$2"
  local holder="$3"
  local generation="$4"
  local records count

  records="$(bd list --id "$waiter" --all --json)" || return "$QUERY_ERROR"
  count="$(printf '%s' "$records" | jq -er 'length')" || return "$QUERY_ERROR"
  if [[ $count -eq 0 ]]; then
    return "$QUERY_ABSENT"
  fi
  [[ $count -eq 1 ]] || return "$QUERY_ERROR"
  printf '%s' "$records" | jq -ce --arg slot "$slot_id" --arg holder "$holder" \
    --arg waiter "$waiter" --argjson generation "$generation" \
    '.[0] |
     select(.id == $waiter and .metadata.slot_id == $slot and
       .metadata.holder == $holder and .metadata.waiter_id == $waiter and
       .metadata.generation == $generation) |
     {id, status, created_at, assignee: (.assignee // ""), metadata,
       dependencies: (.dependencies // [])}' || return "$QUERY_ERROR"
}

ensure_waiter_link() {
  local waiter="$1"
  local slot_id="$2"
  local holder="$3"
  local generation="$4"
  local record query_rc

  record="$(waiter_record_state "$waiter" "$slot_id" "$holder" "$generation")" ||
    fail "cannot query waiter $waiter dependency"
  if waiter_link_state "$record" "$slot_id"; then
    return 0
  else
    query_rc=$?
  fi
  [[ $query_rc -eq $QUERY_ABSENT ]] || fail "waiter $waiter has invalid parent linkage"
  if ! bd dep add "$waiter" "$slot_id" --type parent-child >/dev/null; then
    record="$(waiter_record_state "$waiter" "$slot_id" "$holder" "$generation")" ||
      fail "cannot reconcile waiter $waiter dependency"
    waiter_link_state "$record" "$slot_id" ||
      fail "cannot link waiter $waiter to merge slot $slot_id"
    return 0
  fi
  record="$(waiter_record_state "$waiter" "$slot_id" "$holder" "$generation")" ||
    fail "cannot verify waiter $waiter dependency"
  waiter_link_state "$record" "$slot_id" ||
    fail "waiter $waiter parent linkage did not persist"
}

waiter_attempts() {
  local slot_id="$1"
  local holder="$2"

  bd list --label "$WAITER_LABEL" --all --metadata-field "slot_id=$slot_id" \
    --metadata-field "holder=$holder" --limit 0 --json
}

waiter_record_by_id() {
  local waiter="$1"
  local slot_id="$2"
  local holder="$3"
  local records generation expected

  records="$(bd list --id "$waiter" --all --json)" || return "$QUERY_ERROR"
  [[ "$(printf '%s' "$records" | jq -er 'length')" -eq 1 ]] || return "$QUERY_ERROR"
  generation="$(printf '%s' "$records" | jq -er \
    '.[0].metadata.generation | select(type == "number" and . >= 1 and floor == .)')" ||
    return "$QUERY_ERROR"
  expected="$(waiter_id "$slot_id" "$holder" "$generation")" || return "$QUERY_ERROR"
  [[ "$waiter" == "$expected" ]] || return "$QUERY_ERROR"
  waiter_record_state "$waiter" "$slot_id" "$holder" "$generation"
}

active_waiter_record() {
  local slot_id="$1"
  local holder="$2"
  local attempts count

  attempts="$(waiter_attempts "$slot_id" "$holder")" || return "$QUERY_ERROR"
  count="$(printf '%s' "$attempts" | jq -er \
    '[.[] | select(.status == "open" or .status == "in_progress")] | length')" ||
    return "$QUERY_ERROR"
  if [[ $count -eq 0 ]]; then
    return "$QUERY_ABSENT"
  fi
  [[ $count -eq 1 ]] || return "$QUERY_ERROR"
  printf '%s' "$attempts" | jq -ce \
    '[.[] | select(.status == "open" or .status == "in_progress")][0]'
}

ensure_waiter_record() {
  local slot_id="$1"
  local holder="$2"
  local mode="${3:-resume}"
  local actor attempts active_count terminal_count generation waiter record metadata status

  [[ "$mode" == "resume" || "$mode" == "requeue" ]] ||
    fail "waiter mode must be resume or requeue"
  actor="$(current_actor)"
  attempts="$(waiter_attempts "$slot_id" "$holder")" ||
    fail "cannot query durable waiter attempts"
  active_count="$(printf '%s' "$attempts" | jq -er \
    '[.[] | select(.status == "open" or .status == "in_progress")] | length')" ||
    fail "invalid waiter attempt records"
  [[ $active_count -le 1 ]] || fail "multiple active waiter attempts exist for $holder"
  if [[ $active_count -eq 1 ]]; then
    record="$(printf '%s' "$attempts" | jq -ce \
      '[.[] | select(.status == "open" or .status == "in_progress")][0]')" ||
      fail "cannot select active waiter attempt"
    generation="$(printf '%s' "$record" | jq -er '.metadata.generation')" ||
      fail "active waiter generation is invalid"
    waiter="$(waiter_id "$slot_id" "$holder" "$generation")"
    record="$(waiter_record_state "$waiter" "$slot_id" "$holder" "$generation")" ||
      fail "active waiter identity is invalid"
    [[ "$(printf '%s' "$record" | jq -r '.metadata.lease_actor // ""')" == "$actor" ]] ||
      fail "waiter $waiter is leased to another actor"
    ensure_waiter_link "$waiter" "$slot_id" "$holder" "$generation"
    printf '%s\n' "$waiter"
    return 0
  fi

  terminal_count="$(printf '%s' "$attempts" | jq -er 'length')" ||
    fail "invalid waiter attempt records"
  if [[ $terminal_count -gt 0 && "$mode" != "requeue" ]]; then
    fail "terminal waiter for $holder requires explicit requeue"
  fi
  generation="$(printf '%s' "$attempts" | jq -er \
    '([.[].metadata.generation] | max // 0) + 1')" ||
    fail "cannot derive waiter generation"
  waiter="$(waiter_id "$slot_id" "$holder" "$generation")"
  metadata="$(jq -cn --arg slot "$slot_id" --arg holder "$holder" \
    --arg actor "$actor" --arg waiter "$waiter" --argjson generation "$generation" \
    '{slot_id: $slot, holder: $holder, lease_actor: $actor,
      generation: $generation, waiter_id: $waiter}')"
  if ! bd create "Merge-slot waiter: $holder" --id "$waiter" \
    --labels "$WAITER_LABEL" --metadata "$metadata" --silent >/dev/null; then
    record="$(waiter_record_state "$waiter" "$slot_id" "$holder" "$generation")" ||
      fail "cannot create or recover durable waiter $waiter"
    [[ "$(printf '%s' "$record" | jq -r '.metadata.lease_actor // ""')" == "$actor" ]] ||
      fail "recovered waiter $waiter is leased to another actor"
  else
    record="$(waiter_record_state "$waiter" "$slot_id" "$holder" "$generation")" ||
      fail "created waiter $waiter is not queryable"
  fi
  ensure_waiter_link "$waiter" "$slot_id" "$holder" "$generation"
  status="$(printf '%s' "$record" | jq -r '.status')"
  case "$status" in
  open | in_progress) ;;
  closed) fail "durable waiter $waiter is already terminal" ;;
  *) fail "durable waiter $waiter has invalid status ${status:-empty}" ;;
  esac
  printf '%s\n' "$waiter"
}

first_waiter_record() {
  local slot_id="$1"
  local records row waiter holder generation expected

  records="$(bd list --label "$WAITER_LABEL" --status open,in_progress \
    --metadata-field "slot_id=$slot_id" --limit 0 --json)" ||
    fail "cannot query merge-slot waiter records"
  while IFS= read -r row; do
    [[ -n "$row" ]] || continue
    waiter="$(printf '%s' "$row" | jq -er '.id')" ||
      fail "invalid merge-slot waiter id"
    holder="$(printf '%s' "$row" | jq -er '.metadata.holder')" ||
      fail "invalid merge-slot waiter holder"
    generation="$(printf '%s' "$row" | jq -er \
      '.metadata.generation | select(type == "number" and . >= 1 and floor == .)')" ||
      fail "invalid merge-slot waiter generation"
    expected="$(waiter_id "$slot_id" "$holder" "$generation")"
    [[ "$waiter" == "$expected" ]] || fail "merge-slot waiter $waiter has invalid identity"
    [[ "$(printf '%s' "$row" | jq -r '.metadata.waiter_id // ""')" == "$waiter" ]] ||
      fail "merge-slot waiter $waiter has invalid identity metadata"
    waiter_link_state "$row" "$slot_id" ||
      fail "merge-slot waiter $waiter has invalid parent linkage"
  done < <(printf '%s' "$records" | jq -c '.[]')
  printf '%s' "$records" | jq -r --arg slot "$slot_id" \
    '[.[] |
      select((.status == "open" or .status == "in_progress") and
        .metadata.slot_id == $slot and
        (.id | type) == "string" and (.id | length) > 0 and
        (.created_at | type) == "string" and (.created_at | length) > 0 and
        (.metadata.holder | type) == "string" and (.metadata.holder | length) > 0)] |
     sort_by(.created_at, .id) | .[0] |
     if . == null then "|" else [(.id // ""), .metadata.holder] | join("|") end'
}

claim_waiter_record() {
  local waiter="$1"
  local slot_id="$2"
  local holder="$3"
  local actor record status assignee lease

  actor="$(current_actor)"
  record="$(waiter_record_by_id "$waiter" "$slot_id" "$holder")" ||
    fail "cannot query waiter before claim"
  status="$(printf '%s' "$record" | jq -r '.status')"
  assignee="$(printf '%s' "$record" | jq -r '.assignee // ""')"
  lease="$(printf '%s' "$record" | jq -r '.metadata.lease_actor // ""')"
  [[ "$lease" == "$actor" ]] || fail "waiter $waiter is leased to another actor"
  if [[ "$status" == "open" ]]; then
    [[ -z "$assignee" ]] || fail "open waiter $waiter has a foreign assignee"
    BEADS_ACTOR="$actor" bd update "$waiter" --claim >/dev/null ||
      fail "cannot claim owned waiter $waiter"
    record="$(waiter_record_by_id "$waiter" "$slot_id" "$holder")" ||
      fail "cannot verify waiter claim"
    status="$(printf '%s' "$record" | jq -r '.status')"
    assignee="$(printf '%s' "$record" | jq -r '.assignee // ""')"
  fi
  [[ "$status" == "in_progress" && "$assignee" == "$actor" ]] ||
    fail "waiter $waiter is not owned by $actor"
  waiter_link_state "$record" "$slot_id" || fail "owned waiter $waiter lost parent linkage"
}

validate_waiter_owner() {
  local slot_id="$1"
  local holder="$2"
  local actor record waiter status assignee lease

  actor="$(current_actor)"
  record="$(active_waiter_record "$slot_id" "$holder")" ||
    fail "cannot find active waiter for owned slot $holder"
  waiter="$(printf '%s' "$record" | jq -er '.id')" || fail "invalid waiter identity"
  record="$(waiter_record_by_id "$waiter" "$slot_id" "$holder")" ||
    fail "cannot validate waiter $waiter ownership"
  waiter_link_state "$record" "$slot_id" || fail "waiter $waiter has invalid parent linkage"
  status="$(printf '%s' "$record" | jq -r '.status')"
  assignee="$(printf '%s' "$record" | jq -r '.assignee // ""')"
  lease="$(printf '%s' "$record" | jq -r '.metadata.lease_actor // ""')"
  [[ "$lease" == "$actor" && "$status" == "in_progress" && "$assignee" == "$actor" ]] ||
    fail "waiter $waiter is not owned by $actor"
}

release_waiter_record() {
  local slot_id="$1"
  local holder="$2"
  local disposition="$3"
  local require_existing="${4:-true}"
  local reason="${5:-merge-slot request completed}"
  local actor waiter record query_rc status assignee lease

  actor="$(current_actor)"
  if record="$(active_waiter_record "$slot_id" "$holder")"; then
    query_rc=$QUERY_FOUND
  else
    query_rc=$?
  fi
  if [[ $query_rc -eq $QUERY_ERROR ]]; then
    fail "cannot query active waiter for $holder"
  fi
  if [[ $query_rc -eq $QUERY_ABSENT ]]; then
    [[ "$require_existing" == "false" ]] && return 0
    fail "active waiter for $holder does not exist"
  fi
  waiter="$(printf '%s' "$record" | jq -er '.id')" || fail "invalid waiter identity"
  record="$(waiter_record_by_id "$waiter" "$slot_id" "$holder")" ||
    fail "cannot validate waiter $waiter for release"
  waiter_link_state "$record" "$slot_id" || fail "waiter $waiter has invalid parent linkage"
  status="$(printf '%s' "$record" | jq -r '.status')"
  assignee="$(printf '%s' "$record" | jq -r '.assignee // ""')"
  lease="$(printf '%s' "$record" | jq -r '.metadata.lease_actor // ""')"
  [[ "$lease" == "$actor" ]] || fail "waiter $waiter is leased to another actor"
  [[ "$status" != "in_progress" || "$assignee" == "$actor" ]] ||
    fail "waiter $waiter is assigned to another actor"
  case "$disposition" in
  retryable)
    bd update "$waiter" --assignee "" --status open >/dev/null ||
      fail "cannot reopen retryable waiter $waiter"
    record="$(waiter_record_by_id "$waiter" "$slot_id" "$holder")" ||
      fail "cannot verify retryable waiter $waiter"
    [[ "$(printf '%s' "$record" | jq -r '.status + "|" + (.assignee // "")')" == "open|" ]] ||
      fail "retryable waiter $waiter did not remain open"
    ;;
  terminal)
    bd close "$waiter" --reason "$reason" >/dev/null || fail "cannot close waiter $waiter"
    record="$(waiter_record_by_id "$waiter" "$slot_id" "$holder")" ||
      fail "cannot verify waiter $waiter close"
    [[ "$(printf '%s' "$record" | jq -r '.status')" == "closed" ]] ||
      fail "waiter $waiter close did not persist"
    ;;
  *) fail "waiter disposition must be retryable or terminal" ;;
  esac
}

close_waiter_record() {
  release_waiter_record "$1" "$2" terminal "${3:-true}" \
    "${4:-merge-slot request completed}"
}

force_close_waiter_record() {
  local slot_id="$1"
  local holder="$2"
  local require_existing="${3:-true}"
  local reason="${4:-recovered dead waiter}"
  local record query_rc waiter attempts count

  if record="$(active_waiter_record "$slot_id" "$holder")"; then
    query_rc=$QUERY_FOUND
  else
    query_rc=$?
  fi
  if [[ $query_rc -eq $QUERY_ABSENT ]]; then
    attempts="$(waiter_attempts "$slot_id" "$holder")" ||
      fail "cannot query terminal waiter for $holder"
    count="$(printf '%s' "$attempts" | jq -er 'length')" ||
      fail "invalid terminal waiter records"
    if [[ $count -gt 0 ]]; then
      record="$(printf '%s' "$attempts" | jq -ce 'sort_by(.metadata.generation) | last')" ||
        fail "cannot select terminal waiter for $holder"
      waiter="$(printf '%s' "$record" | jq -er '.id')" || fail "invalid waiter identity"
      record="$(waiter_record_by_id "$waiter" "$slot_id" "$holder")" ||
        fail "cannot validate terminal waiter $waiter"
      waiter_link_state "$record" "$slot_id" ||
        fail "terminal waiter $waiter has invalid parent linkage"
      [[ "$(printf '%s' "$record" | jq -r '.status')" == "closed" ]] ||
        fail "waiter $waiter has invalid terminal status"
      return 0
    fi
    [[ "$require_existing" == "false" ]] && return 0
    fail "waiter for $holder does not exist"
  fi
  [[ $query_rc -eq $QUERY_FOUND ]] || fail "cannot query active waiter for $holder"
  waiter="$(printf '%s' "$record" | jq -er '.id')" || fail "invalid waiter identity"
  record="$(waiter_record_by_id "$waiter" "$slot_id" "$holder")" ||
    fail "cannot validate waiter $waiter for recovery"
  waiter_link_state "$record" "$slot_id" || fail "waiter $waiter has invalid parent linkage"
  bd close "$waiter" --reason "$reason" >/dev/null || fail "cannot close waiter $waiter"
}

close_observed_waiter_generation() {
  local slot_id="$1"
  local holder="$2"
  local observed="$3"
  local expected_lease="$4"
  local reason="$5"
  local waiter generation record status lease

  waiter="$(printf '%s' "$observed" | jq -er '.id')" || fail "invalid observed waiter identity"
  generation="$(printf '%s' "$observed" | jq -er '.metadata.generation')" ||
    fail "invalid observed waiter generation"
  record="$(waiter_record_state "$waiter" "$slot_id" "$holder" "$generation")" ||
    fail "cannot validate observed waiter $waiter"
  waiter_link_state "$record" "$slot_id" ||
    fail "observed waiter $waiter has invalid parent linkage"
  lease="$(printf '%s' "$record" | jq -r '.metadata.lease_actor // ""')"
  [[ "$lease" == "$expected_lease" ]] ||
    fail "observed waiter $waiter lease changed"
  status="$(printf '%s' "$record" | jq -r '.status')"
  if [[ "$status" != "closed" ]]; then
    [[ "$status" == "open" || "$status" == "in_progress" ]] ||
      fail "observed waiter $waiter has invalid status ${status:-empty}"
    bd close "$waiter" --reason "$reason" >/dev/null ||
      fail "cannot close observed waiter $waiter"
  fi
  record="$(waiter_record_state "$waiter" "$slot_id" "$holder" "$generation")" ||
    fail "cannot verify observed waiter $waiter close"
  [[ "$(printf '%s' "$record" | jq -r '.status')" == "closed" ]] ||
    fail "observed waiter $waiter close did not persist"
}

acquire_slot() {
  local holder="$1"
  local attempts="${2:-3}"
  local interval="${3:-1}"
  local protection="${4:-handoff}"
  local waiter_mode="${5:-resume}"
  local state slot_id actual first_waiter first_waiter_id waiter record native_holder rc attempt

  [[ -n "$holder" ]] || fail "slot holder is required"
  [[ "$attempts" =~ ^[1-9][0-9]*$ ]] || fail "attempts must be a positive integer"
  [[ "$interval" =~ ^[0-9]+$ ]] || fail "poll interval must be a non-negative integer"
  [[ "$protection" == "handoff" || "$protection" == "armed" ]] ||
    fail "slot protection must be handoff or armed"
  [[ "$waiter_mode" == "resume" || "$waiter_mode" == "requeue" ]] ||
    fail "waiter mode must be resume or requeue"

  bd merge-slot create >/dev/null
  state="$(slot_state)" || fail "cannot inspect merge slot"
  slot_id="$(printf '%s' "$state" | jq -r '.id // empty')" || fail "invalid merge-slot id"
  [[ -n "$slot_id" ]] || fail "merge-slot id is missing"
  waiter="$(ensure_waiter_record "$slot_id" "$holder" "$waiter_mode")"
  record="$(waiter_record_by_id "$waiter" "$slot_id" "$holder")" ||
    fail "cannot validate waiter before native slot entry"
  native_holder="$(native_holder_token "$holder" "$record")" ||
    fail "cannot derive native holder token"
  attempt=1
  while [[ $attempt -le $attempts ]]; do
    if [[ $attempt -gt 1 && "$interval" -gt 0 ]]; then
      sleep "$interval"
    fi
    state="$(slot_state)" || fail "cannot inspect merge slot"
    actual="$(printf '%s' "$state" | slot_holder)" || fail "invalid merge-slot state"
    if [[ "$actual" == "$native_holder" ]]; then
      claim_waiter_record "$waiter" "$slot_id" "$holder"
      arm_slot_release "$holder"
      [[ "$protection" == "armed" ]] || disarm_slot_release
      printf 'SLOT_OWNED holder=%s resumed=true\n' "$holder"
      return 0
    fi
    if printf '%s' "$state" | slot_available; then
      first_waiter="$(first_waiter_record "$slot_id")"
      IFS='|' read -r first_waiter_id first_waiter <<<"$first_waiter"
      if [[ "$first_waiter_id" == "$waiter" && "$first_waiter" == "$holder" ]]; then
        claim_waiter_record "$waiter" "$slot_id" "$holder"
        first_waiter="$(first_waiter_record "$slot_id")"
        IFS='|' read -r first_waiter_id first_waiter <<<"$first_waiter"
        [[ "$first_waiter_id" == "$waiter" && "$first_waiter" == "$holder" ]] ||
          fail "waiter $waiter lost queue priority during claim"
        set +e
        bd merge-slot acquire --holder "$native_holder" >/dev/null
        rc=$?
        set -e
        if [[ $rc -eq 0 ]]; then
          arm_slot_release "$holder"
          [[ "$protection" == "armed" ]] || disarm_slot_release
          printf 'SLOT_OWNED holder=%s resumed=false\n' "$holder"
          return 0
        fi
        [[ $rc -eq 1 ]] || fail "merge-slot acquire failed with exit $rc"
      fi
    fi
    attempt=$((attempt + 1))
  done

  release_waiter_record "$slot_id" "$holder" retryable true \
    "merge-slot request remains queued"
  printf 'SLOT_QUEUED holder=%s attempts=%s waiter=%s persisted=true\n' \
    "$holder" "$attempts" "$waiter"
  return "$EXIT_SLOT_QUEUED"
}

release_slot() {
  local holder="$1"
  local disposition="${2:-terminal}"
  local state slot_id actual already_available waiter_rc record native_holder

  [[ "$disposition" == "retryable" || "$disposition" == "terminal" ]] ||
    fail "slot release disposition must be retryable or terminal"

  state="$(slot_state)" || {
    printf 'SLOT_RELEASE_UNKNOWN holder=%s\n' "$holder" >&2
    return "$EXIT_UNKNOWN"
  }
  actual="$(printf '%s' "$state" | slot_holder)" || {
    printf 'SLOT_RELEASE_INVALID holder=%s\n' "$holder" >&2
    return "$EXIT_UNKNOWN"
  }
  slot_id="$(printf '%s' "$state" | jq -r '.id // empty')" || {
    printf 'SLOT_RELEASE_INVALID holder=%s\n' "$holder" >&2
    return "$EXIT_UNKNOWN"
  }
  [[ -n "$slot_id" ]] || return "$EXIT_UNKNOWN"
  if printf '%s' "$state" | slot_available; then
    already_available=true
  else
    record="$(active_waiter_record "$slot_id" "$holder")" ||
      fail "cannot find active waiter for native slot release"
    native_holder="$(native_holder_token "$holder" "$record")" ||
      fail "cannot derive native holder token"
    if [[ "$actual" != "$native_holder" ]]; then
      printf 'SLOT_FOREIGN expected=%s actual=%s\n' "$native_holder" "${actual:-unknown}" >&2
      return "$EXIT_FAILED"
    fi
    validate_waiter_owner "$slot_id" "$holder"
    if [[ "$disposition" == "retryable" ]]; then
      if release_waiter_record "$slot_id" "$holder" retryable true \
        "merge-slot request remains retryable"; then
        waiter_rc=0
      else
        waiter_rc=$?
      fi
      [[ $waiter_rc -eq 0 ]] || return "$waiter_rc"
    fi
    if bd merge-slot release --holder "$native_holder" >/dev/null; then
      already_available=false
    else
      printf 'SLOT_RELEASE_FAILED holder=%s\n' "$holder" >&2
      return "$EXIT_UNKNOWN"
    fi
  fi
  if [[ "$already_available" == "true" || "$disposition" == "terminal" ]]; then
    release_waiter_record "$slot_id" "$holder" "$disposition" false \
      "merge-slot request completed"
  fi
  printf 'SLOT_RELEASED holder=%s already_available=%s disposition=%s\n' \
    "$holder" "$already_available" "$disposition"
}

run_with_slot() {
  local holder="$1"
  local command_rc release_rc acquire_rc disposition
  shift
  if acquire_slot "$holder" "${SHEPHERD_SLOT_ATTEMPTS:-3}" \
    "${SHEPHERD_SLOT_INTERVAL:-1}" armed "${SHEPHERD_WAITER_MODE:-resume}"; then
    acquire_rc=0
  else
    acquire_rc=$?
  fi
  [[ $acquire_rc -eq 0 ]] || return "$acquire_rc"

  if "$@"; then
    command_rc=0
  else
    command_rc=$?
  fi

  if [[ $command_rc -eq $EXIT_WAITING ]]; then
    disposition=retryable
  else
    disposition=terminal
  fi
  if release_slot "$holder" "$disposition"; then
    release_rc=0
    disarm_slot_release
  else
    release_rc=$?
  fi
  if [[ $command_rc -ne 0 ]]; then
    return "$command_rc"
  fi
  return "$release_rc"
}

acquire_slot_cli() {
  local holder="$1"
  local attempts="${2:-3}"
  local interval="${3:-1}"
  local waiter_mode="${4:-resume}"

  acquire_slot "$holder" "$attempts" "$interval" handoff "$waiter_mode"
}

with_slot() {
  local holder="$1"
  shift
  [[ "${1:-}" == "--" ]] || fail "with-slot requires -- before the command"
  shift
  [[ $# -gt 0 ]] || fail "with-slot requires a command"
  run_with_slot "$holder" "$@"
}

check_run() {
  local repo="$1"
  local run_id="$2"
  local expected_head="$3"
  local data actual_head status conclusion url

  require_sha "$expected_head" "expected head"
  data="$(gh run view "$run_id" --repo "$repo" --json headSha,status,conclusion,url \
    --jq '[.headSha,.status,(.conclusion // "NONE"),(.url // "NONE")] | @tsv')" || fail "cannot read run $run_id"
  IFS=$'\t' read -r actual_head status conclusion url <<<"$data"
  require_sha "${actual_head:-}" "run head"

  if [[ "$actual_head" != "$expected_head" ]]; then
    printf 'RUN_STALE run=%s expected=%s actual=%s url=%s\n' \
      "$run_id" "$expected_head" "$actual_head" "${url:-unknown}"
    return "$EXIT_STALE"
  fi
  if [[ "$status" != "completed" ]]; then
    printf 'RUN_WAITING run=%s status=%s head=%s\n' "$run_id" "$status" "$actual_head"
    return "$EXIT_WAITING"
  fi
  if [[ "$conclusion" == "success" ]]; then
    printf 'RUN_READY run=%s head=%s\n' "$run_id" "$actual_head"
    return 0
  fi
  case "$conclusion" in
  failure | cancelled | timed_out | action_required | startup_failure)
    printf 'RUN_FAILED run=%s conclusion=%s head=%s\n' "$run_id" "$conclusion" "$actual_head"
    return "$EXIT_FAILED"
    ;;
  *)
    fail "run $run_id has unknown conclusion ${conclusion:-empty}"
    ;;
  esac
}

check_pr() {
  local repo="$1"
  local pr="$2"
  local expected_head="$3"
  local expected_base="$4"
  local approval_mode="${5:-github}"
  local data state draft mergeable review base head checks

  require_sha "$expected_head" "expected head"
  case "$approval_mode" in
  github | external) ;;
  *) fail "approval mode must be github or external" ;;
  esac
  data="$(gh pr view "$pr" --repo "$repo" \
    --json state,isDraft,mergeable,reviewDecision,baseRefName,headRefOid,statusCheckRollup \
    --jq '[.state,(.isDraft|tostring),(.mergeable // "UNKNOWN"),(if (.reviewDecision // "") == "" then "NONE" else .reviewDecision end),(.baseRefName // "NONE"),(.headRefOid // "NONE"),([.statusCheckRollup[]? | ((.conclusion // .state // .status // "") | ascii_upcase)] | if length == 0 then "NONE" elif all(. == "SUCCESS" or . == "NEUTRAL" or . == "SKIPPED") then "GREEN" elif any(. == "FAILURE" or . == "ERROR" or . == "CANCELLED" or . == "TIMED_OUT" or . == "ACTION_REQUIRED") then "RED" else "PENDING" end)] | @tsv')" ||
    fail "cannot read PR $pr"
  IFS=$'\t' read -r state draft mergeable review base head checks <<<"$data"

  if [[ "$head" != "$expected_head" || "$base" != "$expected_base" ]]; then
    printf 'PR_STALE pr=%s expected_head=%s actual_head=%s expected_base=%s actual_base=%s\n' \
      "$pr" "$expected_head" "${head:-unknown}" "$expected_base" "${base:-unknown}"
    return "$EXIT_STALE"
  fi
  if [[ "$state" != "OPEN" ]]; then
    printf 'PR_NOT_OPEN pr=%s state=%s\n' "$pr" "${state:-unknown}"
    return "$EXIT_FAILED"
  fi
  if [[ "$mergeable" == "CONFLICTING" || "$review" == "CHANGES_REQUESTED" || "$checks" == "RED" ]]; then
    printf 'PR_FAILED pr=%s mergeable=%s review=%s checks=%s\n' "$pr" "$mergeable" "$review" "$checks"
    return "$EXIT_FAILED"
  fi
  if [[ "$draft" == "true" || "$checks" == "PENDING" ||
    ("$approval_mode" == "github" && "$review" != "APPROVED") ]]; then
    printf 'PR_WAITING pr=%s draft=%s review=%s approval=%s checks=%s\n' \
      "$pr" "$draft" "${review:-empty}" "$approval_mode" "$checks"
    return "$EXIT_WAITING"
  fi
  if [[ "$mergeable" != "MERGEABLE" || ("$checks" != "GREEN" && "$checks" != "NONE") ]]; then
    fail "PR $pr readiness is unknown (mergeable=${mergeable:-empty}, checks=${checks:-empty})"
  fi
  printf 'PR_READY pr=%s head=%s base=%s approval=%s checks=%s\n' \
    "$pr" "$head" "$base" "$approval_mode" "$checks"
}

verify_landed() {
  local repo="$1"
  local pr="$2"
  local landing_base="$3"
  local recorded_base="$4"
  local expected_head="$5"
  local expected_merge="$6"
  local data state merged_at actual_merge pr_base actual_head url remote_base compare_status
  local fetched_base paths_file path expected_entry actual_entry changed

  require_sha "$recorded_base" "recorded base"
  require_sha "$expected_head" "expected head"
  require_sha "$expected_merge" "expected merge"
  data="$(gh pr view "$pr" --repo "$repo" \
    --json state,mergedAt,mergeCommit,baseRefName,headRefOid,url \
    --jq '[.state,(.mergedAt // "NONE"),(.mergeCommit.oid // "NONE"),(.baseRefName // "NONE"),(.headRefOid // "NONE"),(.url // "NONE")] | @tsv')" ||
    fail "cannot read merged PR $pr"
  IFS=$'\t' read -r state merged_at actual_merge pr_base actual_head url <<<"$data"

  if [[ "$state" != "MERGED" || "$merged_at" == "NONE" ]]; then
    printf 'NOT_LANDED pr=%s state=%s merged_at=%s\n' "$pr" "${state:-unknown}" "${merged_at:-empty}"
    return "$EXIT_WAITING"
  fi
  if [[ "$actual_head" != "$expected_head" || "$actual_merge" != "$expected_merge" ]]; then
    printf 'LANDING_STALE pr=%s expected_head=%s actual_head=%s expected_merge=%s actual_merge=%s\n' \
      "$pr" "$expected_head" "${actual_head:-unknown}" "$expected_merge" "${actual_merge:-unknown}"
    return "$EXIT_STALE"
  fi

  remote_base="$(gh api "repos/$repo/git/ref/heads/$landing_base" --jq '.object.sha')" ||
    fail "cannot read remote base $landing_base"
  require_sha "$remote_base" "remote base"
  compare_status="$(gh api "repos/$repo/compare/$expected_merge...$remote_base" --jq '.status')" ||
    fail "cannot compare merge commit with $landing_base"
  if [[ "$compare_status" == "ahead" || "$compare_status" == "identical" ]]; then
    printf 'LANDED_COMMIT pr=%s merge=%s base=%s base_sha=%s\n' \
      "$pr" "$expected_merge" "$landing_base" "$remote_base"
    return 0
  fi
  [[ "$compare_status" == "diverged" || "$compare_status" == "behind" ]] ||
    fail "unknown compare state $compare_status"

  git fetch --quiet --no-tags origin \
    "refs/heads/$landing_base:refs/remotes/origin/$landing_base" \
    "refs/pull/$pr/head" || fail "cannot fetch landing proof refs"
  fetched_base="$(git rev-parse --verify "refs/remotes/origin/$landing_base^{commit}")" ||
    fail "cannot resolve fetched base"
  [[ "$fetched_base" == "$remote_base" ]] || fail "fetched base does not match GitHub ref"
  git cat-file -e "$recorded_base^{commit}" 2>/dev/null || fail "recorded base object is unavailable"
  git cat-file -e "$expected_head^{commit}" 2>/dev/null || fail "expected head object is unavailable"

  paths_file="$(mktemp "${TMPDIR:-/tmp}/pr-shepherd-paths.XXXXXX")" ||
    fail "cannot create content-proof file"
  if ! git diff --name-only -z "$recorded_base" "$expected_head" >"$paths_file"; then
    rm -f -- "$paths_file"
    fail "cannot enumerate PR content"
  fi
  exec 3<"$paths_file" || fail "cannot open content-proof file"
  rm -f -- "$paths_file" || fail "cannot unlink content-proof file"
  changed=0
  while IFS= read -r -d '' path; do
    changed=$((changed + 1))
    expected_entry="$(git ls-tree "$expected_head" -- "$path")" ||
      fail "cannot inspect head path $path"
    actual_entry="$(git ls-tree "$remote_base" -- "$path")" ||
      fail "cannot inspect base path $path"
    if [[ "$expected_entry" != "$actual_entry" ]]; then
      printf 'NOT_LANDED_CONTENT pr=%s path=%q base=%s\n' "$pr" "$path" "$landing_base"
      return "$EXIT_WAITING"
    fi
  done <&3
  exec 3<&-
  [[ $changed -gt 0 ]] || fail "content proof has no changed paths"
  printf 'LANDED_CONTENT pr=%s merge=%s pr_base=%s landing_base=%s base_sha=%s paths=%s\n' \
    "$pr" "$expected_merge" "$pr_base" "$landing_base" "$remote_base" "$changed"
}

stamp_landing_proof() {
  local merge_bead="$1"
  local pr="$2"
  local head_sha="$3"
  local merge_sha="$4"

  bd update "$merge_bead" --set-metadata "head_sha=$head_sha" \
    --set-metadata "merge_sha=$merge_sha" --set-metadata "landing_state=proved" >/dev/null ||
    fail "cannot stamp landing metadata"
  bd comment "$merge_bead" "LANDED pr=$pr head_sha=$head_sha merge_sha=$merge_sha proof=base" >/dev/null ||
    fail "cannot record landing proof"
}

record_merge_receipt() {
  local merge_bead="$1"
  local pr="$2"
  local pr_base="$3"
  local landing_base="$4"
  local head_sha="$5"
  local merge_sha="$6"

  bd update "$merge_bead" --set-metadata "head_sha=$head_sha" \
    --set-metadata "merge_sha=$merge_sha" --set-metadata "pr_base=$pr_base" \
    --set-metadata "landing_base=$landing_base" --set-metadata "landing_state=merged" >/dev/null ||
    fail "cannot persist remote merge receipt"
  bd comment "$merge_bead" \
    "MERGED pr=$pr pr_base=$pr_base landing_base=$landing_base head_sha=$head_sha merge_sha=$merge_sha" \
    >/dev/null || fail "cannot record remote merge receipt"
}

hold_for_landing_base() {
  local merge_bead="$1"
  local pr="$2"
  local pr_base="$3"
  local landing_base="$4"
  local merge_sha="$5"

  bd update "$merge_bead" --set-metadata "landing_state=waiting_base" >/dev/null ||
    fail "cannot persist stacked landing hold"
  bd comment "$merge_bead" \
    "LANDING_HOLD pr=$pr pr_base=$pr_base landing_base=$landing_base merge_sha=$merge_sha" \
    >/dev/null || fail "cannot record stacked landing hold"
  printf 'LANDING_HOLD merge=%s pr=%s pr_base=%s landing_base=%s merge_sha=%s\n' \
    "$merge_bead" "$pr" "$pr_base" "$landing_base" "$merge_sha"
}

land_owned() {
  local merge_bead="$1"
  local repo="$2"
  local pr="$3"
  local pr_base="$4"
  local landing_base="$5"
  local recorded_base="$6"
  local expected_head="$7"
  local method="$8"
  local approval_mode="$9"
  local data state actual_head merge_sha probe_output probe_rc verify_rc

  require_sha "$recorded_base" "recorded base"
  require_sha "$expected_head" "expected head"
  case "$method" in
  merge | rebase | squash) ;;
  *) fail "merge method must be merge, rebase, or squash" ;;
  esac

  data="$(gh pr view "$pr" --repo "$repo" --json state,headRefOid,mergeCommit \
    --jq '[.state,(.headRefOid // "NONE"),(.mergeCommit.oid // "NONE")] | @tsv')" ||
    fail "cannot read PR $pr before landing"
  IFS=$'\t' read -r state actual_head merge_sha <<<"$data"
  if [[ "$actual_head" != "$expected_head" ]]; then
    printf 'PR_STALE pr=%s expected_head=%s actual_head=%s\n' \
      "$pr" "$expected_head" "${actual_head:-unknown}"
    return "$EXIT_STALE"
  fi

  if [[ "$state" == "MERGED" ]]; then
    require_sha "$merge_sha" "merge commit"
    record_merge_receipt "$merge_bead" "$pr" "$pr_base" "$landing_base" "$expected_head" "$merge_sha"
    set +e
    verify_landed "$repo" "$pr" "$landing_base" "$recorded_base" "$expected_head" "$merge_sha"
    verify_rc=$?
    set -e
    if [[ $verify_rc -eq "$EXIT_WAITING" && "$pr_base" != "$landing_base" ]]; then
      hold_for_landing_base "$merge_bead" "$pr" "$pr_base" "$landing_base" "$merge_sha"
      return "$EXIT_WAITING"
    fi
    [[ $verify_rc -eq 0 ]] || return "$verify_rc"
    stamp_landing_proof "$merge_bead" "$pr" "$expected_head" "$merge_sha"
    printf 'LANDING_RECOVERY_PROVED merge=%s pr=%s merge_sha=%s\n' "$merge_bead" "$pr" "$merge_sha"
    return 0
  fi

  check_pr "$repo" "$pr" "$expected_head" "$pr_base" "$approval_mode" || return $?
  git fetch --quiet --no-tags origin \
    "refs/heads/$pr_base:refs/remotes/origin/$pr_base" \
    "refs/pull/$pr/head" || fail "cannot fetch landing transaction refs"
  set +e
  probe_output="$("$SCRIPT_DIR/merge-probe.sh" conflicts \
    "refs/remotes/origin/$pr_base" "$expected_head" 2>&1)"
  probe_rc=$?
  set -e
  if [[ $probe_rc -eq 1 ]]; then
    printf 'LANDING_CONFLICT pr=%s paths=%s\n' "$pr" "$probe_output"
    return "$EXIT_FAILED"
  fi
  if [[ $probe_rc -ne 0 ]]; then
    printf 'LANDING_UNKNOWN pr=%s probe=%s\n' "$pr" "$probe_output" >&2
    return "$EXIT_UNKNOWN"
  fi

  gh pr merge "$pr" --repo "$repo" "--$method" --match-head-commit "$expected_head" ||
    {
      printf 'LANDING_MERGE_FAILED pr=%s\n' "$pr" >&2
      return "$EXIT_FAILED"
    }
  data="$(gh pr view "$pr" --repo "$repo" --json state,headRefOid,mergeCommit \
    --jq '[.state,(.headRefOid // "NONE"),(.mergeCommit.oid // "NONE")] | @tsv')" ||
    fail "cannot read PR $pr after merge"
  IFS=$'\t' read -r state actual_head merge_sha <<<"$data"
  [[ "$state" == "MERGED" && "$actual_head" == "$expected_head" ]] ||
    fail "PR identity changed after merge"
  require_sha "$merge_sha" "merge commit"
  record_merge_receipt "$merge_bead" "$pr" "$pr_base" "$landing_base" "$expected_head" "$merge_sha"
  set +e
  verify_landed "$repo" "$pr" "$landing_base" "$recorded_base" "$expected_head" "$merge_sha"
  verify_rc=$?
  set -e
  if [[ $verify_rc -eq "$EXIT_WAITING" && "$pr_base" != "$landing_base" ]]; then
    hold_for_landing_base "$merge_bead" "$pr" "$pr_base" "$landing_base" "$merge_sha"
    return "$EXIT_WAITING"
  fi
  [[ $verify_rc -eq 0 ]] || return "$verify_rc"
  stamp_landing_proof "$merge_bead" "$pr" "$expected_head" "$merge_sha"
  printf 'LANDING_PROVED merge=%s pr=%s merge_sha=%s\n' "$merge_bead" "$pr" "$merge_sha"
}

land_pr() {
  local merge_bead="$1"
  local repo="$2"
  local pr="$3"
  local pr_base="$4"
  local landing_base="$5"
  local recorded_base="$6"
  local expected_head="$7"
  local method="$8"
  local approval_mode="${9:-github}"
  local holder="pr-shepherd:$repo#$pr@$expected_head"
  local landing_rc

  if run_with_slot "$holder" land_owned "$merge_bead" "$repo" "$pr" \
    "$pr_base" "$landing_base" "$recorded_base" "$expected_head" "$method" "$approval_mode"; then
    landing_rc=0
  else
    landing_rc=$?
  fi
  [[ $landing_rc -eq 0 ]] || return "$landing_rc"
  bd close "$merge_bead" --reason "PR #$pr landed on $landing_base with exact proof" >/dev/null ||
    fail "cannot close landed merge bead"
  printf 'LANDING_COMPLETE merge=%s pr=%s base=%s\n' "$merge_bead" "$pr" "$landing_base"
}

failure_key() {
  local repo="$1"
  local kind="$2"
  shift 2
  [[ $# -gt 0 ]] || fail "failure-key requires failure details"
  case "$kind" in
  ci | conflict | review) ;;
  *) fail "failure kind must be ci, conflict, or review" ;;
  esac
  printf '%s\0' "$repo" "$kind" "$@" | git hash-object --stdin
}

find_fixes() {
  local key="$1"
  bd list --label-any agent:coder,agent:reviewer \
    --status open,in_progress,blocked,deferred --metadata-field "failure_key=$key" \
    --json | jq -r 'sort_by(.created_at, .id) | .[].id'
}

find_fix() {
  find_fixes "$1" | sed -n '1p'
}

reconcile_fix_duplicates() {
  local key="$1"
  local canonical="$2"
  local duplicate

  while IFS= read -r duplicate; do
    [[ -z "$duplicate" || "$duplicate" == "$canonical" ]] && continue
    bd close "$duplicate" --reason "Duplicate of $canonical for failure_key=$key" >/dev/null ||
      fail "cannot close duplicate fix bead $duplicate"
  done < <(find_fixes "$key")
}

comment_marker_state() {
  local issue="$1"
  local marker="$2"
  local comments rc

  if ! comments="$(bd comments "$issue" --json)"; then
    return "$QUERY_ERROR"
  fi
  set +e
  printf '%s' "$comments" | jq -e --arg marker "$marker" \
    'any(.[]?; (.text // "") | contains($marker))' >/dev/null
  rc=$?
  set -e
  case "$rc" in
  0) return "$QUERY_FOUND" ;;
  1) return "$QUERY_ABSENT" ;;
  *) return "$QUERY_ERROR" ;;
  esac
}

comment_once() {
  local issue="$1"
  local marker="$2"
  local message="$3"
  local query_rc

  if comment_marker_state "$issue" "$marker"; then
    return 0
  else
    query_rc=$?
  fi
  [[ $query_rc -eq $QUERY_ABSENT ]] || fail "cannot query comment receipt on $issue"
  bd comment "$issue" "$message" >/dev/null || fail "cannot write comment receipt on $issue"
}

dependency_state() {
  local merge_bead="$1"
  local fix_bead="$2"
  local issue rc

  if ! issue="$(bd show "$merge_bead" --json)"; then
    return "$QUERY_ERROR"
  fi
  set +e
  printf '%s' "$issue" | jq -e --arg fix "$fix_bead" \
    'any(.[0].dependencies[]?; (.id // .depends_on_id) == $fix)' >/dev/null
  rc=$?
  set -e
  case "$rc" in
  0) return "$QUERY_FOUND" ;;
  1) return "$QUERY_ABSENT" ;;
  *) return "$QUERY_ERROR" ;;
  esac
}

bounce_receipt() {
  local merge_bead="$1"
  local key="$2"

  bd show "$merge_bead" --json | jq -r --arg key "$key" \
    '.[0].metadata as $metadata |
     if ($metadata.bounce_key // "") == $key
     then [($metadata.bounce_fix // ""), ($metadata.bounce_phase // "")] | join("|")
     else "|"
     end'
}

bounce_phase_rank() {
  case "$1" in
  "") printf '0\n' ;;
  preparing) printf '1\n' ;;
  fix_ready) printf '2\n' ;;
  parked) printf '3\n' ;;
  commented) printf '4\n' ;;
  complete) printf '5\n' ;;
  *) fail "unknown bounce receipt phase $1" ;;
  esac
}

advance_bounce_receipt() {
  local merge_bead="$1"
  local key="$2"
  local fix_bead="$3"
  local phase="$4"

  bd update "$merge_bead" --set-metadata "bounce_key=$key" \
    --set-metadata "bounce_fix=$fix_bead" --set-metadata "bounce_phase=$phase" >/dev/null ||
    fail "cannot persist bounce receipt phase $phase"
}

ensure_bounce() {
  local merge_bead="$1"
  local key="$2"
  local route="$3"
  local title="$4"
  local metadata="$5"
  local description="$6"
  local fix_bead metadata_with_key canonical receipt phase receipt_fix phase_rank marker query_rc

  [[ "$route" == "agent:coder" || "$route" == "agent:reviewer" ]] ||
    fail "bounce route must be agent:coder or agent:reviewer"
  metadata_with_key="$(printf '%s' "$metadata" | jq -ce --arg key "$key" \
    'if type == "object" then . + {failure_key: $key} else error("metadata must be an object") end')" ||
    fail "invalid bounce metadata"
  receipt="$(bounce_receipt "$merge_bead" "$key")" || fail "cannot inspect bounce receipt"
  IFS='|' read -r receipt_fix phase <<<"$receipt"
  phase_rank="$(bounce_phase_rank "$phase")"
  fix_bead="$(find_fix "$key")" || fail "cannot query bounce duplicates"
  if [[ $phase_rank -eq 5 && -z "$fix_bead" ]]; then
    receipt_fix=""
    phase_rank=0
  fi
  if [[ $phase_rank -eq 0 ]]; then
    advance_bounce_receipt "$merge_bead" "$key" "" preparing
    phase_rank=1
  fi

  if [[ -z "$fix_bead" ]]; then
    bd create "$title" --deps "discovered-from:$merge_bead" \
      --labels "$route" --metadata "$metadata_with_key" --description "$description" --silent \
      >/dev/null ||
      fail "cannot create fix bead"
    canonical="$(find_fix "$key")" || fail "cannot reconcile bounce creation"
    [[ -n "$canonical" ]] || fail "created fix bead is not queryable"
    fix_bead="$canonical"
  fi

  if [[ -n "$receipt_fix" && "$receipt_fix" != "$fix_bead" ]]; then
    fail "bounce receipt fix changed (expected $receipt_fix, found $fix_bead)"
  fi
  if [[ $phase_rank -lt 2 ]]; then
    advance_bounce_receipt "$merge_bead" "$key" "$fix_bead" fix_ready
    phase_rank=2
  fi

  if dependency_state "$merge_bead" "$fix_bead"; then
    query_rc=$QUERY_FOUND
  else
    query_rc=$?
  fi
  if [[ $query_rc -eq $QUERY_ABSENT ]]; then
    bd dep add "$merge_bead" "$fix_bead" >/dev/null || fail "cannot park merge bead"
  elif [[ $query_rc -eq $QUERY_ERROR ]]; then
    fail "cannot query bounce dependency receipt"
  fi
  reconcile_fix_duplicates "$key" "$fix_bead"
  if [[ $phase_rank -lt 3 ]]; then
    advance_bounce_receipt "$merge_bead" "$key" "$fix_bead" parked
    phase_rank=3
  fi
  if [[ $phase_rank -lt 4 ]]; then
    marker="bounce_receipt=$key"
    comment_once "$merge_bead" "$marker" \
      "BOUNCED $marker failure_key=$key fix=$fix_bead route=$route"
    comment_once "$fix_bead" "$marker" \
      "CORRELATED $marker merge=$merge_bead failure_key=$key"
    advance_bounce_receipt "$merge_bead" "$key" "$fix_bead" commented
    phase_rank=4
  fi
  bd update "$merge_bead" --assignee "" --status open >/dev/null ||
    fail "cannot release merge bead claim"
  if [[ $phase_rank -lt 5 ]]; then
    advance_bounce_receipt "$merge_bead" "$key" "$fix_bead" complete
    printf 'BOUNCE_PARKED merge=%s fix=%s key=%s\n' "$merge_bead" "$fix_bead" "$key"
  else
    printf 'BOUNCE_REUSED merge=%s fix=%s key=%s\n' "$merge_bead" "$fix_bead" "$key"
  fi
}

recovery_key() {
  local kind="$1"
  local subject="$2"
  local evidence="$3"

  printf '%s\0%s\0%s\0' "$kind" "$subject" "$evidence" | git hash-object --stdin
}

recovery_phase_rank() {
  case "$1" in
  prepared) printf '1\n' ;;
  mutated) printf '2\n' ;;
  commented) printf '3\n' ;;
  audited) printf '4\n' ;;
  complete) printf '5\n' ;;
  *) fail "unknown recovery receipt phase ${1:-empty}" ;;
  esac
}

advance_recovery_receipt() {
  local merge_bead="$1"
  local key="$2"
  local kind="$3"
  local subject="$4"
  local evidence="$5"
  local phase="$6"

  bd update "$merge_bead" --set-metadata "recovery_key=$key" \
    --set-metadata "recovery_kind=$kind" --set-metadata "recovery_subject=$subject" \
    --set-metadata "recovery_evidence=$evidence" --set-metadata "recovery_phase=$phase" \
    >/dev/null || fail "cannot persist recovery receipt phase $phase"
}

prepare_recovery() {
  local merge_bead="$1"
  local key="$2"
  local kind="$3"
  local subject="$4"
  local evidence="$5"
  local receipt current_key phase

  receipt="$(bd show "$merge_bead" --json | jq -r \
    '.[0].metadata | [(.recovery_key // ""), (.recovery_phase // "")] | join("|")')" ||
    fail "cannot inspect recovery receipt"
  IFS='|' read -r current_key phase <<<"$receipt"
  if [[ "$current_key" == "$key" && -n "$phase" ]]; then
    recovery_phase_rank "$phase" >/dev/null
    printf '%s|false\n' "$phase"
    return 0
  fi
  if [[ -n "$current_key" && "$phase" != "complete" ]]; then
    fail "another recovery receipt is incomplete"
  fi
  advance_recovery_receipt "$merge_bead" "$key" "$kind" "$subject" "$evidence" prepared
  printf 'prepared|true\n'
}

recovery_audit_state() {
  local merge_bead="$1"
  local tool_name="$2"
  local beads_path audit_file rc

  beads_path="$(bd where --json | jq -er '.path | select(type == "string" and length > 0)')" ||
    return "$QUERY_ERROR"
  audit_file="$beads_path/interactions.jsonl"
  [[ -f "$audit_file" ]] || return "$QUERY_ABSENT"
  set +e
  jq -se --arg issue "$merge_bead" --arg tool "$tool_name" \
    'any(.[]; .kind == "tool_call" and .issue_id == $issue and .tool_name == $tool)' \
    "$audit_file" >/dev/null
  rc=$?
  set -e
  case "$rc" in
  0) return "$QUERY_FOUND" ;;
  1) return "$QUERY_ABSENT" ;;
  *) return "$QUERY_ERROR" ;;
  esac
}

finish_recovery() {
  local merge_bead="$1"
  local key="$2"
  local kind="$3"
  local subject="$4"
  local evidence="$5"
  local phase="$6"
  local phase_rank marker tool_name query_rc

  phase_rank="$(recovery_phase_rank "$phase")"
  if [[ $phase_rank -lt 2 ]]; then
    advance_recovery_receipt "$merge_bead" "$key" "$kind" "$subject" "$evidence" mutated
    phase_rank=2
  fi
  marker="recovery_receipt=$key"
  if [[ $phase_rank -lt 3 ]]; then
    comment_once "$merge_bead" "$marker" \
      "RECOVERED $marker kind=$kind subject=$subject evidence=$evidence"
    advance_recovery_receipt "$merge_bead" "$key" "$kind" "$subject" "$evidence" commented
    phase_rank=3
  fi
  tool_name="pr-shepherd.recover-$kind.$key"
  if [[ $phase_rank -lt 4 ]]; then
    if recovery_audit_state "$merge_bead" "$tool_name"; then
      query_rc=$QUERY_FOUND
    else
      query_rc=$?
    fi
    if [[ $query_rc -eq $QUERY_ABSENT ]]; then
      bd audit record --kind tool_call --tool-name "$tool_name" \
        --issue-id "$merge_bead" >/dev/null || fail "cannot audit recovery receipt"
    elif [[ $query_rc -eq $QUERY_ERROR ]]; then
      fail "cannot query recovery audit receipt"
    fi
    advance_recovery_receipt "$merge_bead" "$key" "$kind" "$subject" "$evidence" audited
    phase_rank=4
  fi
  if [[ $phase_rank -lt 5 ]]; then
    advance_recovery_receipt "$merge_bead" "$key" "$kind" "$subject" "$evidence" complete
  fi
}

recover_slot() {
  local merge_bead="$1"
  local dead_holder="$2"
  local evidence="$3"
  local key prepared phase is_new phase_rank state slot_id actual record native_holder query_rc lease

  [[ -n "$evidence" ]] || fail "dead-holder recovery requires an evidence reference"
  key="$(recovery_key slot "$dead_holder" "$evidence")" || fail "cannot derive recovery key"
  prepared="$(prepare_recovery "$merge_bead" "$key" slot "$dead_holder" "$evidence")"
  IFS='|' read -r phase is_new <<<"$prepared"
  phase_rank="$(recovery_phase_rank "$phase")"
  if [[ $phase_rank -lt 2 ]]; then
    state="$(slot_state)" || fail "cannot inspect merge slot"
    slot_id="$(printf '%s' "$state" | jq -r '.id // empty')" || fail "invalid merge-slot id"
    actual="$(printf '%s' "$state" | slot_holder)" || fail "invalid merge-slot holder"
    [[ -n "$slot_id" ]] || fail "merge-slot id is missing"
    if record="$(active_waiter_record "$slot_id" "$dead_holder")"; then
      query_rc=$QUERY_FOUND
    else
      query_rc=$?
    fi
    if [[ $query_rc -eq $QUERY_FOUND ]]; then
      lease="$(printf '%s' "$record" | jq -r '.metadata.lease_actor // ""')"
      [[ -n "$lease" ]] || fail "dead holder waiter lease is missing"
      native_holder="$(native_holder_token "$dead_holder" "$record")" ||
        fail "cannot derive dead native holder token"
      if [[ "$actual" == "$native_holder" ]]; then
        bd merge-slot release --holder "$native_holder" >/dev/null ||
          fail "cannot release dead holder"
      elif [[ "$is_new" == "true" ]]; then
        fail "slot holder changed (expected $native_holder, found ${actual:-none})"
      fi
      close_observed_waiter_generation "$slot_id" "$dead_holder" "$record" \
        "$lease" "recovered dead slot holder"
    elif [[ $query_rc -ne $QUERY_ABSENT || "$is_new" == "true" ]]; then
      fail "cannot find dead holder waiter generation"
    else
      force_close_waiter_record "$slot_id" "$dead_holder" false \
        "recovered dead slot holder"
    fi
  fi
  finish_recovery "$merge_bead" "$key" slot "$dead_holder" "$evidence" "$phase"
  printf 'SLOT_RECOVERED merge=%s holder=%s evidence=%s receipt=%s\n' \
    "$merge_bead" "$dead_holder" "$evidence" "$key"
}

recover_waiter() {
  local merge_bead="$1"
  local dead_waiter="$2"
  local evidence="$3"
  local key prepared phase phase_rank state slot_id actual record native_holder query_rc lease

  [[ -n "$evidence" ]] || fail "dead-waiter recovery requires an evidence reference"
  key="$(recovery_key waiter "$dead_waiter" "$evidence")" || fail "cannot derive recovery key"
  prepared="$(prepare_recovery "$merge_bead" "$key" waiter "$dead_waiter" "$evidence")"
  IFS='|' read -r phase _ <<<"$prepared"
  phase_rank="$(recovery_phase_rank "$phase")"
  if [[ $phase_rank -lt 2 ]]; then
    state="$(slot_state)" || fail "cannot inspect merge slot"
    slot_id="$(printf '%s' "$state" | jq -r '.id // empty')" || fail "invalid merge-slot id"
    actual="$(printf '%s' "$state" | slot_holder)" || fail "invalid merge-slot holder"
    [[ -n "$slot_id" ]] || fail "merge-slot id is missing"
    if record="$(active_waiter_record "$slot_id" "$dead_waiter")"; then
      query_rc=$QUERY_FOUND
    else
      query_rc=$?
    fi
    if [[ $query_rc -eq $QUERY_FOUND ]]; then
      lease="$(printf '%s' "$record" | jq -r '.metadata.lease_actor // ""')"
      [[ -n "$lease" ]] || fail "dead waiter lease is missing"
      native_holder="$(native_holder_token "$dead_waiter" "$record")" ||
        fail "cannot derive dead waiter native holder token"
      [[ "$actual" != "$native_holder" ]] || fail "dead waiter currently holds the slot"
      close_observed_waiter_generation "$slot_id" "$dead_waiter" "$record" \
        "$lease" "recovered dead queued waiter"
    elif [[ $query_rc -ne $QUERY_ABSENT ]]; then
      fail "cannot find dead waiter generation"
    else
      force_close_waiter_record "$slot_id" "$dead_waiter" true \
        "recovered dead queued waiter"
    fi
  fi
  finish_recovery "$merge_bead" "$key" waiter "$dead_waiter" "$evidence" "$phase"
  printf 'WAITER_RECOVERED merge=%s waiter=%s evidence=%s receipt=%s\n' \
    "$merge_bead" "$dead_waiter" "$evidence" "$key"
}

recover_claim() {
  local merge_bead="$1"
  local dead_actor="$2"
  local evidence="$3"
  local waiter_holder="${4:-}"
  local subject key prepared phase claim actual status successor_state receipt
  local successor state slot_id record lease native_holder recovery_holder waiter_mode

  [[ -n "$evidence" ]] || fail "dead-claim recovery requires an evidence reference"
  successor="$(current_actor)"
  [[ "$successor" != "$dead_actor" ]] || fail "successor must differ from dead actor"
  subject="$dead_actor"
  [[ -z "$waiter_holder" ]] || subject="$dead_actor|$waiter_holder|$successor"
  key="$(recovery_key claim "$subject" "$evidence")" || fail "cannot derive recovery key"
  receipt="$(bd show "$merge_bead" --json | jq -r \
    '.[0].metadata | [(.recovery_key // ""), (.recovery_phase // "")] | join("|")')" ||
    fail "cannot inspect recovery receipt"
  if [[ "$receipt" == "$key|complete" ]]; then
    printf 'CLAIM_RECOVERED merge=%s holder=%s waiter=%s evidence=%s receipt=%s\n' \
      "$merge_bead" "$dead_actor" "${waiter_holder:-none}" "$evidence" "$key"
    return 0
  fi

  if [[ -n "$waiter_holder" ]]; then
    state="$(slot_state)" || fail "cannot inspect merge slot for waiter recovery"
    slot_id="$(printf '%s' "$state" | jq -er '.id // empty')" ||
      fail "merge-slot id is missing"
    record="$(active_waiter_record "$slot_id" "$waiter_holder")" ||
      fail "cannot find current open waiter attempt for takeover"
    waiter_link_state "$record" "$slot_id" ||
      fail "waiter has invalid parent linkage"
    lease="$(printf '%s' "$record" | jq -r '.metadata.lease_actor // ""')"
    native_holder="$(native_holder_token "$waiter_holder" "$record")" ||
      fail "cannot derive native holder token"
    actual="$(printf '%s' "$state" | slot_holder)" || fail "invalid merge-slot holder"
    if [[ "$lease" == "$dead_actor" ]]; then
      if [[ "$actual" == "$native_holder" ]]; then
        bd merge-slot release --holder "$native_holder" >/dev/null ||
          fail "cannot release dead native holder"
      elif [[ -n "$actual" ]]; then
        fail "slot holder changed before dead-owner recovery"
      fi
      close_observed_waiter_generation "$slot_id" "$waiter_holder" "$record" \
        "$dead_actor" "recovered dead waiter generation"
      waiter_mode=requeue
      acquire_slot "$waiter_holder" 1 0 handoff "$waiter_mode" ||
        fail "cannot acquire fresh successor waiter generation"
    elif [[ "$lease" == "$successor" ]]; then
      [[ "$actual" == "$native_holder" ]] ||
        fail "successor waiter does not own its native slot token"
    else
      fail "waiter recovery is leased to another successor"
    fi
  else
    recovery_holder="pr-shepherd:claim-recovery:$merge_bead:$dead_actor"
    acquire_slot "$recovery_holder" 1 0 handoff resume ||
      fail "cannot acquire dead-claim recovery slot"
  fi

  prepared="$(prepare_recovery "$merge_bead" "$key" claim "$subject" "$evidence")"
  IFS='|' read -r phase _ <<<"$prepared"
  if [[ "$(recovery_phase_rank "$phase")" -lt 2 ]]; then
    claim="$(bd show "$merge_bead" --json | jq -ce \
      '.[0] | {assignee: (.assignee // ""), status: (.status // ""), labels: (.labels // [])}')" ||
      fail "cannot inspect merge claim"
    actual="$(printf '%s' "$claim" | jq -r '.assignee')"
    status="$(printf '%s' "$claim" | jq -r '.status')"
    if [[ "$actual" == "$dead_actor" ]]; then
      bd update "$merge_bead" --assignee "" --status open >/dev/null ||
        fail "cannot release dead claim"
      BEADS_ACTOR="$successor" bd update "$merge_bead" --claim >/dev/null ||
        fail "cannot atomically reclaim merge bead for successor"
    elif [[ -n "$actual" ]]; then
      successor_state="$(printf '%s' "$claim" | jq -r \
        'if .status == "in_progress" and any(.labels[]?; . == "state:working")
         then "working" else "unsafe" end')"
      [[ "$actual" == "$successor" && "$successor_state" == "working" ]] ||
        fail "claim changed to unsafe successor state (holder=${actual:-none}, status=${status:-none})"
    elif [[ "$status" != "open" ]]; then
      fail "unowned claim has unsafe resumed status ${status:-none}"
    else
      BEADS_ACTOR="$successor" bd update "$merge_bead" --claim >/dev/null ||
        fail "cannot atomically resume merge-bead reclaim"
    fi
    claim="$(bd show "$merge_bead" --json | jq -ce \
      '.[0] | {assignee: (.assignee // ""), status: (.status // "")}')" ||
      fail "cannot verify merge-bead reclaim"
    [[ "$(printf '%s' "$claim" | jq -r '.status + "|" + .assignee')" == "in_progress|$successor" ]] ||
      fail "merge-bead reclaim did not persist"
  fi
  finish_recovery "$merge_bead" "$key" claim "$subject" "$evidence" "$phase"
  if [[ -z "$waiter_holder" ]]; then
    release_slot "$recovery_holder" terminal >/dev/null ||
      fail "cannot release dead-claim recovery slot"
  fi
  printf 'CLAIM_RECOVERED merge=%s holder=%s waiter=%s evidence=%s receipt=%s\n' \
    "$merge_bead" "$dead_actor" "${waiter_holder:-none}" "$evidence" "$key"
}

ready_ids() {
  bd ready --label agent:integrator --unassigned --json | jq -r '.[].id'
}

usage() {
  printf '%s\n' \
    'usage: landing-contract.sh check-run <repo> <run-id> <head-sha>' \
    '       landing-contract.sh check-pr <repo> <pr> <head-sha> <pr-base> [github|external]' \
    '       landing-contract.sh verify-landed <repo> <pr> <base> <recorded-base-sha> <head-sha> <merge-sha>' \
    '       landing-contract.sh land <merge-bead> <repo> <pr> <pr-base> <landing-base> <recorded-base-sha> <head-sha> <merge|rebase|squash> [github|external]' \
    '       landing-contract.sh acquire-slot <stable-holder> [attempts] [poll-seconds] [resume|requeue]' \
    '       landing-contract.sh release-slot <stable-holder> [terminal|retryable]' \
    '       landing-contract.sh with-slot <stable-holder> -- <command> [args...]' \
    '       landing-contract.sh failure-key <repo> <ci|conflict|review> <detail>...' \
    '       landing-contract.sh ensure-bounce <merge-bead> <key> <route> <title> <metadata-json> <description>' \
    '       landing-contract.sh recover-slot <merge-bead> <dead-holder> <evidence-ref>' \
    '       landing-contract.sh recover-waiter <merge-bead> <dead-waiter> <evidence-ref>' \
    '       landing-contract.sh recover-claim <merge-bead> <dead-actor> <evidence-ref> [waiter-holder]' \
    '       landing-contract.sh ready-ids'
}

require_command git
require_command gh
require_command bd
require_command jq

command_name="${1:-}"
shift || true
case "$command_name" in
check-run)
  [[ $# -eq 3 ]] || fail "check-run expects 3 arguments"
  check_run "$@"
  ;;
check-pr)
  [[ $# -ge 4 && $# -le 5 ]] || fail "check-pr expects 4-5 arguments"
  check_pr "$@"
  ;;
verify-landed)
  [[ $# -eq 6 ]] || fail "verify-landed expects 6 arguments"
  verify_landed "$@"
  ;;
land)
  [[ $# -ge 8 && $# -le 9 ]] || fail "land expects 8-9 arguments"
  land_pr "$@"
  ;;
acquire-slot)
  [[ $# -ge 1 && $# -le 4 ]] || fail "acquire-slot expects 1-4 arguments"
  acquire_slot_cli "$@"
  ;;
release-slot)
  [[ $# -ge 1 && $# -le 2 ]] || fail "release-slot expects 1-2 arguments"
  release_slot "$@"
  ;;
with-slot)
  [[ $# -ge 3 ]] || fail "with-slot expects a holder and command"
  with_slot "$@"
  ;;
failure-key)
  [[ $# -ge 3 ]] || fail "failure-key expects at least 3 arguments"
  failure_key "$@"
  ;;
ensure-bounce)
  [[ $# -eq 6 ]] || fail "ensure-bounce expects 6 arguments"
  ensure_bounce "$@"
  ;;
recover-slot)
  [[ $# -eq 3 ]] || fail "recover-slot expects 3 arguments"
  recover_slot "$@"
  ;;
recover-waiter)
  [[ $# -eq 3 ]] || fail "recover-waiter expects 3 arguments"
  recover_waiter "$@"
  ;;
recover-claim)
  [[ $# -ge 3 && $# -le 4 ]] || fail "recover-claim expects 3-4 arguments"
  recover_claim "$@"
  ;;
ready-ids)
  [[ $# -eq 0 ]] || fail "ready-ids expects no arguments"
  ready_ids
  ;;
-h | --help | help) usage ;;
*)
  usage >&2
  exit "$EXIT_UNKNOWN"
  ;;
esac
