# Quickstart -- Agent Conformance Harness

Validation scenarios proving the feature end-to-end. Prereqs: a Claude Code
session in this repo with the fleet's agents installed, `uv` installed.
The LLM-touching scenarios (2 to 4) run inside a session via the
`/agent-conformance` skill; the deterministic layer (1, 5) is plain CLI.

## 1. Deterministic layer (no LLM, no credentials)

```bash
# Coverage + consistency: every agent has a case or a reasoned skip,
# every case matches its agent's declared contract, sandbox paths safe.
uv run --with pyyaml packages/agent-conformance/scripts/conformance.py check
# expect: exit 0, "OK: <N> agents, <M> cases, <K> skips"

# Unit suite (same layer, pytest form — what CI runs):
uv run --with pytest --with pyyaml pytest -q packages/agent-conformance/scripts/test_conformance.py
```

Negative probe (SC-001/US2): delete any case dir → `check` exits 1 naming
the agent; restore.

Drift probe (SC-004/FR-011): edit an agent's `CAP` line in a scratch branch →
`check` exits 1 naming the case whose `max_words` no longer matches.

## 2. Single-agent sweep (SC-005) -- in-session

In a Claude Code session: `/agent-conformance sweep reviewer-low`

The skill runs: `stage --agent reviewer-low` → Task-spawns the installed
`reviewer-low` agent with the fixture prompt → saves the verbatim reply to
the manifest's `reply_path` → `assert` → `report`.

Expect: complete within ~3 min; report table with PASS row(s);
`.conformance-runs/<ts>/report.{json,md}` + `journal.jsonl` + `manifest.json`.

## 3. Full-fleet sweep (SC-002) -- in-session

`/agent-conformance sweep all`

Expect: < 30 min (4-wide spawn batches), every agent exactly once in the
report (PASS or SKIP+reason); subscription-covered (no API-key spend).

## 4. Violation detection (SC-003)

In a scratch branch, edit `packages/agent-reviewer-low/.apm/agents/reviewer-low.agent.md`
to remove the `L1 VERDICT:` line from its Output contract, reinstall the
agent, keep the fixture expecting it -- then run scenario 2. Expect FAIL with
`failed_assertions[].kind == "first_line"` and the redacted raw reply
persisted under `replies/`. (Run `check` first to see the drift gate catch
the same edit deterministically.)

## 5. Interrupted-sweep recovery

Abort a fleet sweep mid-way; then:

```bash
uv run --with pyyaml packages/agent-conformance/scripts/conformance.py \
  report --out-dir .conformance-runs/<ts>
# expect: valid partial report; unreached manifest entries appear as
# ERROR missing-result (no silently dropped cases)
```

Contracts: [cli.md](contracts/cli.md) ·
[case-schema.md](contracts/case-schema.md) ·
[report-schema.md](contracts/report-schema.md) ·
entities: [data-model.md](data-model.md)
