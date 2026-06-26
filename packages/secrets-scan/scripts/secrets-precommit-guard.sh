#!/usr/bin/env bash
set -euo pipefail

# secrets-precommit-guard.sh
#
# PreToolUse hook (Claude + Codex). Gates `git commit`: runs the secret scanner
# over the staged diff and blocks the commit (exit 2) when a secret is found.
#
# Decision model (the Claude-native PreToolUse contract; Codex honors non-zero
# the same way):
#   - scanner clean      -> exit 0 (allow)
#   - scanner finding     -> print an actionable block message to stderr, exit 2
#   - no scanner on PATH  -> print a WARN to stderr, exit 0 (allow). A missing
#                            scanner is a tooling gap, not a reason to wedge the
#                            human's commit -- we never block on absent tooling.
#
# Portability floor: bash 3.2.57 + BSD grep. No PCRE, no \b.

# Locate the shared scanner relative to this script (works under ${PLUGIN_ROOT}).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAN="${SCRIPT_DIR}/scan.sh"

payload="$(cat 2>/dev/null || true)"

# No jq -> we cannot parse the payload safely, so fail open (do not block). The
# scanner itself is the security control; the hook is only the trigger.
command -v jq >/dev/null 2>&1 || exit 0

# String-form tool_input idiom: tool_input may be an object {command: "..."} or
# a bare string. Naive '.tool_input.command // .tool_input' THROWS on a string
# input and silently bypasses the guard, so type-check first.
command="$(
  printf '%s' "$payload" | jq -r '
    if (.tool_input|type)=="string" then .tool_input
    else (.tool_input.command // empty) end
  ' 2>/dev/null || true
)"

if [ -z "$command" ] || [ "$command" = "null" ]; then
  exit 0
fi

# Documented bypass: a deliberate, per-invocation escape hatch. Honored both as
# an inherited env var (SECRETS_SCAN_SKIP=1 set in the session) and as an inline
# prefix on the commit command itself (SECRETS_SCAN_SKIP=1 git commit ...), the
# latter via a scan of the command string since the hook does not inherit the
# tool call's transient env.
if [ "${SECRETS_SCAN_SKIP:-}" = "1" ]; then
  printf 'WARN secrets-scan: SECRETS_SCAN_SKIP=1 set; skipping secret scan for this commit.\n' >&2
  exit 0
fi
if printf '%s' "$command" | grep -Eq '(^|[[:space:]])SECRETS_SCAN_SKIP=1([[:space:]]|$)'; then
  printf 'WARN secrets-scan: SECRETS_SCAN_SKIP=1 on the commit; skipping secret scan.\n' >&2
  exit 0
fi

# Anchor to an actual `git commit`. Fires for `git commit ...` and for
# `git -C <path> commit ...` / `git --git-dir=... commit ...`, but NOT for other
# git subcommands or arbitrary Bash that merely contains the word "commit". The
# middle group allows global git options within one command segment.
if ! printf '%s' "$command" | grep -Eq '(^|[[:space:]])git([[:space:]][^;&|]*)?[[:space:]]+commit($|[[:space:]])'; then
  exit 0
fi

# The scanner is missing -> not installed in this environment; skip cleanly.
[ -x "$SCAN" ] || exit 0

# Run the scanner over the staged diff. Capture output + exit so we can map the
# scan.sh contract (0 clean / 1 finding / 2 no-scanner) onto the hook contract.
scan_out=""
scan_status=0
scan_out="$(/bin/bash "$SCAN" --staged 2>&1)" && scan_status=0 || scan_status=$?

case "$scan_status" in
  0)
    # Clean.
    exit 0
    ;;
  2)
    # No scanner on PATH: warn and allow. Never block on missing tooling.
    {
      printf 'WARN secrets-scan: no secret scanner installed (gitleaks/trufflehog).\n'
      printf 'Commit allowed WITHOUT a secret scan. Install gitleaks or trufflehog to enable gating.\n'
    } >&2
    exit 0
    ;;
  *)
    # Finding (exit 1) or scanner error: block with an actionable message and a
    # documented bypass.
    {
      printf 'BLOCKED: secrets-scan found a potential secret in the staged changes.\n'
      if [ -n "$scan_out" ]; then
        printf '%s\n' "$scan_out"
      fi
      printf 'Do NOT commit credentials. To resolve:\n'
      printf '  1. Remove the secret from the staged files (git restore --staged <file>, edit, re-add).\n'
      printf '  2. If it is a false positive, add an inline allow per your scanner:\n'
      printf '       gitleaks:   append "  # gitleaks:allow" to the line, or use a .gitleaksignore entry.\n'
      printf '       trufflehog: tune detectors / exclude the path via config.\n'
      printf '  3. Bypass (use sparingly, you accept the risk): set SECRETS_SCAN_SKIP=1 in the\n'
      printf '     environment for the commit, e.g. SECRETS_SCAN_SKIP=1 git commit ...\n'
      printf 'Then re-run the commit.\n'
    } >&2
    exit 2
    ;;
esac
