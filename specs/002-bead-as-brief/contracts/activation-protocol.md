# Contract: Activation & Communication Protocol

## Activation messages

| Target | Prompt |
|---|---|
| Node work (directed) | `CLAIM <node-bead-id>` |
| Node work (pull mode) | `CLAIM queue:<label-filter>` (tier-filtered) |
| Review | `CLAIM <review-wisp-id>` |
| Advice/research question | `CLAIM <escalation-wisp-id>` |
| Ledger drain | `CLAIM <query-wisp-id>` or resume |

Nothing else. Any task or runtime mechanics in an activation message violate
FR-002.

## Allocation prompts

A claim-holder starts with one exact wait-only bootstrap. A checkout-backed
resource uses:

```text
WAIT checkout=<absolute-worktree>
RESOURCE <bead-or-wisp-id>
Do not invoke tools or start work.
The controlling parent will release you with exactly CLAIM <bead-or-wisp-id>.
```

The resource must exist and remain unclaimed. A checkout-backed resource must
already carry its canonical `metadata.worktree` as an absolute path. The
orchestrator sends the activation message as a separate message to the waiting
runtime. No task data, runtime mechanics appendix, or combined WAIT plus CLAIM
message is valid.

Write authority comes from holding the claim. The claim-holder takes it with
`bd update <resource-id> --claim`, which sets the assignee, and holds it until
it stops.

A queue actor also receives a checkout:

```text
WAIT checkout=<absolute-worktree>
QUEUE <label-filter>
Do not invoke tools or start work.
The controlling parent will release you with exactly CLAIM queue:<label-filter>.
```

## Actor naming (claim-derivation dependency)

`<role>-<node-bead>` (node-scoped) · `<role>-<domain>[-n]` (specialist) ·
`advisor-<wisp-id>` · `shepherd-<run>-<repo>` (in-run) ·
`pr-shepherd-<repo>` (repository-global) · children `<parent>.<k>` (never
claim). The universal Stop hook derives its `--assignee` fallback query from the
assignee name. A resource that carries no `worktree` resolves only through that
query.

## Wake protocol

1. Probe capability at run start (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`).
2. Wake = `SendMessage` to the actor's live runtime → on a dead runtime →
   respawn `CLAIM <same-bead>` under the same actor name.
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

1. Agent creates an open, unassigned `agent:integrator` merge bead and adds
   `bd dep add <work> <merge-bead>`.
2. Agent opens a draft PR with `Merge-Bead:` in the body, then reports.
3. The bundled run shepherd ignores drafts. On ready and unblocked, it claims,
   probes through the shared safeguards, acquires the slot, merges, stamps,
   closes, and releases.
4. Content problems become a fix bead plus park and release, never an edit.
5. Both shepherd lifecycles acquire, touch, and release the deterministic
   repository sheepdog through the dependency-owned landing executable.
6. The standalone pr-shepherd uses the transaction only for repository-global
   drain or recovery when no live run shepherd holds that lease.

## Ledger protocol

Any actor: fire-and-forget `[wisp:ledger]` linked to its node. Scribe: timer
gate expiry → drain all open ledger wisps → fold into epic run record → close
them → re-arm gate. Run end: T0 triggers final drain + report.
