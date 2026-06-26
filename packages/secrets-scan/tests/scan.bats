#!/usr/bin/env bats
#
# Coverage for the secrets-scan package: the shared scanner (scan.sh) and the
# pre-commit PreToolUse hook (secrets-precommit-guard.sh).
#
# We never install a real scanner. Instead we stub one via SECRETS_SCAN_CMD (an
# absolute path to a fake binary on a temp dir) so the suite is hermetic:
#   - a stub named "gitleaks" exercises the gitleaks routing
#   - a stub named "trufflehog" exercises the trufflehog routing
#   - a generically-named stub exercises the stdin (git diff --cached) branch
# Each stub flags a finding (exit 1) iff the scanned content contains a fake AWS
# key marker, else it is clean (exit 0).
#
# Asserts: staged fake key -> flagged (scan.sh exit 1, hook exit 2); clean diff
# -> pass (exit 0); no scanner -> scan.sh exit 2 and hook WARN+allow (exit 0).
# Also asserts both scripts PARSE under /bin/bash (macOS bash 3.2.57).
#
# Run: bats packages/secrets-scan/tests/scan.bats

setup() {
  SCAN="${BATS_TEST_DIRNAME}/../.apm/skills/secrets-scan/scripts/scan.sh"
  GUARD="${BATS_TEST_DIRNAME}/../scripts/secrets-precommit-guard.sh"

  # Marker the stub treats as a secret. Split so this test file itself does not
  # contain a literal AWS-key-shaped token.
  AWS_KEY="AKIA""IOSFODNN7EXAMPLE"

  # Hermetic temp git repo to stage files into.
  REPO="$(mktemp -d)"
  git -C "$REPO" init -q
  git -C "$REPO" config user.email t@t.t
  git -C "$REPO" config user.name t
  git -C "$REPO" config commit.gpgsign false

  # Temp dir to hold stub scanner binaries.
  STUBDIR="$(mktemp -d)"
}

teardown() {
  [ -n "${REPO:-}" ] && rm -rf "$REPO"
  [ -n "${STUBDIR:-}" ] && rm -rf "$STUBDIR"
}

# Write a stub scanner that flags a finding (exit 1) when the staged diff or its
# stdin contains $AWS_KEY, else exits 0. $1 = stub basename (gitleaks/trufflehog/
# generic). The stub handles all invocation shapes scan.sh uses.
mk_stub() {
  local name="$1"
  local path="${STUBDIR}/${name}"
  cat >"$path" <<STUB
#!/usr/bin/env bash
# Stub scanner. Determine what to inspect based on how scan.sh called us, then
# flag iff the marker is present.
marker='${AWS_KEY}'
content=""
case "\$1" in
  protect|detect)
    # gitleaks routing: inspect the staged diff directly.
    content="\$(git diff --cached 2>/dev/null)"
    ;;
  filesystem)
    # trufflehog routing: remaining args are file paths (or '.'); read them.
    shift
    for a in "\$@"; do
      case "\$a" in
        --*) continue ;;
      esac
      if [ -f "\$a" ]; then content="\$content\$(cat "\$a" 2>/dev/null)"; fi
      if [ -d "\$a" ]; then content="\$content\$(git -C "\$a" diff --cached 2>/dev/null; cat "\$a"/* 2>/dev/null)"; fi
    done
    ;;
  *)
    # generic-override routing: scan.sh pipes 'git diff --cached' on stdin.
    content="\$(cat 2>/dev/null)"
    ;;
esac
case "\$content" in
  *"\$marker"*) echo "stub: secret found"; exit 1 ;;
  *) exit 0 ;;
esac
STUB
  chmod +x "$path"
  echo "$path"
}

# Run scan.sh inside $REPO with a stubbed scanner.
run_scan() {
  local stub="$1"; shift
  output="$(cd "$REPO" && SECRETS_SCAN_CMD="$stub" /bin/bash "$SCAN" "$@" 2>&1)" && status=0 || status=$?
}

# Build a PreToolUse object payload for `git commit`.
mk_commit_payload() {
  jq -cn --arg cmd "$1" '{tool_input: {command: $cmd}}'
}

