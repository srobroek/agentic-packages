# Quickstart: Validating Bead-as-Brief Orchestration

End-to-end validation scenarios proving the feature works. Run from the repo
root on a machine with bd ≥ 1.1.0, Claude Code ≥ 2.1.198, gh, and jq.

## Prerequisites

```bash
bd --version                 # ≥ 1.1.0
claude --version             # ≥ 2.1.198
apm compile && apm pack      # regenerate artifacts after fleet changes
echo "$CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"   # 1 → warm tier; empty → degraded (both valid)
```

## V1 — Rules engine conformance (SC-002 foundation)

```bash
packages/beads/.apm/scripts/rules-eval-test.sh     # fixture suite
```

Expect: every predicate type exercised; every shipped rules file passes its
fixtures (allow / block / bounce / escape / pause verdicts match).

## V2 — Contract block on incomplete exit (US2)

Simulated: feed the evaluator a fixture bead missing `push` with agent
`domain-specialist` → expect `decision:block` whose reason names only the
`push` check. Then set fixture `state=failed` + FAILED comment → expect allow.
Then run attempt 3 → expect allow + BOUNCE side effects + counters reset.

## V3 — Brief-only spawn + crash resume (US1)

1. Create an epic + one node bead with full metadata + BRIEF.
2. Spawn a specialist with only `CLAIM <node>`; let it checkpoint to its
   worklog wisp; kill it mid-task.
3. Respawn same actor name, same verb. Expect: continues from last
   checkpoint; delivers; stop hook passes; no task data ever in a prompt.

## V4 — Multi-dimension review + graph aggregation (US3)

1. Node labeled `needs-review:code` + `needs-review:security`; report it.
2. Expect two review-wisp shells, both dep-blocking the merge bead, before
   any reviewer spawns.
3. Approve code only → merge bead NOT ready. Approve security → ready, PR
   undrafted by that reviewer, labels swapped to `reviewed:*`.
4. Changes round: verify single batched coder wake with the union of items.

## V5 — Draft-PR landing (US4)

1. Specialist opens draft PR + merge bead. Shepherd patrol: ignores it.
2. Undraft via reviewer flow (V4). Shepherd: probes, acquires slot, merges,
   stamps `merge_sha`/`pr`, closes merge bead, releases claim, sheepdog
   touched.
3. Start a second shepherd against the repo → expect lease refusal + exit.

## V6 — Wisp hygiene (US5, SC-003)

After a full node lifecycle + cleanup: node thread ≤ 6 durable comments;
`bd mol wisp list --all` shows the node's wisps closed; `bd purge --force`
removes them; no dep edge targets a purged bead; epic run record contains the
scribe's folded ledger.

## V7 — Live orchestrated build (SC-001…SC-007 integrated)

The real test: orchestrate a small creative project end-to-end with the new
machinery (planner node → domain specialists → multi-dimension review →
draft-PR landing → scribe report), spanning at least one kill/resume and one
overnight-gap simulation (orchestrator restart mid-run). Success criteria
checked against the run's beads store and transcripts.

Deliverable beyond the run itself: an observations journal
(`specs/002-bead-as-brief/validation-run/`) recording, per iteration, whether
each mechanism behaved — beads, wisps, links, labels, gates, contracts,
hooks, wakes — plus a final mechanism-by-mechanism writeup (worked / broke /
surprised / changed-later).

## Expected overall outcome

All seven scenarios pass on Claude-with-flag; V1–V6 also pass in degraded
mode (no flag) with respawn-only wakes. Divergence in either mode is a
release blocker for the orchestrate package.
