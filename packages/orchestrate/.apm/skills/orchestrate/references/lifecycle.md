# Lifecycle: states, dispatch, review, recovery, ambiguity, cleanup

Agent lifecycle and task-node state share one vocabulary, tracked on the
node's bead: `bd set-state <bead> state=<name> --reason "<why>"` plus bead
status per the mapping table in `references/beads-store.md`.

## State diagram

```
                 ┌────────── ASK (question) ──► waiting_human ──(answer)──┐
                 │                                                         ▼
pending ─ready─► working ─(BLOCKED wisp→advisor ADVICE)─► working ─► reported ─► in_review
   ▲ bd ready +                                                             │
   │ scope/route clean                          changes_requested ◄─────────┤ verdict=changes
   │                                                    │                   │ verdict=approve
   └──────────── deps closed + scope free ──────────────┘                   ▼
                                                                         approved
                                             git: APPROVE → shepherd   │ non-git: evidence accepted
                                    CONFLICT ─► working (rebase)          │
                                                 │                        ▼
                                                 └────────► merged ───► dismissed
                                            (any state) ───────────────► failed
```

Blocked workers keep the node in `working`. `BLOCKED` is written on an
escalation wisp, not stored as a node state.

## Transitions

| Transition | Trigger |
|---|---|
| `pending → ready` | `bd ready --label orc-node --parent <epic>` reports the node, no gate is open, scope is clean, and routing envelope is complete |
| `ready → working` | native task agent runs in the parent checkout with isolation off, claims under `metadata.actor`, then creates and records its linked Worktrunk checkout |
| `reported → in_review` | worker reports declared evidence; orchestrator creates every review-wisp shell and activates reviewers by wisp id |
| `working` (blocked) | worker writes `BLOCKED` on a linked escalation wisp and exits or continues independent work; an advisor claims and answers that wisp directly |
| `changes_requested → working` | same worker re-claims its node, reads all open review wisps, and applies the union of FIX items |
| `approved → merged` | the last approving reviewer closes the final review wisp and makes the draft PR ready; the run shepherd claims the unblocked merge bead, applies its safeguards, serializes on the merge slot, proves the final base, releases, and closes |
| `approved → dismissed` | non-git evidence only: orchestrator records accepted evidence, sets `state=dismissed`, closes, then dismisses worker and reviewer |
| `waiting_human` | agent raised `ASK`; orchestrator records the question and holds the node. A node not started also gets `bd gate create --type=human --blocks <bead>` |
| `waiting_gate` | only an external machine gate remains; orchestrator parks the node with the awaited identifier and resume instruction, never polls it, and exits when nothing else is ready |
| `failed` | unrecoverable; set `state:failed` plus status `blocked`, log the error, and surface it |

## Completion paths

The node's `execution_kind` selects the terminal path, not whether its
subject sounds technical.

| Evidence | Required completion proof | Terminal owner |
|---|---|---|
| `git` | pushed branch, commit SHAs, scoped verification, independent branch review | shepherd closes as `merged` |
| `artifact` | absolute `output_ref`, method, verification, independent evidence review | orchestrator closes as `dismissed` |
| `comment` | bead comment or audit-event ref, verification, independent evidence review | orchestrator closes as `dismissed` |
| `external` | resource identity, read-back or before/after evidence, verification, independent evidence review | orchestrator closes as `dismissed` |

Tracked documentation and configuration changes use `git`. Research, analysis,
read-only review, and external operations may use non-git evidence. Non-git
work follows the same claim, report, independent review, fix, approval, and
closure states. It never creates an empty commit, placeholder branch, or fake
merge requirement.

## Persistence classes

| Class | Agents | Rule |
|---|---|---|
| Run patrol | shepherd | one run and repository; restartable from Beads and GitHub |
| Global patrol | pr-shepherd | cross-run repository recovery and queue drain |
| Task-scoped | directed or generic worker; independent reviewer | activated by claim; resume is an optimization and respawn reads bead plus wisps |
| Ephemeral | Researcher gatherers/synthesizer, Advisor/debugger, Tiebreaker, Scribe | claim one node or wisp, report there, release, exit |

A `BOUNCE` comment invalidates that actor attempt. Repair the durable envelope and
redispatch a native task agent with isolation off. The replacement claims the
resource in the parent checkout, creates a fresh linked Worktrunk checkout with
`wt switch -y --create --no-cd --base <base> --format json omp/agent/<bead-id>`,
records its branch and absolute path on the bead, and resumes from durable state.
Do not continue the bounced handle or create a runtime binding.

## Resume after orchestrator compaction or crash

