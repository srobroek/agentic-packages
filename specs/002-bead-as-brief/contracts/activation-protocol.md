# Contract: Activation & Communication Protocol

## Spawn prompts (complete grammar)

| Target | Prompt |
|---|---|
| Node work (directed) | `CLAIM <node-bead-id>` |
| Node work (pull mode) | `CLAIM queue:<label-filter>` (tier-filtered) |
| Review | `CLAIM <review-wisp-id>` |
| Advice/research question | `CLAIM <escalation-wisp-id>` |
| Ledger drain | `CLAIM <query-wisp-id>` or resume |

Nothing else. Any task data in a spawn prompt is a contract violation of
FR-002. The orchestrator MAY append runtime-only details the bead cannot
carry (e.g. "teams flag off -- poll, don't wait").

## Actor naming (claim-derivation dependency)

`<role>-<node-bead>` (node-scoped) · `<role>-<domain>[-n]` (specialist) ·
`advisor-<wisp-id>` · `pr-shepherd-<repo>` · children `<parent>.<k>` (never
claim). The universal Stop hook derives the claim query from the assignee
name -- naming is load-bearing.

## Wake protocol

1. Probe capability at run start (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`).
2. Wake = `SendMessage(agent_id)` → on dead handle → respawn
   `CLAIM <same-bead>` under the same actor name.
3. Respawned actor reads: bead metadata → BRIEF → durable comments → worklog
   wisp thread (via links). Resume point = last CHECKPOINT.
4. No live waiting: blocked actors write the escalation wisp, checkpoint, and
   exit (pause state) -- or bounded-poll (60s tick, 15 to 30min cap) on
   non-resume runtimes.
5. Freshness rule: prefer respawn over resume after ~2 rounds on the same
   node or post-compaction.

## Review round protocol

1. Orchestrator at `reported`: read `needs-review:*` → create ALL wisp shells
   + dep edges to merge bead atomically → then spawn reviewers.
2. Reviewer: claim wisp → review → verdict line on node → GitHub review →
   approve: close wisp + swap label (one act) | changes: wisp stays open with
   FIX material.
3. Last close unblocks merge bead → that reviewer runs `gh pr ready`.
4. Fix round: barrier on all round verdicts → coder woken once with the union
   → re-review only still-open dimensions (+ scope-retriggered ones).

## Landing protocol

Agent: merge bead (open, unassigned, `agent:integrator`) + `bd dep add
<work> <merge-bead>` → draft PR with `Merge-Bead:` in body → report.
Shepherd: ignore drafts → on ready+unblocked: claim → probe → slot → merge →
stamp → close → release. Content problems: fix bead + park + release, never
edit.

## Ledger protocol

Any actor: fire-and-forget `[wisp:ledger]` linked to its node. Scribe: timer
gate expiry → drain all open ledger wisps → fold into epic run record → close
them → re-arm gate. Run end: T0 triggers final drain + report.
