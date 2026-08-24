# Claim-holder activation

Task data lives on the claimed bead or wisp. A claim-holder's activation
message is exactly `CLAIM {bead-or-wisp-id}` or `CLAIM queue:{filter}`. Do not
put scope, commands, role mechanics, review items, or questions in that
message.

Spawn the claim-holder with that `CLAIM` message as its whole prompt. There is
no separate bootstrap and no acknowledgement to wait for: the bead already
carries the task, the scope and the checkout, so a runtime has nothing to report
back before it can start. Provisioning happens BEFORE the spawn -- stamp
`branch` and the absolute `worktree` on the bead first, because that is where
the agent reads its checkout from.

Write authority comes from holding the claim. The claim-holder takes it with
`bd update {bead-or-wisp-id} --claim`, which sets the assignee.

## Target state: self-discovery replaces the CLAIM grammar

Everything else on this page describes the grammar as it runs today. The
`orchestrator-activation-guard.py` regexes and validators are live, so a
malformed WAIT or CLAIM is still rejected. Do not treat the following as
current behavior.

The target is that an architect is not told its domain; it finds one. This
filter selects unclaimed architect domains and nothing else:

```text
bd ready -t epic --has-metadata-key worktree \
  --metadata-field role=architect --unassigned --json
```

Adding `--claim` makes taking one atomic and first-wins, which is what lets two
architects race safely: a second `--claim` on the same bead fails with `issue
already claimed by <actor>`.

All four predicates carry weight. Dropping `-t epic` admits ordinary tasks that
carry `role=architect`; dropping `--has-metadata-key worktree` admits the run
epic, which is `role=architect` but is nobody's domain. A filter that returns a
task where a domain was expected would have the architect decompose a leaf.

`bd ready` excludes a bead whose ancestor has an open `blocks` dependency, so a
domain under a not-yet-unblocked phase epic is invisible to this filter even
when the domain itself is unblocked. A phase-scoped run must either clear the
phase's blockers or pre-assign.

Directed dispatch survives as pre-assignment: `bd update <bead> --assignee
<actor>` is atomic in one update and makes the bead invisible to other actors'
`--claim`. Self-discovery is the default; pre-assignment is the explicit order.

Under self-discovery the spawn prompt carries nothing at all: the agent claims
its own domain, reads `metadata.worktree` off it, cross-checks the worktree var,
and starts. That removes the last thing the parent has to say, which is what
retires the "the prompt is the channel" assumption behind both the WAIT
grammars and the CLAIM regexes.

## Build the bead brief first

Before allocating a runtime, write the complete machine envelope to metadata
and the narrative task to one `BRIEF` comment. Read both back before spawning.

Required node metadata:

- `scope`, `base_ref`, `base_sha`, `execution_task_kind`, `execution_kind`,
  and `artifacts_dir`
- `execution_dispatch`, `execution_agent`, and `complexity_tier`
- `branch` and absolute `worktree` for a Worktrunk-backed actor

`artifacts_dir` is an absolute path under the primary checkout and outside
every Worktrunk checkout. Create it and read the stamped value back before
spawning. Relative or checkout-contained paths are invalid.

`base_ref` is the ref where the target work ACTUALLY lives, which is often not
`main`. Stamping `main` for a defect that exists only on an unmerged branch
forces the node to merge that branch inside its own checkout, and any conflict it
hits there belongs to another node. That is how a node ends up either resolving
someone else's conflicts or switching branches to escape them, which strands its
own branch/worktree anchors. Confirm the ref carries the target before stamping.

Set `metadata.integration_owner=orchestrate` on every merge bead this run
creates, or the repository-global `pr-shepherd` may drain the run's PRs mid-flight.

## Preflight before every dispatch

Read each back rather than assuming the write landed.

1. `wt switch --create <branch>` used a BRANCH source, not a filesystem path.
   A filesystem path fails as `Branch <path> has no worktree`.
2. `base_ref` and `base_sha` name the ref that carries the target work.
3. `wt config state vars set bead <bead-id> --branch <branch>` landed: read it
   back with `wt -C <path> step eval '{{ vars.bead }}' --format json` and
   confirm it matches the node id.
4. Node metadata has all of `scope`, `base_ref`, `base_sha`,
   `execution_task_kind`, `execution_kind`, `artifacts_dir`,
   `execution_dispatch`, `execution_agent`, `complexity_tier`, `branch`, and
   `worktree`.
5. One `BRIEF` comment exists on the resource. `bd show --json` omits comments,
   so verify with plain `bd show`.
