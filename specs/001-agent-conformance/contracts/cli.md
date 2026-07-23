# CLI Contract — `conformance.py`

Invocation: `uv run --with pyyaml packages/agent-conformance/scripts/conformance.py <subcommand>`
(or via the package skill). Non-interactive; deterministic exit codes (FR-010).

## `run` — execute conformance cases (LLM-in-the-loop)

```
conformance.py run [--all | --agent NAME ... | --package PKG ...]
                   [--model MODEL]            # override; stamped model_source=override
                   [--default-model MODEL]    # for unpinned agents (default: sonnet)
                   [--jobs N]                 # default 4
                   [--retries N]              # default 2
                   [--strict-flaky]           # FLAKY → exit 1
                   [--timeout-s N]            # per-case default 120
                   [--budget-usd X]           # per-case default 1.00
                   [--out-dir PATH]           # default .conformance-runs/<utc-timestamp>/
                   [--bare]                   # pass --bare to claude (API-key envs)
```

Behavior:
- Discovers agents from `packages/*/.apm/agents/*.agent.md` (FR-001).
- Fails fast (exit 2) before any case if `claude` is missing or auth is
  unusable (probe: `claude -p "ping" --model haiku` equivalent cheap call or
  documented credential check) — FR-010.
- Runs each selected case per R1; appends CaseResult lines to
  `<out-dir>/journal.jsonl` as cases complete; writes `report.json` +
  `report.md` at the end.
- Prints the human summary table to stdout.

Exit codes: `0` all PASS/SKIP (and FLAKY unless `--strict-flaky`); `1` any
FAIL (or FLAKY under `--strict-flaky`); `2` any ERROR / config failure.

## `check` — deterministic coverage + consistency (no LLM)

```
conformance.py check
```

- Coverage: every discovered agent has ≥1 case or a skip entry; no stale
  skip/case references (FR-002, US2).
- Case validity: YAML schema, regexes compile, regime consistent.
- Drift: case expectations vs source-derived contract slice (FR-011, SC-004).

Exit codes: `0` clean; `1` any violation (each printed as
`AGENT <name>: <violation>` one per line).

## `report` — re-render from a journal

```
conformance.py report --out-dir PATH
```

Rebuilds `report.json`/`report.md` from an existing (possibly partial)
journal. Exit code mirrors the journal's verdict totals (same rules as
`run`). Supports the interrupted-sweep edge case.
