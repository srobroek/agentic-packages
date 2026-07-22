#!/usr/bin/env bash
set -Eeuo pipefail

readonly EXIT_UNKNOWN=2
readonly EXIT_WAITING=10
readonly EXIT_STALE=11
readonly EXIT_FAILED=12
readonly EXIT_SLOT_QUEUED=75
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

slot_first_waiter() {
  jq -r '.waiters[0] // empty'
}

slot_has_waiter() {
  local holder="$1"

  jq -e --arg holder "$holder" 'any(.waiters[]?; . == $holder)' >/dev/null
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

remove_slot_waiter() {
  local holder="$1"
  local required_holder="${2:-}"
  local state slot_id actual metadata

  state="$(slot_state)" || fail "cannot inspect merge slot for waiter cleanup"
  slot_id="$(printf '%s' "$state" | jq -r '.id // empty')" || fail "invalid merge-slot id"
  actual="$(printf '%s' "$state" | slot_holder)" || fail "invalid merge-slot holder"
  [[ -n "$slot_id" ]] || fail "merge-slot id is missing"
  if [[ -n "$required_holder" && "$actual" != "$required_holder" ]]; then
    fail "slot holder changed during waiter cleanup"
  fi
  if ! printf '%s' "$state" | slot_has_waiter "$holder"; then
    return 0
  fi

  metadata="$(bd show "$slot_id" --json | jq -ce --arg holder "$holder" \
    --arg required "$required_holder" \
    '.[0].metadata |
     if ($required != "" and (.holder // "") != $required)
     then error("slot holder changed")
     else .waiters = ((.waiters // []) | map(select(. != $holder)))
     end')" \
    || fail "cannot prepare merge-slot waiter cleanup"
  bd update "$slot_id" --metadata "$metadata" >/dev/null || fail "cannot remove merge-slot waiter"
  state="$(slot_state)" || fail "cannot verify merge-slot waiter cleanup"
  if printf '%s' "$state" | slot_has_waiter "$holder"; then
    fail "merge-slot waiter cleanup did not persist"
  fi
}

acquire_slot() {
  local holder="$1"
  local attempts="${2:-3}"
  local interval="${3:-1}"
  local protection="${4:-handoff}"
  local state actual first_waiter rc attempt queued

  [[ -n "$holder" ]] || fail "slot holder is required"
  [[ "$attempts" =~ ^[1-9][0-9]*$ ]] || fail "attempts must be a positive integer"
  [[ "$interval" =~ ^[0-9]+$ ]] || fail "poll interval must be a non-negative integer"
  [[ "$protection" == "handoff" || "$protection" == "armed" ]] \
    || fail "slot protection must be handoff or armed"

  bd merge-slot create >/dev/null
  queued=false
  attempt=1
  while [[ $attempt -le $attempts ]]; do
    if [[ $attempt -gt 1 && "$interval" -gt 0 ]]; then
      sleep "$interval"
    fi
    state="$(slot_state)" || fail "cannot inspect merge slot"
    actual="$(printf '%s' "$state" | slot_holder)" || fail "invalid merge-slot state"
    first_waiter="$(printf '%s' "$state" | slot_first_waiter)" || fail "invalid merge-slot waiters"
    if [[ "$actual" == "$holder" ]]; then
      arm_slot_release "$holder"
      remove_slot_waiter "$holder" "$holder"
      [[ "$protection" == "armed" ]] || disarm_slot_release
      printf 'SLOT_OWNED holder=%s resumed=true\n' "$holder"
      return 0
    fi
    if printf '%s' "$state" | slot_available; then
      if [[ -z "$first_waiter" || "$first_waiter" == "$holder" ]]; then
        set +e
        bd merge-slot acquire --holder "$holder" >/dev/null
        rc=$?
        set -e
        if [[ $rc -eq 0 ]]; then
          arm_slot_release "$holder"
          remove_slot_waiter "$holder" "$holder"
          [[ "$protection" == "armed" ]] || disarm_slot_release
          printf 'SLOT_OWNED holder=%s resumed=false\n' "$holder"
          return 0
        fi
        [[ $rc -eq 1 ]] || fail "merge-slot acquire failed with exit $rc"
      fi
    elif ! printf '%s' "$state" | slot_has_waiter "$holder"; then
      set +e
      bd merge-slot acquire --holder "$holder" --wait >/dev/null
      rc=$?
      set -e
      [[ $rc -eq 1 ]] || fail "merge-slot enqueue failed with exit $rc"
      queued=true
    else
      queued=true
    fi
    attempt=$((attempt + 1))
  done

  printf 'SLOT_QUEUED holder=%s attempts=%s persisted=%s\n' "$holder" "$attempts" "$queued"
  return "$EXIT_SLOT_QUEUED"
}

release_slot() {
  local holder="$1"
  local state actual

  state="$(slot_state)" || {
    printf 'SLOT_RELEASE_UNKNOWN holder=%s\n' "$holder" >&2
    return "$EXIT_UNKNOWN"
  }
  actual="$(printf '%s' "$state" | slot_holder)" || {
    printf 'SLOT_RELEASE_INVALID holder=%s\n' "$holder" >&2
    return "$EXIT_UNKNOWN"
  }
  if printf '%s' "$state" | slot_available; then
    printf 'SLOT_RELEASED holder=%s already_available=true\n' "$holder"
    return 0
  fi
  if [[ "$actual" != "$holder" ]]; then
    printf 'SLOT_FOREIGN expected=%s actual=%s\n' "$holder" "${actual:-unknown}" >&2
    return "$EXIT_FAILED"
  fi
  bd merge-slot release --holder "$holder" >/dev/null || {
    printf 'SLOT_RELEASE_FAILED holder=%s\n' "$holder" >&2
    return "$EXIT_UNKNOWN"
  }
  printf 'SLOT_RELEASED holder=%s already_available=false\n' "$holder"
}

run_with_slot() {
  local holder="$1"
  local command_rc release_rc acquire_rc
  shift
  if acquire_slot "$holder" "${SHEPHERD_SLOT_ATTEMPTS:-3}" \
    "${SHEPHERD_SLOT_INTERVAL:-1}" armed; then
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

  if release_slot "$holder"; then
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
    --jq '[.state,(.isDraft|tostring),(.mergeable // "UNKNOWN"),(.reviewDecision // "NONE"),(.baseRefName // "NONE"),(.headRefOid // "NONE"),([.statusCheckRollup[]? | ((.conclusion // .state // .status // "") | ascii_upcase)] | if length == 0 then "NONE" elif all(. == "SUCCESS" or . == "NEUTRAL" or . == "SKIPPED") then "GREEN" elif any(. == "FAILURE" or . == "ERROR" or . == "CANCELLED" or . == "TIMED_OUT" or . == "ACTION_REQUIRED") then "RED" else "PENDING" end)] | @tsv')" \
    || fail "cannot read PR $pr"
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
    --jq '[.state,(.mergedAt // "NONE"),(.mergeCommit.oid // "NONE"),(.baseRefName // "NONE"),(.headRefOid // "NONE"),(.url // "NONE")] | @tsv')" \
    || fail "cannot read merged PR $pr"
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

  remote_base="$(gh api "repos/$repo/git/ref/heads/$landing_base" --jq '.object.sha')" \
    || fail "cannot read remote base $landing_base"
  require_sha "$remote_base" "remote base"
  compare_status="$(gh api "repos/$repo/compare/$expected_merge...$remote_base" --jq '.status')" \
    || fail "cannot compare merge commit with $landing_base"
  if [[ "$compare_status" == "ahead" || "$compare_status" == "identical" ]]; then
    printf 'LANDED_COMMIT pr=%s merge=%s base=%s base_sha=%s\n' \
      "$pr" "$expected_merge" "$landing_base" "$remote_base"
    return 0
  fi
  [[ "$compare_status" == "diverged" || "$compare_status" == "behind" ]] \
    || fail "unknown compare state $compare_status"

  git fetch --quiet --no-tags origin \
    "refs/heads/$landing_base:refs/remotes/origin/$landing_base" \
    "refs/pull/$pr/head" || fail "cannot fetch landing proof refs"
  fetched_base="$(git rev-parse --verify "refs/remotes/origin/$landing_base^{commit}")" \
    || fail "cannot resolve fetched base"
  [[ "$fetched_base" == "$remote_base" ]] || fail "fetched base does not match GitHub ref"
  git cat-file -e "$recorded_base^{commit}" 2>/dev/null || fail "recorded base object is unavailable"
  git cat-file -e "$expected_head^{commit}" 2>/dev/null || fail "expected head object is unavailable"

  paths_file="$(mktemp "${TMPDIR:-/tmp}/pr-shepherd-paths.XXXXXX")" \
    || fail "cannot create content-proof file"
  if ! git diff --name-only -z "$recorded_base" "$expected_head" >"$paths_file"; then
    rm -f -- "$paths_file"
    fail "cannot enumerate PR content"
  fi
  exec 3<"$paths_file" || fail "cannot open content-proof file"
  rm -f -- "$paths_file" || fail "cannot unlink content-proof file"
  changed=0
  while IFS= read -r -d '' path; do
    changed=$((changed + 1))
    expected_entry="$(git ls-tree "$expected_head" -- "$path")" \
      || fail "cannot inspect head path $path"
    actual_entry="$(git ls-tree "$remote_base" -- "$path")" \
      || fail "cannot inspect base path $path"
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
    --set-metadata "merge_sha=$merge_sha" --set-metadata "landing_state=proved" >/dev/null \
    || fail "cannot stamp landing metadata"
  bd comment "$merge_bead" "LANDED pr=$pr head_sha=$head_sha merge_sha=$merge_sha proof=base" >/dev/null \
    || fail "cannot record landing proof"
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
    --set-metadata "landing_base=$landing_base" --set-metadata "landing_state=merged" >/dev/null \
    || fail "cannot persist remote merge receipt"
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

  bd update "$merge_bead" --set-metadata "landing_state=waiting_base" >/dev/null \
    || fail "cannot persist stacked landing hold"
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
    --jq '[.state,(.headRefOid // "NONE"),(.mergeCommit.oid // "NONE")] | @tsv')" \
    || fail "cannot read PR $pr before landing"
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

  gh pr merge "$pr" --repo "$repo" "--$method" --match-head-commit "$expected_head" \
    || {
      printf 'LANDING_MERGE_FAILED pr=%s\n' "$pr" >&2
      return "$EXIT_FAILED"
    }
  data="$(gh pr view "$pr" --repo "$repo" --json state,headRefOid,mergeCommit \
    --jq '[.state,(.headRefOid // "NONE"),(.mergeCommit.oid // "NONE")] | @tsv')" \
    || fail "cannot read PR $pr after merge"
  IFS=$'\t' read -r state actual_head merge_sha <<<"$data"
  [[ "$state" == "MERGED" && "$actual_head" == "$expected_head" ]] \
    || fail "PR identity changed after merge"
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
  bd close "$merge_bead" --reason "PR #$pr landed on $landing_base with exact proof" >/dev/null \
    || fail "cannot close landed merge bead"
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
    bd close "$duplicate" --reason "Duplicate of $canonical for failure_key=$key" >/dev/null \
      || fail "cannot close duplicate fix bead $duplicate"
  done < <(find_fixes "$key")
}

comment_exists() {
  local issue="$1"
  local marker="$2"

  bd comments "$issue" --json | jq -e --arg marker "$marker" \
    'any(.[]?; (.text // "") | contains($marker))' >/dev/null
}

dependency_exists() {
  local merge_bead="$1"
  local fix_bead="$2"
  bd show "$merge_bead" --json | jq -e --arg fix "$fix_bead" \
    '.[0].dependencies[]? | select((.id // .depends_on_id) == $fix)' >/dev/null
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
    --set-metadata "bounce_fix=$fix_bead" --set-metadata "bounce_phase=$phase" >/dev/null \
    || fail "cannot persist bounce receipt phase $phase"
}

ensure_bounce() {
  local merge_bead="$1"
  local key="$2"
  local route="$3"
  local title="$4"
  local metadata="$5"
  local description="$6"
  local fix_bead metadata_with_key canonical receipt phase receipt_fix phase_rank marker

  [[ "$route" == "agent:coder" || "$route" == "agent:reviewer" ]] \
    || fail "bounce route must be agent:coder or agent:reviewer"
  metadata_with_key="$(printf '%s' "$metadata" | jq -ce --arg key "$key" \
    'if type == "object" then . + {failure_key: $key} else error("metadata must be an object") end')" \
    || fail "invalid bounce metadata"
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
      >/dev/null \
      || fail "cannot create fix bead"
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

  if ! dependency_exists "$merge_bead" "$fix_bead"; then
    bd dep add "$merge_bead" "$fix_bead" >/dev/null || fail "cannot park merge bead"
  fi
  reconcile_fix_duplicates "$key" "$fix_bead"
  if [[ $phase_rank -lt 3 ]]; then
    advance_bounce_receipt "$merge_bead" "$key" "$fix_bead" parked
    phase_rank=3
  fi
  if [[ $phase_rank -lt 4 ]]; then
    marker="bounce_receipt=$key"
    if ! comment_exists "$merge_bead" "$marker"; then
      bd comment "$merge_bead" \
        "BOUNCED $marker failure_key=$key fix=$fix_bead route=$route" >/dev/null \
        || fail "cannot comment merge bead"
    fi
    if ! comment_exists "$fix_bead" "$marker"; then
      bd comment "$fix_bead" \
        "CORRELATED $marker merge=$merge_bead failure_key=$key" >/dev/null \
        || fail "cannot comment fix bead"
    fi
    advance_bounce_receipt "$merge_bead" "$key" "$fix_bead" commented
    phase_rank=4
  fi
  bd update "$merge_bead" --assignee "" --status open >/dev/null \
    || fail "cannot release merge bead claim"
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
    '.[0].metadata | [(.recovery_key // ""), (.recovery_phase // "")] | join("|")')" \
    || fail "cannot inspect recovery receipt"
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

recovery_audit_exists() {
  local merge_bead="$1"
  local tool_name="$2"
  local beads_path audit_file

  beads_path="$(bd where --json | jq -r '.path // empty')" || return 1
  [[ -n "$beads_path" ]] || return 1
  audit_file="$beads_path/interactions.jsonl"
  [[ -f "$audit_file" ]] || return 1
  jq -e --arg issue "$merge_bead" --arg tool "$tool_name" \
    'select(.kind == "tool_call" and .issue_id == $issue and .tool_name == $tool)' \
    "$audit_file" >/dev/null
}

finish_recovery() {
  local merge_bead="$1"
  local key="$2"
  local kind="$3"
  local subject="$4"
  local evidence="$5"
  local phase="$6"
  local phase_rank marker tool_name

  phase_rank="$(recovery_phase_rank "$phase")"
  if [[ $phase_rank -lt 2 ]]; then
    advance_recovery_receipt "$merge_bead" "$key" "$kind" "$subject" "$evidence" mutated
    phase_rank=2
  fi
  marker="recovery_receipt=$key"
  if [[ $phase_rank -lt 3 ]]; then
    if ! comment_exists "$merge_bead" "$marker"; then
      bd comment "$merge_bead" \
        "RECOVERED $marker kind=$kind subject=$subject evidence=$evidence" >/dev/null \
        || fail "cannot comment recovery receipt"
    fi
    advance_recovery_receipt "$merge_bead" "$key" "$kind" "$subject" "$evidence" commented
    phase_rank=3
  fi
  tool_name="pr-shepherd.recover-$kind.$key"
  if [[ $phase_rank -lt 4 ]]; then
    if ! recovery_audit_exists "$merge_bead" "$tool_name"; then
      bd audit record --kind tool_call --tool-name "$tool_name" \
        --issue-id "$merge_bead" >/dev/null || fail "cannot audit recovery receipt"
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
  local key prepared phase is_new phase_rank state actual

  [[ -n "$evidence" ]] || fail "dead-holder recovery requires an evidence reference"
  key="$(recovery_key slot "$dead_holder" "$evidence")" || fail "cannot derive recovery key"
  prepared="$(prepare_recovery "$merge_bead" "$key" slot "$dead_holder" "$evidence")"
  IFS='|' read -r phase is_new <<<"$prepared"
  phase_rank="$(recovery_phase_rank "$phase")"
  if [[ $phase_rank -lt 2 ]]; then
    state="$(slot_state)" || fail "cannot inspect merge slot"
    actual="$(printf '%s' "$state" | slot_holder)" || fail "invalid merge-slot holder"
    if [[ "$actual" == "$dead_holder" ]]; then
      bd merge-slot release --holder "$dead_holder" >/dev/null || fail "cannot release dead holder"
    elif [[ "$is_new" == "true" || -n "$actual" ]]; then
      fail "slot holder changed (expected $dead_holder, found ${actual:-none})"
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
  local key prepared phase is_new phase_rank state actual

  [[ -n "$evidence" ]] || fail "dead-waiter recovery requires an evidence reference"
  key="$(recovery_key waiter "$dead_waiter" "$evidence")" || fail "cannot derive recovery key"
  prepared="$(prepare_recovery "$merge_bead" "$key" waiter "$dead_waiter" "$evidence")"
  IFS='|' read -r phase is_new <<<"$prepared"
  phase_rank="$(recovery_phase_rank "$phase")"
  if [[ $phase_rank -lt 2 ]]; then
    state="$(slot_state)" || fail "cannot inspect merge slot"
    actual="$(printf '%s' "$state" | slot_holder)" || fail "invalid merge-slot holder"
    [[ "$actual" != "$dead_waiter" ]] || fail "dead waiter currently holds the slot"
    if printf '%s' "$state" | slot_has_waiter "$dead_waiter"; then
      remove_slot_waiter "$dead_waiter"
    elif [[ "$is_new" == "true" ]]; then
      fail "waiter changed or is no longer queued"
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
  local key prepared phase is_new phase_rank actual

  [[ -n "$evidence" ]] || fail "dead-claim recovery requires an evidence reference"
  key="$(recovery_key claim "$dead_actor" "$evidence")" || fail "cannot derive recovery key"
  prepared="$(prepare_recovery "$merge_bead" "$key" claim "$dead_actor" "$evidence")"
  IFS='|' read -r phase is_new <<<"$prepared"
  phase_rank="$(recovery_phase_rank "$phase")"
  if [[ $phase_rank -lt 2 ]]; then
    actual="$(bd show "$merge_bead" --json | jq -r '.[0].assignee // empty')" \
      || fail "cannot inspect merge claim"
    if [[ "$actual" == "$dead_actor" ]]; then
      bd update "$merge_bead" --assignee "" --status open >/dev/null \
        || fail "cannot release dead claim"
    elif [[ "$is_new" == "true" || -n "$actual" ]]; then
      fail "claim holder changed (expected $dead_actor, found ${actual:-none})"
    fi
  fi
  finish_recovery "$merge_bead" "$key" claim "$dead_actor" "$evidence" "$phase"
  printf 'CLAIM_RECOVERED merge=%s holder=%s evidence=%s receipt=%s\n' \
    "$merge_bead" "$dead_actor" "$evidence" "$key"
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
    '       landing-contract.sh acquire-slot <stable-holder> [attempts] [poll-seconds]' \
    '       landing-contract.sh release-slot <stable-holder>' \
    '       landing-contract.sh with-slot <stable-holder> -- <command> [args...]' \
    '       landing-contract.sh failure-key <repo> <ci|conflict|review> <detail>...' \
    '       landing-contract.sh ensure-bounce <merge-bead> <key> <route> <title> <metadata-json> <description>' \
    '       landing-contract.sh recover-slot <merge-bead> <dead-holder> <evidence-ref>' \
    '       landing-contract.sh recover-waiter <merge-bead> <dead-waiter> <evidence-ref>' \
    '       landing-contract.sh recover-claim <merge-bead> <dead-actor> <evidence-ref>' \
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
    [[ $# -ge 1 && $# -le 3 ]] || fail "acquire-slot expects 1-3 arguments"
    acquire_slot "$@"
    ;;
  release-slot)
    [[ $# -eq 1 ]] || fail "release-slot expects 1 argument"
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
    [[ $# -eq 3 ]] || fail "recover-claim expects 3 arguments"
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
