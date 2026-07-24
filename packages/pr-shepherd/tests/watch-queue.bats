#!/usr/bin/env bats

setup() {
  export TEST_ROOT
  TEST_ROOT=$(mktemp -d)
  export SCRIPT
  SCRIPT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)/.apm/skills/pr-shepherd/scripts/watch-queue.sh"
  export PRSHEP_REPO="owner/repo"
  export PRSHEP_DEFAULT_BRANCH="main"
  export PRSHEP_REQUIRED_CONTEXTS
  PRSHEP_REQUIRED_CONTEXTS="$(printf 'CI\nLint\nTest')"
  export PRSHEP_RELEASE_PATTERN="^release-please--"
  export PRSHEP_TEST_PRS="$TEST_ROOT/prs.json"
  export PRSHEP_TEST_MAIN_SHA="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  export PRSHEP_TEST_BD_JSON="$TEST_ROOT/bd.json"
  mkdir -p "$TEST_ROOT/bin"
  export PATH="$TEST_ROOT/bin:$PATH"

  # Default: one green PR, ranked in beads
  printf '[]\n' >"$PRSHEP_TEST_BD_JSON"
  write_pr green false feature/test CLEAN 42
  write_bd_queue 42
  write_stubs
}

teardown() {
  rm -rf -- "$TEST_ROOT"
}

write_pr() {
  local mode="$1" draft="$2" branch="$3" merge_state="$4" number="${5:-42}"
  local checks
  checks=$(jq -n '[
    "CI", "Lint", "Test"
  ] | map({name: ., status: "COMPLETED", conclusion: "SUCCESS"})')

  case "$mode" in
    green) ;;
    missing) checks=$(jq '.[0:2]' <<<"$checks") ;;
    pending) checks=$(jq '.[2].status = "IN_PROGRESS" | .[2].conclusion = null' <<<"$checks") ;;
    failed) checks=$(jq '.[2].conclusion = "FAILURE"' <<<"$checks") ;;
    duplicate) checks=$(jq '. + [.[0]]' <<<"$checks") ;;
    *) return 2 ;;
  esac

  jq -n \
    --argjson draft "$draft" \
    --arg branch "$branch" \
    --arg merge_state "$merge_state" \
    --argjson checks "$checks" \
    --argjson number "$number" \
    '[{number: $number, title: "test queue policy", isDraft: $draft,
       headRefName: $branch, mergeStateStatus: $merge_state,
       statusCheckRollup: $checks}]' >"$PRSHEP_TEST_PRS"
}

write_bd_queue() {
  # Simulate bd ready --label pr:merge --json output
  local numbers=("$@")
  local entries=""
  for n in "${numbers[@]}"; do
    entries+='{"metadata":{"pr":"'"$n"'"}},'
  done
  entries="${entries%,}"
  printf '[%s]\n' "$entries" >"$PRSHEP_TEST_BD_JSON"
}

write_stubs() {
  cat >"$TEST_ROOT/bin/gh" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail

if [[ "$1" == "pr" && "$2" == "list" ]]; then
  cat "$PRSHEP_TEST_PRS"
  exit 0
fi

if [[ "$1" == "api" ]]; then
  # repo info or SHA
  if [[ "$2" == *"/commits/"* ]]; then
    if [[ -n "${PRSHEP_TEST_MAIN_SHA_NEXT:-}" && -f "$TEST_ROOT/sha-read" ]]; then
      printf '%s\n' "$PRSHEP_TEST_MAIN_SHA_NEXT"
    else
      : >"$TEST_ROOT/sha-read"
      printf '%s\n' "$PRSHEP_TEST_MAIN_SHA"
    fi
  elif [[ "$2" == *"/protection/"* ]]; then
    # Return empty to force PRSHEP_REQUIRED_CONTEXTS env usage
    exit 1
  elif [[ "$2" == *"/rules/"* ]]; then
    exit 1
  else
    # repo default branch query
    printf '{"default_branch":"main"}\n'
  fi
  exit 0
fi

printf 'unexpected gh invocation:' >&2
printf ' %q' "$@" >&2
printf '\n' >&2
exit 2
STUB
  chmod +x "$TEST_ROOT/bin/gh"

  cat >"$TEST_ROOT/bin/bd" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "ready" ]]; then
  cat "$PRSHEP_TEST_BD_JSON"
  exit 0
fi
exit 1
STUB
  chmod +x "$TEST_ROOT/bin/bd"

  # git stub for repo discovery (not needed since we set PRSHEP_REPO)
  cat >"$TEST_ROOT/bin/git" <<'STUB'
#!/usr/bin/env bash
printf 'https://github.com/owner/repo.git\n'
STUB
  chmod +x "$TEST_ROOT/bin/git"
}

# --- READY + ranked = merge candidate ---

@test "all contexts pass produces the ranked candidate" {
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"-- READY  (1) --"* ]]
  [[ "$output" == *"CLEAR — next merge is #42"* ]]
}

# --- fail-closed: no required contexts ---

