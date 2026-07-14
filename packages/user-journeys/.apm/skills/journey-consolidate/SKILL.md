---
name: journey-consolidate
description: >-
  Consolidation checkpoint for user journeys: human-approved review that
  blesses a journey as current truth, advances last_reviewed, flushes delta
  log entries older than the checkpoint, prunes old run files, and
  regenerates the index. Use after a green validation or when a delta log
  has accumulated. Never runs without explicit human approval per journey.
---

# journey-consolidate

Consolidation is what keeps journey files small and trusted (FORMAT.md,
"Consolidation checkpoints"). An agent prepares and proposes; **only a
human blesses**. Never consolidate as a side effect of another skill.

## Eligibility

Propose consolidation only for journeys where:
- the latest run is `pass` at the journey's current version (or the user
  explicitly waives this), and
- there is something to flush or prune (Δ entries, excess runs) or
  `status: draft` is ready to become `active`.

## Procedure (per journey)

1. Present the review packet: current body (or a summary for long
   journeys), the Δ entries that would be flushed, latest run result +
   date, open findings referencing this journey (grep the tracker for the
   `journey-finding` block / `journey: J<id>`). Open findings against a
   journey are a reason to DEFER consolidation — surface them.
2. Ask the human to bless, per journey (AskUserQuestion for batches). No
   blanket approvals across journeys they haven't seen the packet for.
3. On approval:
   - set `last_reviewed:` to today,
   - delete Δ entries dated on or before the previous `last_reviewed`
     (git retains them),
   - promote `status: draft` → `active` if agreed,
   - prune runs: `journeys.py prune <dir> --keep <runs_keep> --yes`
     (dry-run first, show what dies; `runs_keep` from README frontmatter),
   - reindex: `journeys.py index <dir>`, then lint.
4. Commit: `journey(J<id>): consolidate — last_reviewed <date>`.

## Report

Which journeys were consolidated (entries flushed, runs pruned), which were
deferred and why (open findings, red run, human declined).