# Run the hook inside $REPO with a payload on stdin.
run_guard() {
  local payload="$1"; shift
  output="$(cd "$REPO" && "$@" /bin/bash "$GUARD" <<<"$payload" 2>&1)" && status=0 || status=$?
}

# --- parse / portability floor --------------------------------------------

@test "scan.sh parses under /bin/bash (no bash-4 syntax)" {
  run /bin/bash -n "$SCAN"
  [ "$status" -eq 0 ]
}

@test "secrets-precommit-guard.sh parses under /bin/bash (no bash-4 syntax)" {
  run /bin/bash -n "$GUARD"
  [ "$status" -eq 0 ]
}

# --- scan.sh: staged fake AWS key is flagged --------------------------------

@test "scan.sh gitleaks stub: staged AWS key -> finding (exit 1)" {
  printf 'aws_secret=%s\n' "$AWS_KEY" >"$REPO/leak.txt"
  git -C "$REPO" add leak.txt
  run_scan "$(mk_stub gitleaks)" --staged
  [ "$status" -eq 1 ]
  [[ "$output" == *"potential secret"* ]]
}

@test "scan.sh trufflehog stub: staged AWS key -> finding (exit 1)" {
  printf 'aws_secret=%s\n' "$AWS_KEY" >"$REPO/leak.txt"
  git -C "$REPO" add leak.txt
  run_scan "$(mk_stub trufflehog)" --staged
  [ "$status" -eq 1 ]
}

@test "scan.sh generic stub: staged AWS key -> finding (exit 1)" {
  printf 'aws_secret=%s\n' "$AWS_KEY" >"$REPO/leak.txt"
  git -C "$REPO" add leak.txt
  run_scan "$(mk_stub myscanner)" --staged
  [ "$status" -eq 1 ]
}

# --- scan.sh: clean diff passes --------------------------------------------

@test "scan.sh gitleaks stub: clean staged diff -> pass (exit 0)" {
  printf 'hello world, no secrets here\n' >"$REPO/clean.txt"
  git -C "$REPO" add clean.txt
  run_scan "$(mk_stub gitleaks)" --staged
  [ "$status" -eq 0 ]
  [[ "$output" == *"clean"* ]]
}

@test "scan.sh generic stub: clean staged diff -> pass (exit 0)" {
  printf 'hello world, no secrets here\n' >"$REPO/clean.txt"
  git -C "$REPO" add clean.txt
  run_scan "$(mk_stub myscanner)" --staged
  [ "$status" -eq 0 ]
}

# --- scan.sh: no scanner installed -> tooling-gap exit 2 --------------------

@test "scan.sh: no scanner on PATH -> exit 2 with install hint" {
  if command -v gitleaks >/dev/null 2>&1 || command -v trufflehog >/dev/null 2>&1; then
    skip "a real scanner is installed; cannot assert the no-scanner path"
  fi
  printf 'aws_secret=%s\n' "$AWS_KEY" >"$REPO/leak.txt"
  git -C "$REPO" add leak.txt
  # Force-empty SECRETS_SCAN_CMD. PATH is left intact (jq/git live outside
  # /usr/bin here); the test machine has no gitleaks/trufflehog, so the
  # command -v checks naturally miss and we hit the tooling-gap path.
  output="$(cd "$REPO" && SECRETS_SCAN_CMD="" /bin/bash "$SCAN" --staged 2>&1)" && status=0 || status=$?
  [ "$status" -eq 2 ]
  [[ "$output" == *"no secret scanner"* ]]
}

# --- hook: staged fake key blocks the commit --------------------------------

@test "hook: staged AWS key + git commit -> block (exit 2)" {
  printf 'aws_secret=%s\n' "$AWS_KEY" >"$REPO/leak.txt"
  git -C "$REPO" add leak.txt
  run_guard "$(mk_commit_payload 'git commit -m "feat: x"')" env "SECRETS_SCAN_CMD=$(mk_stub gitleaks)"
  [ "$status" -eq 2 ]
  [[ "$output" == *"BLOCKED"* ]]
  [[ "$output" == *"SECRETS_SCAN_SKIP=1"* ]]
}

