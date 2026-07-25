---
name: agent-conformance
description: Run the agent contract-conformance sweep -- stage fixtures, spawn agents, assert output contracts, report. Use for pre-release sweeps or testing one agent's contract.
---

# Agent Conformance Sweep

Behavioral regression suite for shipped agents: every judgment is made by the
deterministic engine (`scripts/conformance.py`); this skill only orchestrates
spawns. Engine subcommands are documented in the package README and the CLI
contract; invoke as:

```bash
uv run --with pyyaml <pkg>/scripts/conformance.py <check|stage|assert|report> ...
```

where `<pkg>` is this package's root (in the monorepo:
`packages/agent-conformance`).

## Sweep protocol

1. **Check**: run `conformance.py check`. Violations → stop and report them;
   do not sweep a fleet whose fixtures are stale.
2. **Stage**: run `conformance.py stage --all` (or `--agent NAME` /
   `--package PKG` for a scoped sweep). Note the printed manifest path and
   out-dir.
3. **Execute** -- for each manifest entry, in parallel batches of 4:
   - Spawn the entry's `agent` via the Task tool with the entry's `prompt`
     as the task prompt, instructing the subagent that its working directory
     for any file operations is the entry's `sandbox_path`.
   - MUST save the subagent's final reply to the entry's `reply_path`
     verbatim -- the exact returned text, no summarizing, no reformatting, no
     added framing. Write it with the Write tool immediately on receipt.
   - Run `conformance.py assert --manifest <path> --case <agent>/<case>`.
   - On a failed attempt (exit 1): re-spawn the same entry fresh (retry ≤ 2)
     and assert again; the engine tracks attempts and finalizes the verdict.
4. **Report**: run `conformance.py report --out-dir <dir>`; relay the
   totals line and every non-PASS row to the user, with `report.md` path.

## Rules

MUST Save replies verbatim -- a paraphrased reply invalidates the verdict; the
  engine's plausibility floor flags suspicious saves as ERROR.
MUST Work every manifest entry or none -- `report` marks unworked entries as
  ERROR missing-result; never hand-edit the journal.
MUST Model overrides (scoped iteration only): pass the override to the Task
  spawn and note it when reporting -- overridden verdicts are not
  shipped-config evidence.
NOT Judge replies yourself, relax an assertion, or skip `check`. The engine
  is the only judge.
NOT Run the LLM sweep in CI or on a schedule from this skill; that wrapper is
  a separate feature.
