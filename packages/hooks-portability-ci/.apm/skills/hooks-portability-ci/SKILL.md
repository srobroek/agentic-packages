---
name: hooks-portability-ci
description: Lint shipped hook scripts for the portability failure modes the audits found - bash 3.2 parse errors (;;& fallthrough, mapfile/readarray), GNU-only sed/grep constructs (\b word boundaries, +?/*? lazy quantifiers), and string-form tool_input payloads that crash jq. Use when the user asks to check hook portability, lint hooks for bash 3.2 / BSD, run the portability gate, or wire a portability check into CI.
---

# Hook Portability CI

A deterministic CI gate for shipped hook scripts. It reproduces the three real
failure modes the Phase-1/Phase-2 audits caught, so a regression fails CI
instead of failing silently on a user's stock macOS bash.

## What It Checks

For every `*.sh` found under a `*/scripts/` or `*/hooks` path (tests are
excluded), `scripts/portability-check.sh` runs:

1. **bash 3.2 parse** — `/bin/bash -n` against the script. `;;&` fallthrough and
   other bash-4 syntax are parse errors on the 3.2 floor and fail here. Because
   `mapfile`/`readarray` *parse* fine on 3.2 but exit 127 at runtime, they are
   caught by a separate grep, not by `-n`.
2. **GNU-only sed/grep** — flags `\b` word boundaries in `sed` (BSD sed treats
   `\b` literally; BSD grep does support it, so `\b` is scoped to sed) and
   `+?`/`*?` lazy quantifiers in `sed`/`grep` (not BSD ERE). Comment-only lines
   are excluded to avoid false positives on remarks that mention the construct.
3. **string-form `tool_input`** — feeds each PreToolUse-shaped script a
   `{"tool_input":"<cmd>"}` payload (the historical bypass) and asserts it does
   not crash jq with `Cannot index string ...`.

It prints a per-failure summary and exits non-zero if any script fails any
check.

## Run It

```sh
# Default: scan packages/
bash packages/hooks-portability-ci/scripts/portability-check.sh

# Or scan a specific directory
bash packages/hooks-portability-ci/scripts/portability-check.sh path/to/dir
```

Exit codes: `0` all clear, `1` a script failed a check, `2` usage/environment
error (missing dir, or `jq` not installed).

## Requirements

- `bash` (the gate self-selects `/bin/bash` when it is 3.2.x, else PATH `bash`)
- `jq` (for the string-form payload probe)
- BSD or GNU `find`, `grep`, `sed` — the gate itself stays within the bash 3.2 +
  BSD floor it enforces.

## Wire Into CI

Add a job step that runs the gate over the package tree. Example GitHub Actions:

```yaml
- name: Hook portability gate
  run: bash packages/hooks-portability-ci/scripts/portability-check.sh packages
```

The non-zero exit on failure blocks the merge. Run it on macOS runners (or any
runner where `/bin/bash` is 3.2) to exercise the true floor; on Linux runners it
still catches the GNU-ism and string-payload regressions.

## Validate The Gate Itself

```sh
/bin/bash -n packages/hooks-portability-ci/scripts/portability-check.sh
mise exec shellcheck@0.11.0 -- shellcheck -S warning \
  packages/hooks-portability-ci/scripts/portability-check.sh
bats packages/hooks-portability-ci/tests/portability-check.bats
```