1. Find the run epic: `bd list --type epic --json` and match metadata `run_id`.
2. Read in-flight nodes with `bd list --label orc-node --parent {epic}
   --status in_progress --json`. Each recovery record carries exact actor in
   `assignee`, directed or generic mode in `execution_dispatch`, branch/worktree
   or non-git resource scope, and the fine-grained `state:` label.
   Confirm every recorded checkout through `wt list --format=json`. A recorded
   branch without a worktree is recovered by dispatching the replacement actor in
   the parent checkout; it claims the bead and recreates the linked checkout with
   `wt switch -y --create --no-cd --base <base> --format json omp/agent/<bead-id>`.
   Update the bead with the returned absolute path and branch.
3. Run `bd merge-slot check`. Never infer a dead holder from age or a recycled
   shepherd. Resume the landing transaction, or use evidence-gated recovery after
   proving the exact actor is dead.
4. Resume every live assignee from its claimed bead and recorded worktree. If its
   handle is dead, dispatch the same actor in the parent checkout; it claims the
   same resource and recreates its linked checkout. Never route an assigned bead
   to a generic queue. If an unassigned `in_progress` bead lacks its review
   handoff evidence, run dead-claim recovery before redispatch.
5. Restart each GitHub repository watcher with `--slots=1`. Replay every node
   whose current `queue_dispatch` or `queue_lifecycle` lacks its matching ack;
   pending or sent receipts identify the last completed delivery step. Only a
   matching ack suppresses replay. Normalize key-only migration records before
   SendMessage by stamping a pending receipt. Route records unmatched to the
   run once through standalone pr-shepherd. The run shepherd resumes
   acknowledged, approved, unmerged nodes from its startup scan; see
   `references/queue-watcher.md`.

## Dead-claim recovery

Age is a diagnostic, not proof of death. `bd stale --status in_progress` may
identify candidates, but there is no automatic lease expiry and no daemon is
required. Never steal a claim because a timestamp is old.

1. Read the bead, comments, audit trail, actor handle, branch/worktree or
   non-git resource scope, and last verification evidence.
2. Try to resume the actor. Clear ownership only when the platform reports the
   handle stopped or absent, the actor explicitly releases it, or the user
   confirms the session is dead. Record that evidence before mutation.
3. Preserve the worktree, pushed branch, artifacts, comments, and external
   resource references. Do not sweep them during recovery.
4. Record recovery with a bead comment and `orc.recover` audit event. Beads
   1.1.0 has no `bd unclaim`; release and reopen with:

```
bd update <bead> --assignee "" --status open
bd set-state <bead> state=pending --reason "dead claim verified; redispatch"
```

5. For directed recovery, dispatch the replacement actor in the parent checkout.
   It claims the bead and creates its linked Worktrunk checkout with the approved
   `wt switch -y --create --no-cd --base <base> --format json
   omp/agent/<bead-id>` command, then records the returned branch and absolute
   path. For generic recovery, restore one compatible `agent:<queue>` and leave
   the bead unassigned; the replacement claims atomically and creates its own
   checkout.

If holder death is uncertain, keep the assignment and record a revisit trigger.
That safe default prevents two workers from mutating the same scope.

## Failure propagation

- `failed` never satisfies a dependency. A failed node's bead is `blocked`,
  never `closed`, so dependents stay out of `bd ready`.
- `bd dep tree <bead>` shows every downstream node stranded by a failure. The
  orchestrator replans with a replacement node or abandons the subtree; it does
  not leave the graph silently stalled.

## Recycle runtime processes

Every process is restartable because Beads, wisps, GitHub, and pushed branches
are the source of truth.

- **Run shepherd:** restart from its run epic after the merge slot is released,
  never during a landing transaction.
- **Standalone pr-shepherd:** use only for repository-global recovery or queue
  drain when no live run shepherd owns the sheepdog.
- **Scribe:** one query wisp per drain or report; no persistent context.
- **Task workers:** resume while the handle is fresh; otherwise respawn the
  same actor on the same claim and recover from node plus worklog.

## Human-in-the-loop and safe autonomy

An agent may choose a default autonomously only when every condition is true:

- the action and its effects are reversible;
- the effect is local to one bead and its owned resources;
- the downside and rollback boundary are explicit and bounded;
- the choice is compatible with accepted policy and recorded evidence; and
- the choice preserves user intent rather than selecting or changing it.

Record the ambiguity before applying the default. A cross-boundary choice that
existing evidence fully resolves uses a decision bead. Cross-boundary
uncertainty, irreversible action, external mutation, security/financial/legal
risk, or missing user intent is not an autonomous default. It enters
`waiting_human` with one exact question and its impact.

The orchestrator adds this comment to the affected bead:

```text
WAITING_HUMAN
owner: <actor responsible for resumption>
scope: <bead and affected resource>
question: <one exact choice the human must make>
impact: <what remains stopped and what each answer changes>
resume: <exact state transition, gate action, and actor to wake>
```

Every field is nonempty. The question cannot delegate discovery back to the
human or ask for general approval. The orchestrator records `orc.ask`, runs
`bd set-state <bead> state=waiting_human --reason "<question summary>"`, and
keeps status `in_progress`. The resulting `state:waiting_human` label is the
durable hold. A node that had not started also receives
`bd gate create --type=human --blocks <bead> --reason "<question>"`.

The orchestrator does not poll the human or the held worker. It continues
unrelated nodes returned by `bd ready`. On an answer, it promotes any message
into a work-bead comment or decision bead, resolves the human gate when one
exists, and follows the stored `resume` instruction. A started node returns to
`state=working`, status `in_progress`, and the same agent. An unstarted node
returns to `state=pending`, status `open`, and normal dispatch.

## Waiting on an external machine gate

The same rule applies when the wait is on a machine rather than a person: a CI
run, a release workflow, a release PR's checks, a review bot's round, or a
long-running reviewer. The orchestrator does not poll it and does not hold the
session open for it.

Park the node instead. Record what is being awaited on the bead with
`bd set-state <bead> state=waiting_gate --reason "<what is awaited and how to
resume>"`, add `bd gate create --type=gh:run --blocks <bead> --await-id
<run-id>` for a workflow run or `--type=gh:pr --await-id <pr#>` for a PR merge
when the wait has an external identifier worth storing, then continue unrelated
nodes from `bd ready`. When nothing else is ready and only external waits remain,
write the run report and exit; the gate bead plus the next pass own the wait.

This is the rule `pr-shepherd` already states for itself -- never re-poll a
pending PR or stay alive as a watcher. Two campaign runs violated it on the final
release node: each polled a release workflow and a package-executing reviewer
until the stream aborted, leaving that node `in_progress` even though every PR,
tag and release had already landed correctly. A run whose only remaining work is
an external wait must terminate with a clean record, not an aborted stream.

## Reversible local defaults

Before applying a reversible bead-local default, write a provisional
`LOCAL_DECISION` comment using the contract in `references/beads-store.md`.
Its objective `revisit` trigger defines when the default becomes stale.

A choice affecting another bead, agent, package, shared contract, ordering
rule, or later work uses a decision bead instead. Product intent, unsafe
effects, and unresolved cross-boundary choices enter `waiting_human`.

## Revisit, conflict, and late evidence

At the recorded trigger, the owner re-reads the cited evidence before any
further use of the default. The owner supersedes the provisional comment with
an accepted `LOCAL_DECISION`, creates a decision bead, or enters
`waiting_human`. Routing changes only while the bead is unassigned.

A local choice that changes gets a new comment referencing the old comment; no
comment is edited or erased. A cross-boundary change gets a replacement
decision bead and explicit supersession. Duplicate, conflicting, superseded,
and partially linked decisions follow the deterministic rules in
`references/decisions.md`; chronology alone never selects policy.

Restart recovery reads work-bead comments, decision beads, their dispositions
and links, and `state:waiting_human` before resuming any agent. Message wisps
and artifacts supply coordination/evidence only. An unpromoted material
message is not replay authority.

Late evidence follows the same revisit flow. If the affected bead is closed,
append the evidence and disposition to that closed bead or its decision bead.
When behavior must change, create follow-up work with a `discovered-from` link;
do not reopen the completed bead or rewrite its terminal evidence.

## Worktree and cleanup

Sweep after fan-in, per the global Worktrunk rule:

- Registered checkouts are inspected with `wt list` and removed with
  `wt remove` through `worktree-sweep.sh`; raw `git worktree` lifecycle
  commands are prohibited.
- Reviewer/advisor/debugger branches are disposable and use
  `worktree-sweep.sh --discard-branch <path>` after their actor is dismissed.
- A broken, unregistered harness directory is moved out of the
  harness root into quarantine. Unknown or dirty paths are refused.
- The dirty primary checkout, artifacts directory, Beads database, and the
  repository-shared build target are never swept.
- At run end, after all known role checkouts are dismissed or reclaimed, run
  `worktree-sweep.sh --prune <primary-repo-path>`. Exit 1 means at least one
  dirty, valid-but-unregistered, unknown, or symlink path was refused; inspect
  those paths and keep the run open instead of forcing deletion.

Stop repository watchers before removing run-local process state. Non-git
nodes have no worktree to sweep. This cleanup contract and the per-repository
build target address the disk/orphan failure recorded in bead
`astro-plan-ki35`.