@test "empty PRSHEP_REQUIRED_CONTEXTS fails closed" {
  export PRSHEP_REQUIRED_CONTEXTS=""
  run "$SCRIPT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"required contexts"* ]] || [[ "$output" == *"Fail-closed"* ]] || [[ "$output" == *"empty"* ]]
}

@test "unset PRSHEP_REQUIRED_CONTEXTS with no branch protection fails closed" {
  unset PRSHEP_REQUIRED_CONTEXTS
  run "$SCRIPT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Fail-closed"* ]] || [[ "$output" == *"required contexts"* ]]
}

# --- context classification ---

@test "a missing required context is STUCK" {
  write_pr missing false feature/test CLEAN 42
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"-- STUCK  (1) --"* ]]
  [[ "$output" != *"next merge is #42"* ]]
}

@test "a pending required context is WAITING" {
  write_pr pending false feature/test CLEAN 42
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"-- WAITING  (1) --"* ]]
  [[ "$output" != *"next merge is #42"* ]]
}

@test "a failed required context is FAILING" {
  write_pr failed false feature/test CLEAN 42
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"-- FAILING  (1) --"* ]]
  [[ "$output" != *"next merge is #42"* ]]
}

@test "a duplicate context is STUCK (AMBIGUOUS)" {
  write_pr duplicate false feature/test CLEAN 42
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"-- STUCK  (1) --"* ]]
  [[ "$output" != *"next merge is #42"* ]]
}

# --- exclusions ---

@test "a draft PR is HELD" {
  write_pr green true feature/test CLEAN 42
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"-- HELD  (1) --"* ]]
  [[ "$output" == *"[draft]"* ]]
  [[ "$output" != *"next merge is #42"* ]]
}

@test "a release branch is HELD" {
  write_pr green false release-please--branches--main CLEAN 42
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"-- HELD  (1) --"* ]]
  [[ "$output" == *"[RELEASE]"* ]]
  [[ "$output" != *"next merge is #42"* ]]
}

@test "a dirty PR is CONFLICT" {
  write_pr green false feature/test DIRTY 42
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"-- CONFLICT  (1) --"* ]]
  [[ "$output" != *"next merge is #42"* ]]
}

# --- main SHA snapshot guard ---

@test "main moving during inspection holds the gate" {
  export PRSHEP_TEST_MAIN_SHA_NEXT="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"HOLD — main moved during inspection (aaaaaaaa -> bbbbbbbb)"* ]]
  [[ "$output" != *"next merge is #42"* ]]
}

# --- unranked READY: default mode (auto-append + warning) ---

@test "unranked READY PR in default mode warns and still recommends" {
  write_bd_queue 999  # queue has #999, not #42
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"UNRANKED AND READY"* ]]
  [[ "$output" == *"#42"* ]]
  [[ "$output" == *"WARNING"* ]]
  [[ "$output" == *"CLEAR — next merge is"* ]]
}

# --- unranked READY: strict mode ---

@test "unranked READY PR in strict mode holds the gate" {
  write_bd_queue 999
  export PRSHEP_STRICT_RANKING=1
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"UNRANKED AND READY"* ]]
  [[ "$output" == *"STRICT"* ]]
  [[ "$output" == *"HOLD"* ]]
  [[ "$output" != *"CLEAR — next merge is"* ]]
}

@test "--strict-ranking flag activates strict mode" {
  write_bd_queue 999
  unset PRSHEP_STRICT_RANKING 2>/dev/null || true
  run "$SCRIPT" --strict-ranking
  [ "$status" -eq 0 ]
  [[ "$output" == *"STRICT"* ]]
  [[ "$output" == *"HOLD"* ]]
}

# --- FCFS mode ---

@test "PRSHEP_FCFS=1 skips beads ranking" {
  export PRSHEP_FCFS=1
  write_bd_queue  # empty queue
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"FCFS mode"* ]]
  [[ "$output" == *"CLEAR — next merge is #42"* ]]
}

# --- single merge recommendation ---

@test "only first ranked ready PR is the merge candidate" {
  # Two PRs ready, queue ranks 42 before 43
  jq -n '[
    {number: 42, title: "first", isDraft: false, headRefName: "feat/a", mergeStateStatus: "CLEAN",
     statusCheckRollup: [
       {name: "CI", status: "COMPLETED", conclusion: "SUCCESS"},
       {name: "Lint", status: "COMPLETED", conclusion: "SUCCESS"},
       {name: "Test", status: "COMPLETED", conclusion: "SUCCESS"}]},
    {number: 43, title: "second", isDraft: false, headRefName: "feat/b", mergeStateStatus: "CLEAN",
     statusCheckRollup: [
       {name: "CI", status: "COMPLETED", conclusion: "SUCCESS"},
       {name: "Lint", status: "COMPLETED", conclusion: "SUCCESS"},
       {name: "Test", status: "COMPLETED", conclusion: "SUCCESS"}]}
  ]' >"$PRSHEP_TEST_PRS"
  write_bd_queue 42 43
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"CLEAR — next merge is #42"* ]]
}
