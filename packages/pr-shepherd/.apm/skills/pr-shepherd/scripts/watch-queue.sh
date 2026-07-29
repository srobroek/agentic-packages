#!/usr/bin/env bash
# pr-shepherd: read-only merge-queue dashboard.
#
# Discovers required CI contexts from branch protection, classifies open PRs,
# ranks by beads merge queue (bd ready --label pr:merge), and recommends the
# next merge candidate. Fail-closed: no required contexts = no merge.
#
# ENV:
#   PRSHEP_REPO            — owner/repo (auto-detected from git remote)
#   PRSHEP_DEFAULT_BRANCH  — base branch (auto-detected via gh)
#   PRSHEP_REQUIRED_CONTEXTS — override: newline-separated context names
#   PRSHEP_RELEASE_PATTERN — regex for release branch exclusion (default: ^release-please--)
#   PRSHEP_FCFS=1          — first-come-first-served: skip beads ranking
#   PRSHEP_STRICT_RANKING=1 or --strict-ranking — hold gate on unranked READY PRs
#
# Portability floor: bash 3.2 + BSD/GNU coreutils.
set -Eeuo pipefail

# --- arg parsing ---
STRICT_RANKING="${PRSHEP_STRICT_RANKING:-0}"
for arg in "$@"; do
  case "$arg" in
    --strict-ranking) STRICT_RANKING=1 ;;
    *) printf 'watch-queue: unknown argument: %s\n' "$arg" >&2; exit 2 ;;
  esac
done
readonly STRICT_RANKING

# --- dependency check ---
for cmd in gh jq git date mktemp; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    printf 'ERROR: required command not found: %s\n' "$cmd" >&2
    exit 127
  fi
done

# --- repo discovery ---
discover_repo() {
  if [[ -n "${PRSHEP_REPO:-}" ]]; then
    printf '%s' "$PRSHEP_REPO"
    return
  fi
  local url
  url=$(git remote get-url origin 2>/dev/null) || {
    printf 'ERROR: cannot discover repo — no git remote and PRSHEP_REPO unset\n' >&2
    exit 1
  }
  # Extract owner/repo from ssh or https URL
  printf '%s' "$url" | sed -E 's|^.*github\.com[:/]||; s|\.git$||'
}

discover_default_branch() {
  if [[ -n "${PRSHEP_DEFAULT_BRANCH:-}" ]]; then
    printf '%s' "$PRSHEP_DEFAULT_BRANCH"
    return
  fi
  gh api "repos/$REPO" --jq .default_branch
}

REPO="$(discover_repo)"
readonly REPO
DEFAULT_BRANCH="$(discover_default_branch)"
readonly DEFAULT_BRANCH
readonly RELEASE_PATTERN="${PRSHEP_RELEASE_PATTERN:-^release-please--}"

# --- required contexts discovery (fail-closed) ---
discover_required_contexts() {
  if [[ -n "${PRSHEP_REQUIRED_CONTEXTS:-}" ]]; then
    printf '%s' "$PRSHEP_REQUIRED_CONTEXTS"
    return
  fi

  # Try branch protection API first
  local bp_contexts
  bp_contexts=$(gh api "repos/$REPO/branches/$DEFAULT_BRANCH/protection/required_status_checks" \
    --jq '.contexts[]' 2>/dev/null) || true

  if [[ -n "$bp_contexts" ]]; then
    printf '%s' "$bp_contexts"
    return
  fi

  # Fallback: rulesets API
  local ruleset_contexts
  ruleset_contexts=$(gh api "repos/$REPO/rules/branches/$DEFAULT_BRANCH" \
    --jq '[.[] | select(.type == "required_status_checks") | .parameters.required_status_checks[].context] | unique | .[]' 2>/dev/null) || true

  if [[ -n "$ruleset_contexts" ]]; then
    printf '%s' "$ruleset_contexts"
    return
  fi

  return 1
}

REQUIRED_CONTEXTS_RAW=""
REQUIRED_CONTEXTS_RAW=$(discover_required_contexts) || {
  printf 'ERROR: no required contexts found (branch protection, rulesets, or PRSHEP_REQUIRED_CONTEXTS). Fail-closed.\n' >&2
  exit 1
}

# Parse into array (bash 3.2 compatible — no mapfile)
REQUIRED_CONTEXTS=()
while IFS= read -r _ctx; do
  [[ -n "$_ctx" ]] && REQUIRED_CONTEXTS+=("$_ctx")
