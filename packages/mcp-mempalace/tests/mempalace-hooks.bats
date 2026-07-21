#!/usr/bin/env bats
#
# Tests for mcp-mempalace hook scripts:
#   - mempalace-wake-up.sh    SessionStart tiny-index injection
#   - mempalace-auto-mine.sh  SessionEnd single-transcript auto-mine
#
# mempalace itself is stubbed — these tests cover the shell contract
# (stdin parsing, wing scoping, staging, silence-on-failure), not mining.
#
# Portability floor: bash 3.2.57 + BSD userland.
# Run: bats packages/mcp-mempalace/tests/mempalace-hooks.bats

setup() {
  export GIT_CONFIG_SYSTEM=/dev/null GIT_CONFIG_GLOBAL=/dev/null
  S="$(cd "${BATS_TEST_DIRNAME}/../scripts" && pwd -P)"
  WAKE="$S/mempalace-wake-up.sh"
  MINE="$S/mempalace-auto-mine.sh"
  command -v jq >/dev/null 2>&1 || skip "jq not available"
  command -v git >/dev/null 2>&1 || skip "git not available"

  HOME_DIR="$(mktemp -d "${BATS_TEST_TMPDIR}/home.XXXXXX")"
  export HOME="$HOME_DIR"

  REPO="$(mktemp -d "${BATS_TEST_TMPDIR}/repo.XXXXXX")"
  REPO="$(cd "$REPO" && pwd -P)"
  git -C "$REPO" init -q

  # Stub mempalace on PATH: records invocations, emits canned status.
  BIN="$(mktemp -d "${BATS_TEST_TMPDIR}/bin.XXXXXX")"
  CALLS="$BIN/calls.log"
  cat > "$BIN/mempalace" <<EOF
#!/usr/bin/env bash
echo "\$@" >> "$CALLS"
if [ "\$1" = "status" ]; then
  wing="\$(basename "$REPO")"
  printf '  WING: %s\n    ROOM: technical  12 drawers\n    ROOM: decisions  3 drawers\n' "\$wing"
fi
exit 0
EOF
  chmod +x "$BIN/mempalace"
  export PATH="$BIN:$PATH"
}

# --- parse ------------------------------------------------------------------

@test "scripts parse under /bin/bash" {
  run /bin/bash -n "$WAKE"; [ "$status" -eq 0 ]
  run /bin/bash -n "$MINE"; [ "$status" -eq 0 ]
}

# --- wake-up ----------------------------------------------------------------

@test "wake-up: inside repo with wing memory -> tiny index with wing name and recall pointer" {
  out="$( (cd "$REPO" && /bin/bash "$WAKE") )"
  printf '%s' "$out" | jq -e '.hookSpecificOutput.hookEventName == "SessionStart"' >/dev/null
  ctx="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext')"
  wing="$(basename "$REPO")"
  printf '%s' "$ctx" | grep -q "wing: $wing"
  printf '%s' "$ctx" | grep -q "ROOM: technical"
  printf '%s' "$ctx" | grep -q "mempalace_search"
}

@test "wake-up: does not dump drawer content (no L1 story)" {
  out="$( (cd "$REPO" && /bin/bash "$WAKE") )"
  ctx="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext')"
  ! printf '%s' "$ctx" | grep -q "ESSENTIAL STORY"
}

@test "wake-up: wing without memory -> no output" {
  cat > "$BIN/mempalace" <<'EOF'
#!/usr/bin/env bash
[ "$1" = "status" ] && printf '  WING: some-other-repo\n    ROOM: general  5 drawers\n'
exit 0
EOF
  chmod +x "$BIN/mempalace"
  out="$( (cd "$REPO" && /bin/bash "$WAKE") )"
  [ -z "$out" ]
}

@test "wake-up: outside a git repo -> no output" {
  DIR="$(mktemp -d "${BATS_TEST_TMPDIR}/nongit.XXXXXX")"
  out="$( (cd "$DIR" && /bin/bash "$WAKE") )"
  [ -z "$out" ]
}

