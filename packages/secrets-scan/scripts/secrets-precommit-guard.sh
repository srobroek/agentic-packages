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

# Locate the shared scanner. The canonical scan.sh lives with the skill at
# .apm/skills/secrets-scan/scripts/scan.sh (so the skill's relative `scripts/scan.sh`
# ref resolves on install). This hook ships separately under ${PLUGIN_ROOT}/scripts/,
# so we resolve scan.sh across the layouts it can appear in:
#   1. a sibling in this script's dir (${PLUGIN_ROOT}/scripts/scan.sh) -- the
#      flattened-hook layout, used if a copy is ever materialized next to the hook;
#   2. the canonical skill path relative to this hook (in-repo / co-installed tree).
# First match wins; if none resolve we treat the scanner as absent and skip cleanly.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAN=""
for candidate in \
  "${SCRIPT_DIR}/scan.sh" \
  "${SCRIPT_DIR}/../.apm/skills/secrets-scan/scripts/scan.sh"
do
  if [ -x "$candidate" ]; then
    SCAN="$candidate"
    break
  fi
done

payload="$(cat 2>/dev/null || true)"

# No jq -> we cannot parse the payload safely, so fail open (do not block). The
# scanner itself is the security control; the hook is only the trigger.
command -v jq >/dev/null 2>&1 || exit 0

# Cheap pre-jq bail: this guard acts ONLY on `git commit` commands, so if the raw
# payload contains no `commit` token there is nothing to inspect. Skips the jq
# spawn (the dominant per-call cost) for the common case on the hot path. Pure
# SUPERSET filter on literal bytes — the command still has to survive the
# structured checks below — so it can never mask a command jq would have flagged.
case "$payload" in
  *commit*) ;;
  *) exit 0 ;;
esac

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
# an inherited env var (SECRETS_SCAN_SKIP=1 set in the session) and as a LEADING
# inline prefix on the commit command itself (SECRETS_SCAN_SKIP=1 git commit ...),
# the latter via a scan of the command string since the hook does not inherit the
# tool call's transient env.
if [ "${SECRETS_SCAN_SKIP:-}" = "1" ]; then
  printf 'WARN secrets-scan: SECRETS_SCAN_SKIP=1 set; skipping secret scan for this commit.\n' >&2
  exit 0
fi
# Anchor the inline form to a LEADING env-assignment prefix (`SECRETS_SCAN_SKIP=1
# git commit ...`, optionally after other VAR=val assignments). Matching it
# anywhere in the string let a commit whose MESSAGE merely mentions
# SECRETS_SCAN_SKIP=1 silently bypass the scan — a real TIER-E hole.
#
# CRITICAL: collapse newlines to a single space FIRST. `grep -E` is line-oriented,
# so a multi-line commit body (`git commit -m $'feat\n\nSECRETS_SCAN_SKIP=1'`)
# would otherwise let the `^`-anchor match the start of an INNER body line and
# skip the scan. Flattening to one line means `^` only ever anchors the real
# command start, not an embedded message line.
command_flat="$(printf '%s' "$command" | tr '\n\r' '  ')"
if printf '%s' "$command_flat" | grep -Eq '^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*SECRETS_SCAN_SKIP=1([[:space:]]|$)'; then
  printf 'WARN secrets-scan: SECRETS_SCAN_SKIP=1 on the commit; skipping secret scan.\n' >&2
  exit 0
fi

# Anchor to an actual `git commit` where commit is the SUBCOMMAND (the first
# non-option token), so:
#   * `git commit ...`, `git -C <path> commit ...`, `git --git-dir=... commit`,
#     and a path-prefixed `/usr/bin/git commit` / `./git commit` all FIRE; but
#   * `git help commit`, `git log --grep commit`, `git config commit.gpgsign`,
#     and arbitrary Bash merely containing the word "commit" do NOT.
# The middle group is restricted to OPTION tokens only (-x / --long, plus a
# `-C <dir>` value), so a non-option word like `help`/`log` before `commit`
# breaks the match instead of being swallowed. `git` may be preceded by a path
# segment (a leading `/` or `name/`).
if ! printf '%s' "$command_flat" | grep -Eq '(^|[[:space:]]|/)git([[:space:]]+-[^[:space:]]+([[:space:]]+[^-][^[:space:];&|]*)?)*[[:space:]]+commit($|[[:space:]])'; then
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