done <<<"$REQUIRED_CONTEXTS_RAW"
readonly REQUIRED_COUNT="${#REQUIRED_CONTEXTS[@]}"

if [[ "$REQUIRED_COUNT" -eq 0 || -z "${REQUIRED_CONTEXTS[0]}" ]]; then
  printf 'ERROR: required contexts list is empty. Fail-closed.\n' >&2
  exit 1
fi

# --- workspace ---
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/prshep-watch-queue.XXXXXX")
trap 'rm -rf -- "$work_dir"' EXIT

prs_json="$work_dir/prs.json"
classified_json="$work_dir/classified.json"

# --- main SHA snapshot ---
main_sha=$(gh api "repos/$REPO/commits/$DEFAULT_BRANCH" --jq .sha)
if [[ ! "$main_sha" =~ ^[0-9a-fA-F]{40}$ ]]; then
  printf 'ERROR: GitHub returned an invalid %s SHA: %s\n' "$DEFAULT_BRANCH" "$main_sha" >&2
  exit 1
fi

# --- fetch open PRs ---
gh pr list -R "$REPO" --state open --base "$DEFAULT_BRANCH" --limit 100 \
  --json number,title,isDraft,headRefName,mergeStateStatus,statusCheckRollup >"$prs_json"

# --- classify PRs ---
# Build required-contexts JSON array for jq
contexts_json=$(printf '%s\n' "${REQUIRED_CONTEXTS[@]}" | jq -R . | jq -s .)