# --- hook: clean diff allows the commit -------------------------------------

@test "hook: clean staged diff + git commit -> allow (exit 0)" {
  printf 'hello world\n' >"$REPO/clean.txt"
  git -C "$REPO" add clean.txt
  run_guard "$(mk_commit_payload 'git commit -m "fix: y"')" env "SECRETS_SCAN_CMD=$(mk_stub gitleaks)"
  [ "$status" -eq 0 ]
}

# --- hook: no scanner -> WARN + allow ---------------------------------------

@test "hook: no scanner installed -> WARN and allow (exit 0)" {
  if command -v gitleaks >/dev/null 2>&1 || command -v trufflehog >/dev/null 2>&1; then
    skip "a real scanner is installed; cannot assert the no-scanner path"
  fi
  printf 'aws_secret=%s\n' "$AWS_KEY" >"$REPO/leak.txt"
  git -C "$REPO" add leak.txt
  # Empty SECRETS_SCAN_CMD; real PATH retained so jq/git resolve. With no real
  # scanner present, scan.sh returns the tooling-gap code and the hook WARNs.
  run_guard "$(mk_commit_payload 'git commit -m "z"')" env "SECRETS_SCAN_CMD="
  [ "$status" -eq 0 ]
  [[ "$output" == *"WARN"* ]]
  [[ "$output" == *"no secret scanner installed"* ]]
}

# --- hook: bypass escape hatch ----------------------------------------------

@test "hook: SECRETS_SCAN_SKIP=1 env -> skip scan and allow (exit 0)" {
  printf 'aws_secret=%s\n' "$AWS_KEY" >"$REPO/leak.txt"
  git -C "$REPO" add leak.txt
  run_guard "$(mk_commit_payload 'git commit -m "x"')" env "SECRETS_SCAN_SKIP=1" "SECRETS_SCAN_CMD=$(mk_stub gitleaks)"
  [ "$status" -eq 0 ]
  [[ "$output" == *"skipping secret scan"* ]]
}

@test "hook: SECRETS_SCAN_SKIP=1 inline prefix -> skip scan and allow (exit 0)" {
  printf 'aws_secret=%s\n' "$AWS_KEY" >"$REPO/leak.txt"
  git -C "$REPO" add leak.txt
  run_guard "$(mk_commit_payload 'SECRETS_SCAN_SKIP=1 git commit -m "x"')" env "SECRETS_SCAN_CMD=$(mk_stub gitleaks)"
  [ "$status" -eq 0 ]
}

# --- hook: non-commit git command is ignored --------------------------------

@test "hook: git status is ignored (not a commit) -> allow (exit 0)" {
  printf 'aws_secret=%s\n' "$AWS_KEY" >"$REPO/leak.txt"
  git -C "$REPO" add leak.txt
  run_guard "$(mk_commit_payload 'git status')" env "SECRETS_SCAN_CMD=$(mk_stub gitleaks)"
  [ "$status" -eq 0 ]
}

# --- hook: string-form payload is handled (no bypass) -----------------------

@test "hook: string-form tool_input with staged key -> block (exit 2)" {
  printf 'aws_secret=%s\n' "$AWS_KEY" >"$REPO/leak.txt"
  git -C "$REPO" add leak.txt
  payload="$(jq -cn --arg cmd 'git commit -m "x"' '{tool_input: $cmd}')"
  run_guard "$payload" env "SECRETS_SCAN_CMD=$(mk_stub gitleaks)"
  [ "$status" -eq 2 ]
}

# --- hook: empty / non-JSON stdin -> allow ----------------------------------

@test "hook: empty stdin -> allow (exit 0)" {
  run_guard "" env "SECRETS_SCAN_CMD=$(mk_stub gitleaks)"
  [ "$status" -eq 0 ]
}

@test "hook: non-JSON stdin -> allow (exit 0)" {
  run_guard "not json at all" env "SECRETS_SCAN_CMD=$(mk_stub gitleaks)"
  [ "$status" -eq 0 ]
}
