# Quickstart — Agent Conformance Harness

Validation scenarios proving the feature end-to-end. Prereqs: `claude` CLI
authenticated (`claude -p "say ok" --model haiku` succeeds), `uv` installed,
repo checkout.

## 1. Deterministic layer (no LLM, no credentials)

```bash
# Coverage + consistency: every agent has a case or a reasoned skip,
# and every case matches its agent's declared contract.
uv run --with pyyaml packages/agent-conformance/scripts/conformance.py check
# expect: exit 0, "OK: <N> agents, <M> cases, <K> skips"

# Unit suite (same layer, pytest form — what CI runs):
uv run --with pytest --with pyyaml pytest -q packages/agent-conformance/scripts/test_conformance.py
```

Negative probe (SC-001/US2): delete any case dir → `check` exits 1 naming
the agent; restore.

Drift probe (SC-004/FR-011): edit an agent's `CAP` line in a scratch branch →
`check` exits 1 naming the case whose `max_words` no longer matches.

## 2. Single-agent run (SC-005)

```bash
uv run --with pyyaml packages/agent-conformance/scripts/conformance.py \
  run --agent reviewer-low
# expect: exit 0 within ~3 min; report table with one PASS row;
# .conformance-runs/<ts>/report.{json,md} + journal.jsonl written
```

## 3. Full-fleet sweep (SC-002) — costs real tokens

```bash
uv run --with pyyaml packages/agent-conformance/scripts/conformance.py run --all
# expect: < 30 min, every agent exactly once in report (PASS or SKIP+reason)
```

## 4. Violation detection (SC-003)

In a scratch branch, edit `packages/agent-reviewer-low/.apm/agents/reviewer-low.agent.md`
to remove the `L1 VERDICT:` line from its Output contract, update the fixture
to still expect it — then run scenario 2. Expect FAIL with
`failed_assertions[].kind == "first_line"` and the raw reply persisted under
`replies/`. (Run `check` first to see the drift gate catch the same edit
deterministically.)

## 5. Interrupted-sweep recovery

Ctrl-C a fleet run mid-way; then:

```bash
uv run --with pyyaml packages/agent-conformance/scripts/conformance.py \
  report --out-dir .conformance-runs/<ts>
# expect: valid partial report assembled from journal.jsonl
```

Contracts: [cli.md](contracts/cli.md) ·
[case-schema.md](contracts/case-schema.md) ·
[report-schema.md](contracts/report-schema.md) ·
entities: [data-model.md](data-model.md)