@test "wake-up: mempalace missing -> silent exit 0" {
  rm "$BIN/mempalace"
  run /bin/bash -c "cd '$REPO' && /bin/bash '$WAKE'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "wake-up: drains stdin before the missing-dependency gate" {
  rm "$BIN/mempalace"
  run /bin/bash -o pipefail -c '
    dd if=/dev/zero bs=1048576 count=8 2>/dev/null |
      (cd "$1" && PATH=/usr/bin:/bin /bin/bash "$2")
  ' _ "$REPO" "$WAKE"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "wake-up: drains stdin before the non-repo gate" {
  DIR="$(mktemp -d "${BATS_TEST_TMPDIR}/nongit.XXXXXX")"
  run /bin/bash -o pipefail -c '
    dd if=/dev/zero bs=1048576 count=8 2>/dev/null |
      (cd "$1" && PATH="$2:/usr/bin:/bin" /bin/bash "$3")
  ' _ "$DIR" "$BIN" "$WAKE"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- auto-mine --------------------------------------------------------------

_transcript() {
  T="$(mktemp -d "${BATS_TEST_TMPDIR}/tr.XXXXXX")/session-abc.jsonl"
  printf '{"type":"user"}\n{"type":"assistant"}\n' > "$T"
  printf '%s' "$T"
}

_wait_calls() {
  # Detached worker is async; poll briefly for the stub call log.
  expected="${1:-1}"
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    count="$(grep -c -- "--mode convos" "$CALLS" 2>/dev/null || true)"
    [ "$count" -ge "$expected" ] && return 0
    sleep 0.25
  done
  return 1
}

@test "auto-mine: stages this transcript and mines the staging dir with the repo wing" {
  T="$(_transcript)"
  jq -cn --arg t "$T" '{transcript_path:$t}' | (cd "$REPO" && /bin/bash "$MINE")
  _wait_calls
  wing="$(basename "$REPO")"
  grep -q -- "--mode convos --wing $wing" "$CALLS"
  # mined the per-wing staging dir, NOT the original transcript's directory
  grep -q "$HOME/.mempalace/auto-mine/staging/$wing" "$CALLS"
  ! grep -q "$(dirname "$T")" "$CALLS"
}

@test "auto-mine: staged file removed after successful mine" {
  T="$(_transcript)"
  jq -cn --arg t "$T" '{transcript_path:$t}' | (cd "$REPO" && /bin/bash "$MINE")
  _wait_calls
  wing="$(basename "$REPO")"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    n="$(ls "$HOME/.mempalace/auto-mine/staging/$wing/" 2>/dev/null | wc -l | tr -d ' ')"
    [ "$n" = "0" ] && break
    sleep 0.25
  done
  [ "$n" = "0" ]
}

@test "auto-mine: staged file kept when the mine fails (retry on next session)" {
  cat > "$BIN/mempalace" <<EOF
#!/usr/bin/env bash
echo "\$@" >> "$CALLS"
exit 1
EOF
  chmod +x "$BIN/mempalace"
  T="$(_transcript)"
  jq -cn --arg t "$T" '{transcript_path:$t}' | (cd "$REPO" && /bin/bash "$MINE")
  _wait_calls
  wing="$(basename "$REPO")"
  ls "$HOME/.mempalace/auto-mine/staging/$wing/" | grep -q '\.jsonl$'
}

@test "auto-mine: resumed session (grown transcript) stages under a new name" {
  T="$(_transcript)"
  jq -cn --arg t "$T" '{transcript_path:$t}' | (cd "$REPO" && /bin/bash "$MINE")
  printf '{"type":"user"}\n' >> "$T"
  jq -cn --arg t "$T" '{transcript_path:$t}' | (cd "$REPO" && /bin/bash "$MINE")
  _wait_calls 2
  wing="$(basename "$REPO")"
  # both line-count-suffixed names were staged at some point; at minimum the
  # names differ, so the grown transcript is not skipped as already-mined
  run ls "$HOME/.mempalace/auto-mine/staging/$wing/"
  # (files may already be deleted by the successful mine — assert via call log)
  c="$(grep -c -- "--mode convos" "$CALLS")"
  [ "$c" -ge 2 ]
}

@test "auto-mine: no transcript_path on stdin -> exits 0, no mine" {
  printf '{}' | (cd "$REPO" && /bin/bash "$MINE")
  sleep 0.5
  [ ! -s "$CALLS" ]
}

@test "auto-mine: non-jsonl transcript path -> exits 0, no mine" {
  T="$(mktemp "${BATS_TEST_TMPDIR}/evil.XXXXXX.txt")"
  jq -cn --arg t "$T" '{transcript_path:$t}' | (cd "$REPO" && /bin/bash "$MINE")
  sleep 0.5
  [ ! -s "$CALLS" ]
}

@test "auto-mine: outside a git repo -> exits 0, no mine" {
  DIR="$(mktemp -d "${BATS_TEST_TMPDIR}/nongit.XXXXXX")"
  T="$(_transcript)"
  jq -cn --arg t "$T" '{transcript_path:$t}' | (cd "$DIR" && /bin/bash "$MINE")
  sleep 0.5
  [ ! -s "$CALLS" ]
}
