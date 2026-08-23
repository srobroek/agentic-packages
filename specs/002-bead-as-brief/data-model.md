# Data Model: Bead-as-Brief Orchestration Contracts

Authoritative definitions live in [design.md](design.md). This file indexes
them for planning and validation.

## Entities

### Node bead
One unit of run work. Durable, synced.

| Field group | Keys | Writer |
|---|---|---|
| Planning | `scope`, `base_ref`, `base_sha`, `execution_task_kind`, `execution_kind`, `artifacts_dir`, `model?`, `complexity_tier`, `tool_hints?`, `skill_hints?` | planner node / orchestrator at creation |
| Activation | `actor`, `branch`, `worktree`, `lease_token`, `runtime_handle`, `runtime_context`, `execution_dispatch`, `execution_agent` | orchestrator before release |
| Delivery | `push` (git kind) · `output_ref` (artifact/comment kinds) | claiming agent |
| Landing | `merge_sha`, `pr` | bundled run shepherd or standalone pr-shepherd |
| Counters | `stop_attempts`, `review_round` | hooks (reset at bounce) |

Superseded 2026-08-24. Bead orc-eopq retired the `lease_token`,
`runtime_handle`, and `runtime_context` activation keys, together with the bind
handshake that produced them. Write authority comes from holding the bead claim
(`bd update <bead> --claim`, which sets the assignee). The SubagentStop hook
resolves the claimed resource by matching the agent's `cwd` against the absolute
`metadata.worktree`, then narrowing to the active claim. See
[contracts/hook-io.md](contracts/hook-io.md).

Comments (durable thread, ≤6 healthy): BRIEF · REPORTED · verdict lines
(`REVIEW dim=<d> round=<n> verdict=<v>`) · BOUNCE · FAILED · closing summary.

Validation rules: `output_ref` never under `worktree`, must be under
`artifacts_dir` (artifact kind); no metadata key but `worktree` may point into
a worktree; every key referenced by ≥1 rule, spawn decision, or landing step.

### Merge bead
One PR's landing record. Created (open, unassigned, `agent:integrator`) by
whichever agent opens the PR, before `gh pr create`; PR body carries
`Merge-Bead:` id. Blocked by: review wisps (dep edges), fix beads. Ready ⇔
undrafted + all blockers closed.

### Wisp (ephemeral bead)
`Ephemeral=true`; excluded from federation sync; GC'd only when closed.

| Our name | bd `--wisp-type` | TTL class | Claimable |
|---|---|---|---|
| `[wisp:review] <node>: <dim>` | escalation | 7d | yes -- reviewer |
| `[wisp:escalation] <node>: <q>` | escalation | 7d | yes -- advisor/researcher |
| `[wisp:worklog] <node>` | gc_report | 24h | no |
| `[wisp:ledger] <event>` | gc_report | 24h | no (scribe closes) |
| `[wisp:patrol] sheepdog <repo>` | patrol | 24h | yes -- shepherd (lease) |
| probe chatter | ping/heartbeat | 6h | no |
| recovery | recovery | 7d | per protocol |

Burn rules: never while a dep edge targets it; review wisps only after merge
bead closes; worklog/escalation at node close; ledger at scribe drain.

### Rules file (per contract-holding agent)
`agent`, `kind?` · `completion[]` (check, require) · `authority`
(deny_states, deny_metadata, deny_labels?) · `escape` (state=failed + verb) ·
`pause[]` (valid non-terminal exits). Predicates: metadata-key-exists ·
label-match · comment-verb-exists · state-in-set · wisp-open/closed. Single
source for: hook evaluation, compile-generated definition prose.

### Domain bead
Specialist identity + standing brief. Child of run epic; nodes link
`relates-to`. Carries the domain BRIEF comment; never claimed by children.

### Gate
Native bd blocker. `human` (ASK/approval) · `timer` (scribe cycle) ·
`gh:run`/`gh:pr` (CI/PR waits; never on a merge bead). Resolved only by
`bd gate check` ticks (shepherd patrol, orchestrator wake) or manual resolve.

### Label
`agent:<role>` (routing) · `needs-review:<dim>` (add: planner/any T1; remove:
approving reviewer via swap, orchestrator via retrigger) · `reviewed:<dim>`.
Declarative only -- merge safety derives from the dep graph, never labels.

## State machine (node) -- DERIVED, not stored

bd has exactly five built-in statuses: `open`, `in_progress`, `blocked`,
`deferred`, `closed` (`--claim` sets `in_progress`). The design's richer
lifecycle phases are **not** custom statuses and are **not** mirrored into
metadata -- each is derived from the built-in status plus labels, gates, and
review-wisp closure (single source of truth per fact):

| Design phase | Derived from |
|---|---|
| pending | `status=open`, unclaimed |
| working | `status=in_progress` (claimed) |
| reported | `status=in_progress` + `agent:reviewer` label + REPORTED comment |
| in_review | `status=in_progress`, claimed by a reviewer |
| waiting_human | open **human gate** blocking the bead |
| changes_requested | review wisp **open** + `needs-review:<dim>` label |
| approved | all review wisps closed → merge bead ready (dep graph) |
| merged / dismissed | `status=closed` + reason |
| failed | `status=blocked` + FAILED comment (the escape hatch) |

Claim lifecycle: released at the reported point; fix rounds re-claim (queued
behind the specialist's current claim). BLOCKED is a wisp + pause; the
escape-hatch exit is `status=blocked` + a FAILED/BLOCKED comment.

## Actor ↔ bead authority matrix (summary)

| Actor | May write | Never |
|---|---|---|
| T0 orchestrator | create/close/dismiss beads, shells, gates, deps, BRIEF, label retrigger | claim anything |
| domain-specialist | claim-scope metadata, delivery fields, `agent:*` + `needs-review:*` add, REPORTED/CHECKPOINT/FAILED, merge-bead create + dep | close, approve, merge states; merge metadata |
| reviewer | verdict lines, wisp fill/close, label swap, `gh pr review`/`ready` | node code metadata, push, merge, `gh pr edit` |
| advisor | claimed wisp content plus promoted node summary | node state, delivery, or review mutation |
| researcher | `output_ref`, REPORTED, wisp answers plus promoted summary | push, merge, or approval state |
| scribe | epic run record, query/ledger-wisp close | work-node mutation |
| run shepherd | one run's PR state (`ready`→probe→merge), `merge_sha`/`pr`, merge-bead close, fix beads, sheepdog, run cleanup | PR content, push, `gh pr edit`, repository-global queue ownership |
| pr-shepherd | cross-run recovery and repository-global queue drain under the same landing safeguards | PR content, push, `gh pr edit`, a queue held by a live run shepherd |

Claim invariants: ≤1 durable claim per actor; wisps exempt; 0 claims of any
kind at exit; claim-holders spawned only by T0; children never claim.

## Link vocabulary

`relates-to` (node↔wisp, node↔domain) · `discovered-from` (follow-up work,
fix beads) · `caused-by` (bounce/recovery) · `supersedes` (re-planning) ·
`duplicates` (dedup) · `replies-to` (wisp threads; CLI support unverified --
fallback relates-to + chronological comments).