6. `scope-check.py` reports the candidate disjoint from every in-flight node.
7. The spawn prompt is one of the three bootstraps below, byte-exact, and carries
   no task text. Task data belongs on the resource.

The `BRIEF` comment carries the objective, acceptance checks, verification
method, dependencies, skill hints, and linked domain context. Review and
escalation wisps carry their question or review dimension in the wisp body and
link to the affected node. The activation message never repeats this content.

## Worktrunk checkout preparation

Every independently dispatched tool user gets a separate prepared checkout.
The orchestrator performs this sequence:

1. Create the checkout with plain Worktrunk: `wt switch --create <branch>`.
2. Stamp the unclaimed bead or wisp id on that branch with `wt config state
   vars set bead <bead-id> --branch <branch>`, then stamp `branch`, canonical
   `worktree`, and `base_sha` on the bead as `metadata.worktree` and its
   siblings. Stamp `worktree` as an absolute path. The SubagentStop hook matches
   the agent's `cwd` against that value, and a relative path leaves the resource
   unresolvable.
3. Spawn using only the resource bootstrap shown below. Send it with no leading
   whitespace: the match is anchored, so an indented copy is rejected.
4. Send exactly `CLAIM {bead-or-wisp-id}` as a separate message.

The role definition owns claim, validation, recovery, and reporting behavior.
Do not append commands or a protocol block to the release message. If any
stamp fails, keep the actor waiting, reclaim the checkout, and retry with a
fresh runtime.

The activation message carries no task, command, question, review item, or
protocol appendix. The activation resource must exist and remain unclaimed. Its
canonical worktree must already be stamped on that resource, and the worker
cross-checks its claimed bead against `wt -C <path> step eval
'{{ vars.bead }}' --format json` before writing. Those two facts -- a stamped
`metadata.worktree` and a matching `vars.bead` -- are what make the checkout
safe to write in; nothing is negotiated at spawn time.

Claude has no checkout `cwd` field, so every Bash call starts with
`cd -- {absolute-worktree}`, read off the bead. Codex sets the command workdir to
that path. File tools use absolute paths in both runtimes.

## Domain specialist

Activate a directed specialist with `CLAIM {node-bead-id}`. The specialist
reads the node metadata, `BRIEF`, linked domain bead, comments, and worklog
wisp. It claims the node, reads `metadata.worktree` off the claimed bead, and
cross-checks it against `wt -C <path> step eval '{{ vars.bead }}' --format
json`: a mismatched bead id means another actor owns that tree, and it stops
without writing. Only then does it start repository work.

A fix or conflict wake uses the same activation. The specialist reads open
review or escalation wisps linked to its node; the parent does not paste FIX,
ADVICE, or CONFLICT content into the wake.

## Bounded implementation child

A domain specialist may delegate bounded implementation inside its existing
checkout:

1. Spawn the child with the same wait bootstrap and no bead ID, naming the
   specialist's existing checkout.
2. Send a bounded implementation brief limited to the specialist's scope.
3. Prohibit Beads claims, Worktrunk lifecycle commands, commits, pushes, and
   further write-capable delegation.
4. Collect the child before review, commit, or `REPORTED`.

The child is not a claim-holder, so bead-as-brief activation does not apply to
its one-shot implementation prompt. The specialist remains the only lifecycle
owner and reviews every child edit.

## Reviewer, advisor, and researcher

- Reviewer: create and link every review-wisp shell before dispatch. Prepare a
  read-only checkout from the exact writer branch, stamp the wisp, then send
  `CLAIM {review-wisp-id}`.
- Advisor or bounded-question researcher: put the question on an escalation
  wisp linked to the node, prepare and stamp its checkout, then send
  `CLAIM {escalation-wisp-id}`.
- Artifact-producing researcher: create a normal research node with
  `execution_kind=artifact`, a complete `BRIEF`, and its output boundary, then
  send `CLAIM {research-node-id}`.

These actors communicate findings directly through their claimed wisps and
promote material outcomes to the linked node. The orchestrator supplies a
doorbell only; it never relays their content.

## Scribe and shepherd

Activate a scribe drain with `CLAIM {query-wisp-id}`. The query wisp links to
the run epic and names the requested report or ledger drain.

Give the bundled run shepherd one dedicated integration Worktrunk checkout per
repository. Activate it only through a merge bead or supported queue claim.
PR identity, CI state, bounce evidence, and landing authority remain on the
merge bead and GitHub; the activation carries no merge instructions. The
standalone `pr-shepherd` is reserved for repository-global drain or recovery
when the run-scoped sheepdog is not held.