jq -e --argjson required "$contexts_json" --arg release_pat "$RELEASE_PATTERN" '
  [ .[]
    | . as $pr
    | ($pr.statusCheckRollup // []) as $rollup
    | (($pr.headRefName | test($release_pat))
        or ($pr.title | test("^chore(\\(.*\\))?: release"; "i"))) as $release
    | [ $required[] as $name
        | ($rollup | map(select(.name == $name))) as $matches
        | if ($matches | length) == 0 then "ABSENT"
          elif ($matches | length) > 1 then "AMBIGUOUS"
          elif $matches[0].status != "COMPLETED" then "RUNNING"
          elif ($matches[0].conclusion == "SUCCESS"
                or $matches[0].conclusion == "SKIPPED") then "OK"
          else "FAIL"
          end ] as $checks
    | (($release | not)
        and ($pr.isDraft | not)
        and $pr.mergeStateStatus == "CLEAN"
        and ($checks | length) == ($required | length)
        and ($checks | all(. == "OK"))) as $ready
    | {
        number: $pr.number,
        title: ($pr.title[0:52]),
        draft: $pr.isDraft,
        release: $release,
        mergeState: $pr.mergeStateStatus,
        checks: $checks,
        done: ($checks | map(select(. == "OK")) | length),
        total: ($required | length),
        ready: $ready,
        bucket:
          (if $release or $pr.isDraft then "HELD"
           elif $ready then "READY"
           elif $pr.mergeStateStatus == "DIRTY" then "CONFLICT"
           elif ($checks | index("FAIL")) != null then "FAILING"
           elif ($checks | index("RUNNING")) != null then "WAITING"
           elif (($checks | index("ABSENT")) != null
                 or ($checks | index("AMBIGUOUS")) != null) then "STUCK"
           else "WAITING"
           end)
      }
  ]
' "$prs_json" >"$classified_json"

# --- dashboard output ---
printf '== %s  %s/%s ==\n' "$(date -u '+%H:%M:%SZ')" "$REPO" "$DEFAULT_BRANCH"
jq -r --argjson total "$REQUIRED_COUNT" '
  group_by(.bucket)
  | sort_by(.[0].bucket as $bucket
      | ["READY", "FAILING", "STUCK", "CONFLICT", "WAITING", "HELD"]
      | index($bucket))
  | .[]
  | "-- \(.[0].bucket)  (\(length)) --",
    (sort_by(.number) | reverse | .[]
      | "   #\(.number)\(if .release then " [RELEASE]" elif .draft then " [draft]" else "" end)  \(.done)/\($total)  \(.title)")
' "$classified_json"

printf '%s\n' \
  '   note: STUCK = a required context is absent or ambiguous.' \
  '   note: HELD = release or draft. Never rank or merge these.'

# --- ranking via beads merge queue ---
ready_numbers=()
while IFS= read -r _num; do ready_numbers+=("$_num"); done \
  < <(jq -r '.[] | select(.ready) | .number' "$classified_json" | sort -n)

ranked_numbers=()
if [[ "${PRSHEP_FCFS:-0}" != "1" ]] && command -v bd >/dev/null 2>&1; then
  # Beads priority order: bd ready gives them priority-sorted
  while IFS= read -r pr_num; do
    [[ -n "$pr_num" ]] && ranked_numbers+=("$pr_num")
  done < <(bd ready --label pr:merge --json 2>/dev/null | jq -r '.[].metadata.pr // empty')
fi

# Callers MUST pass the haystack as ${arr[@]+"${arr[@]}"}. Under `set -u` bash 3.2
# treats "${arr[@]}" on an EMPTY array as an unbound variable and aborts the whole
# script -- and because the EXIT trap overwrites the status, the caller sees a
# truncated dashboard and exit 0. That is a silent wrong answer, not a crash.
contains_number() {
  local needle="$1"; shift
  local n
  for n in "$@"; do [[ "$n" == "$needle" ]] && return 0; done
  return 1
}

printf '%s\n' '-- MERGE ORDER --'
if [[ "${PRSHEP_FCFS:-0}" == "1" ]]; then
  printf '   (FCFS mode — no ranking enforced)\n'
elif [[ ${#ranked_numbers[@]} -eq 0 ]]; then
  printf '   (no merge beads found — queue empty)\n'
fi

first_ranked_ready=""
if ((${#ranked_numbers[@]} > 0)); then
  for number in "${ranked_numbers[@]}"; do
    if contains_number "$number" ${ready_numbers[@]+"${ready_numbers[@]}"}; then
      [[ -n "$first_ranked_ready" ]] || first_ranked_ready="$number"
      printf '   ranked #%s  READY\n' "$number"
    else
      printf '   ranked #%s  (not ready or no longer open)\n' "$number"
    fi
  done
fi

unranked_ready=()
if ((${#ready_numbers[@]} > 0)); then
  for number in "${ready_numbers[@]}"; do
    if [[ "${PRSHEP_FCFS:-0}" == "1" ]]; then
      # In FCFS mode all ready PRs are valid candidates
      [[ -n "$first_ranked_ready" ]] || first_ranked_ready="$number"
    elif ((${#ranked_numbers[@]} == 0)) || ! contains_number "$number" ${ranked_numbers[@]+"${ranked_numbers[@]}"}; then
      unranked_ready+=("$number")
    fi
  done
fi

if ((${#unranked_ready[@]} > 0)); then
  printf '   !! UNRANKED AND READY:'
  printf ' #%s' "${unranked_ready[@]}"
  printf '\n'
  if [[ "$STRICT_RANKING" == "1" ]]; then
    printf '   !! STRICT: gate held until all READY PRs have merge beads.\n'
  else
    printf '   !! WARNING: create merge beads for these PRs. Auto-appended to queue back.\n'
    # In default mode, unranked ready PRs are appended after ranked ones
    for number in "${unranked_ready[@]}"; do
      [[ -n "$first_ranked_ready" ]] || first_ranked_ready="$number"
    done
  fi
fi

# --- merge gate ---
confirmed_sha=$(gh api "repos/$REPO/commits/$DEFAULT_BRANCH" --jq .sha)
if [[ ! "$confirmed_sha" =~ ^[0-9a-fA-F]{40}$ ]]; then
  printf 'ERROR: GitHub returned an invalid confirmation SHA: %s\n' "$confirmed_sha" >&2
  exit 1
fi

printf '%s\n' '-- MERGE GATE --'
if [[ "$confirmed_sha" != "$main_sha" ]]; then
  printf '   HOLD — %s moved during inspection (%s -> %s). No merge candidate.\n' \
    "$DEFAULT_BRANCH" "${main_sha:0:8}" "${confirmed_sha:0:8}"
elif [[ "$STRICT_RANKING" == "1" ]] && ((${#unranked_ready[@]} > 0)); then
  printf '%s\n' '   HOLD — READY PRs are missing merge beads (strict mode). No merge candidate.'
elif [[ -n "$first_ranked_ready" ]]; then
  printf '   CLEAR — next merge is #%s\n' "$first_ranked_ready"
  printf '%s\n' \
    '          verify the required checks on its HEAD SHA immediately before merging.' \
    '          Only one merge may be in flight at a time.'
else
  printf '%s\n' '   CLEAR — but nothing ranked is READY.'
fi

printf '%s\n' "-- $DEFAULT_BRANCH --"
printf '   %s\n' "${confirmed_sha:0:8}"
