#!/usr/bin/env bash
set -euo pipefail

# scan.sh
#
# Scan staged changes (or the working tree) for committed secrets using whatever
# scanner is on PATH -- gitleaks preferred, then trufflehog. Shared by the
# secrets-scan skill (run it manually) and the pre-commit PreToolUse hook (it
# gates `git commit`).
#
# Modes:
#   scan.sh             scan the staged diff (git diff --cached); default
#   scan.sh --staged    same as default, made explicit
#   scan.sh --working   scan the working tree (tracked + untracked, not ignored)
#
# Exit codes (a stable contract the hook relies on):
#   0  clean: a scanner ran and found nothing
#   1  finding: a scanner ran and flagged a secret
#   2  no scanner installed (gitleaks/trufflehog both absent) -- caller decides
#      whether to warn-and-allow (the hook does) or treat as an error
#
# Portability floor: bash 3.2.57 + BSD userland. No mapfile, no PCRE, no \b.
# Scanner override (testing): SECRETS_SCAN_CMD forces a specific binary name so
# the bats suite can stub gitleaks/trufflehog without installing them.

mode="staged"
case "${1:-}" in
  ""|--staged) mode="staged" ;;
  --working) mode="working" ;;
  -h|--help)
    cat <<'EOF'
usage: scan.sh [--staged|--working]
  --staged   scan the staged diff (default)
  --working  scan the working tree
exit: 0 clean, 1 secret found, 2 no scanner installed
EOF
    exit 0
    ;;
  *)
    printf 'scan.sh: unknown argument: %s\n' "$1" >&2
    exit 2
    ;;
esac

# We must be inside a git work tree to scan staged/working changes.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf 'secrets-scan: not inside a git work tree; nothing to scan.\n' >&2
  exit 0
fi

# Pick a scanner. An explicit override wins so tests can stub a fake binary.
scanner=""
if [ -n "${SECRETS_SCAN_CMD:-}" ]; then
  scanner="$SECRETS_SCAN_CMD"
elif command -v gitleaks >/dev/null 2>&1; then
  scanner="gitleaks"
elif command -v trufflehog >/dev/null 2>&1; then
  scanner="trufflehog"
fi

if [ -z "$scanner" ]; then
  # No scanner: this is a tooling gap, not a finding. Tell the caller via exit 2
  # and let it decide. The hook warns and allows; a human running the skill gets
  # an install hint.
  {
    printf 'secrets-scan: no secret scanner found on PATH (looked for gitleaks, trufflehog).\n'
    printf 'Install one to enable scanning:\n'
    printf '  brew install gitleaks       # or: https://github.com/gitleaks/gitleaks\n'
    printf '  brew install trufflehog      # or: https://github.com/trufflesecurity/trufflehog\n'
  } >&2
  exit 2
fi

# Derive the base name so a stubbed override like /tmp/stub/gitleaks still routes
# to the gitleaks branch.
scanner_base="$(basename "$scanner")"

run_gitleaks() {
  # gitleaks "protect --staged" scans the staged diff; "detect --no-git" scans
  # the working tree as files. --redact keeps printed secrets out of logs.
  # Exit status: 0 = clean, non-zero = leak found (or error). We treat any
  # non-zero as a finding for the staged path; that is the conservative choice
  # for a pre-commit gate.
  if [ "$mode" = "staged" ]; then
    "$scanner" protect --staged --redact --no-banner 2>&1
  else
    "$scanner" detect --no-git --redact --no-banner 2>&1
  fi
}

run_trufflehog() {
  # trufflehog filesystem mode scans paths. For the staged set we feed it the
  # list of staged files; for working mode we scan the repo root. --fail makes
  # trufflehog exit non-zero when a verified/!unknown result is found.
  if [ "$mode" = "staged" ]; then
    # Collect staged (Added/Copied/Modified) paths, NUL-delimited for safety.
    staged_files="$(git diff --cached --name-only --diff-filter=ACM -z 2>/dev/null || true)"
    if [ -z "$staged_files" ]; then
      printf 'secrets-scan: no staged files to scan.\n' >&2
      return 0
    fi
    # xargs -0 passes each path to a single trufflehog invocation over the repo.
    # trufflehog has no native staged mode, so scan the listed files in place.
    printf '%s' "$staged_files" | xargs -0 "$scanner" filesystem --fail --no-update 2>&1
  else
    "$scanner" filesystem --fail --no-update . 2>&1
  fi
}

# Run the chosen scanner, capture output, and translate its exit into our
# contract. We capture rather than stream so the hook can fold findings into one
# actionable message.
output=""
status=0
case "$scanner_base" in
  gitleaks)
    output="$(run_gitleaks)" && status=0 || status=$?
    ;;
  trufflehog)
    output="$(run_trufflehog)" && status=0 || status=$?
    ;;
  *)
    # Unknown override binary: run it bare on the staged diff via stdin so a
    # generic stub can still signal a finding through its exit code.
    output="$(git diff --cached 2>/dev/null | "$scanner" 2>&1)" && status=0 || status=$?
    ;;
esac

if [ "$status" -eq 0 ]; then
  printf 'secrets-scan: clean (%s, %s).\n' "$scanner_base" "$mode"
  exit 0
fi

# Non-zero scanner exit == finding (or scanner error). Surface the output and
# fail with our finding code so the hook can block.
{
  printf 'secrets-scan: potential secret(s) detected by %s (%s scan).\n' "$scanner_base" "$mode"
  if [ -n "$output" ]; then
    printf -- '---\n%s\n---\n' "$output"
  fi
} >&2
exit 1
