# CLI Contract -- `conformance.py` (deterministic engine)

Invocation: `uv run --with pyyaml packages/agent-conformance/scripts/conformance.py <subcommand>`.
Non-interactive; deterministic exit codes (FR-010). No subcommand calls an
LLM -- model execution belongs to the sweep driver (the package skill), which
spawns agents via the Task tool and shells back into `assert`/`report`.

## `check` -- coverage + consistency (no LLM, per-PR eligible)

```
conformance.py check
```

- Coverage: every discovered agent (`packages/*/.apm/agents/*.agent.md`,
  FR-001) has ≥1 case or a skip entry; no stale skip/case references
  (FR-002, US2).
- Case validity: YAML schema, regexes compile, regime consistent,
  `sandbox.files` keys relative with no `..`/leading-`/` (R11.2), pattern
  complexity within bounds (R11.5).
- Drift: case expectations vs source-derived contract slice (FR-011, SC-004).

Exit codes: `0` clean; `1` any violation (one per line:
`AGENT <name>: <violation>`).

## `stage` -- prepare sandboxes and the run manifest

```
conformance.py stage [--all | --agent NAME ... | --package PKG ...]
                     [--out-dir PATH]   # default .conformance-runs/<utc-ts>/
```

- Creates `<out-dir>/manifest.json`: one entry per selected case --
  `{agent, case, prompt, sandbox_path, reply_path, model, effort,
  model_source, timeout_s, budget_usd, regime}` -- plus the skip list.
- Creates each sandbox (temp-style dir under `<out-dir>/sandboxes/`), stages
  `sandbox.files`, runs `git init`+commit when `sandbox.git: true`.
- Verifies each selected agent exists in the installed agent registry
  (`~/.claude/agents` or project agents); missing install → staging error
  (exit 2), never a FAIL.
- Prints the manifest path; the sweep driver iterates manifest entries.

Exit codes: `0` staged; `1` selection matched nothing; `2` environment error.

## `assert` -- judge one captured reply (pure)

```
conformance.py assert --manifest PATH --case <agent>/<case> [--attempt N]
```

- Reads the reply file at the manifest's `reply_path` (written verbatim by
  the sweep driver), applies the assertion engine (first line, cap for
  regime, no-reprint, patterns, artifacts in sandbox), redacts high-entropy
  token patterns before persisting non-PASS replies (R11.3).
- Appends/updates the CaseResult line in `<out-dir>/journal.jsonl`
  (attempts accumulate; verdict finalizes per retry policy R5).
- Prints the attempt verdict line: `ASSERT <agent>/<case> attempt=N
  passed=true|false [failed=<kinds>]`.

Exit codes: `0` attempt passed; `1` attempt failed (assertions); `2` reply
missing/unreadable or manifest mismatch.

## `report` -- assemble reports from the journal

```
conformance.py report --out-dir PATH [--strict-flaky]
```

- Rebuilds `report.json` + `report.md` from `manifest.json` +
  `journal.jsonl` (valid on partial journals -- interrupted-sweep edge case).
- Enforces the no-dropped-case invariant: any manifest entry without a
  journal verdict is reported ERROR (`missing-result`), so the sweep driver
  cannot silently skip a case.

Exit codes mirror verdict totals: `0` all PASS/SKIP (FLAKY unless
`--strict-flaky`); `1` any FAIL (or FLAKY under strict); `2` any ERROR.

## Headless fallback (deferred to orc-qrt -- documented, not built in v1)

`run --engine headless` will wrap stage→spawn→assert→report in one process
using `claude -p` (API-billed): restricted `--tools Read,Grep,Glob` by
default, `--permission-mode plan` for Bash-bearing agents,
`--max-budget-usd` per case and `--max-run-budget-usd` aggregate (default
$25) per R11. Its CLI surface is reserved here so v1 flag names stay
forward-compatible.
