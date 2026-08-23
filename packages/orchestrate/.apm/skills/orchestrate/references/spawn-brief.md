# Claim-holder activation

Task data lives on the claimed bead or wisp. A claim-holder's activation
message is exactly `CLAIM {bead-or-wisp-id}` or `CLAIM queue:{filter}`. It
carries none of:

- scope or commands
- role mechanics
- review items or questions

Spawn and activation are separate operations. Never spawn a claim-holder with
`CLAIM`. The Agent call carries only the WAIT bootstrap.

Bind the returned routing handle to the hook context from its WAIT
acknowledgment. Stamp both identities and read them back. Send CLAIM as a
separate message. Never repair an ordering failure with a combined WAIT plus
CLAIM.

## Build the bead brief first

Before allocating a runtime, write the complete machine envelope to metadata
and the narrative task to one `BRIEF` comment. Before you spawn, read both back.

The required node metadata:

- `scope`, `base_ref`, and `base_sha`
- `execution_task_kind`, `execution_kind`, and `artifacts_dir`
- `execution_dispatch`, `execution_agent`, and `complexity_tier`
- `actor`, the claim identity that `BEADS_ACTOR` carries
- `branch` and `worktree` for a Worktrunk-backed actor

Those keys are the orchestrator anchors in `scripts/rules-eval.py`. After the
claim, the orchestrator may re-stamp one. The claiming role may never rewrite
one. Set each as metadata with `bd update <id> --set-metadata key=value`, or
`--metadata '{json}'` for the whole envelope. None has a label form.

`artifacts_dir` is an absolute path under the primary checkout and outside every
Worktrunk checkout. Before spawning, create it and read the stamped value back.
Relative or checkout-contained paths are invalid.

`base_ref` names the ref that carries the target work, which commonly sits off
`main`. Stamping `main` for a defect that lives only on an unmerged branch forces
the node to merge that branch inside its own checkout. Any conflict it hits there
belongs to another node. The stamped node then resolves someone else's conflicts,
or escapes them by switching branches and stranding its own anchors. Before
stamping, confirm that the ref carries the target.

When this node needs an upstream node's code, stamp the upstream's branch as
`base_ref`. The upstream specialist pushes that code at REPORTED, so the
dependent starts there rather than waiting for the merge. See
`references/beads-store.md` for which dependency type each kind of wait takes.

Set `metadata.integration_owner=orchestrate` on every merge bead this run
creates, or the repository-global `pr-shepherd` may drain the run's PRs mid-flight.

## Preflight before every dispatch

Read each back rather than assuming the write landed.

1. `wt switch --create <branch>` used a BRANCH source, not a filesystem path.
   A filesystem path fails as `Branch <path> has no worktree`.
2. `base_ref` and `base_sha` name the ref that carries the target work.
3. `wt config state vars set bead <bead-id> --branch <branch>` landed: read it
   back with `wt -C <path> step eval '{{ vars.bead }}' --format json` and
   confirm that it matches the node id.
4. Node metadata carries every key required under "Build the bead brief first".
5. One `BRIEF` comment exists on the resource. `bd show --json` omits comments,
   so verify with plain `bd show`.
6. `scope-check.py` reports the candidate disjoint from every in-flight node.
7. The spawn prompt is one of the three bootstraps below, byte-exact, and carries
   no task text. Task data belongs on the resource.
8. `bind` returned `status=bound` before any `CLAIM` is sent.

The `BRIEF` comment carries:

- the objective
- its acceptance and verification checks
- the linked domain context

A review wisp holds its dimension in the wisp body. An escalation wisp holds its
question there. Each links to the affected node, and the activation message never
repeats this content.

## Worktrunk handshake

Every independently dispatched tool user gets a separate prepared checkout.
The orchestrator performs this sequence:

1. Create the checkout with plain Worktrunk: `wt switch --create <branch>`.
2. Stamp the unclaimed bead or wisp id on that branch with `wt config state
   vars set bead <bead-id> --branch <branch>`. Then stamp `branch`, canonical
   `worktree`, and `base_sha` on the bead as `metadata.worktree` and its
   siblings.
3. Spawn using only the resource bootstrap under "Worktrunk handshake". Send it
   with no leading whitespace: the anchored match rejects an indented copy.
4. Record the returned `runtime_handle`. The waiting actor's entire first
   response needs to be `WAIT context={runtime_context}`. Bind both values to
   the prepared path.
5. Stamp `runtime_handle` and `runtime_context` on the activation resource and
   read both values back.
6. Send exactly `CLAIM {bead-or-wisp-id}`.

The role definition owns:

- claim
- validation
- recovery
- reporting

Do not append commands or a protocol block to the release message. If any stamp
fails,
keep the actor waiting. Then reclaim the checkout and retry with a fresh runtime
identity.

The canonical WAIT text carries none of:

- a task or command
- a question or review dimension
- a protocol appendix

Activate only an existing unclaimed resource that carries its canonical worktree
stamp. Before writing, the worker cross-checks its claimed bead against
`wt -C <path> step eval '{{ vars.bead }}' --format json`.

A claim-holder gets the resource form.

```text
WAIT checkout={absolute-worktree}
RESOURCE {bead-or-wisp-id}
Do not invoke tools or start work.
The controlling parent will release you with exactly CLAIM {bead-or-wisp-id}.
```

A queue actor uses its prepared checkout.

```text
WAIT checkout={absolute-worktree}
QUEUE {filter}
Do not invoke tools or start work.
The controlling parent will release you with exactly CLAIM queue:{filter}.
```

An actor that receives its task by resume rather than by claiming a resource uses
the generic form, whose last line differs.

```text
WAIT checkout={absolute-worktree}
Do not invoke tools or start work.
The controlling parent will send your task after stamping your Worktrunk checkout.
```

Those three are the whole accepted set. `GENERIC_WAIT_RE`, `RESOURCE_WAIT_RE`,
and `QUEUE_WAIT_RE` match them byte-exact. Wording counts, and so do line breaks
and trailing full stops. Give an absolute checkout. A spawn
carrying a `RESOURCE` line promises a `CLAIM`, so the hook rejects the resource
form closed by the generic line. The hook denies everything else with
`tool-using agent spawn is not parent-prepared`, including a bootstrap that is
correct except for one reworded line.

Claude has no checkout `cwd` field. Its wait bootstrap preserves the absolute
path so every Bash call can start with `cd -- {absolute-worktree}`. Codex sets
the command workdir to that path. File tools use absolute paths in both
runtimes.

## Domain specialist

Activate a directed specialist with `CLAIM {node-bead-id}`. The specialist reads:

- the node metadata and `BRIEF`
- the linked domain bead
- the comments and worklog wisp

It derives its stable actor from `metadata.actor` and claims under that identity.
It reads `metadata.worktree` off the claimed bead and cross-checks that value
against `wt -C <path> step eval '{{ vars.bead }}' --format json`. A mismatched
bead id means another actor owns that tree, so it stops without writing. Once
that check passes, it starts repository work.

A fix or conflict wake uses the same activation. The specialist reads open
review or escalation wisps linked to its node. The parent pastes no FIX,
ADVICE, or CONFLICT content into the wake.

## Bounded implementation child

A domain specialist may delegate bounded work inside its existing checkout:

1. Spawn the child with the same wait bootstrap and no bead ID.
2. Bind the child's routing handle and acknowledged hook context to the
   specialist's existing path.
3. Send a bounded implementation brief limited to the specialist's scope.
4. Prohibit Beads claims, Worktrunk lifecycle commands, and any commit, push,
   or further write-capable delegation.
5. Collect the child before review, commit, or `REPORTED`.

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
doorbell only. It never relays their content.

## Scribe and shepherd

Activate a scribe drain with `CLAIM {query-wisp-id}`. The query wisp links to
the run epic and names the requested report or ledger drain.

Give the bundled run shepherd one dedicated Worktrunk checkout per repository.
Activate it only through a merge bead or supported queue claim. The merge bead and
GitHub hold PR identity, CI state, bounce evidence, and landing authority. The
activation carries no merge instructions. Use the standalone `pr-shepherd` only
for a repository-global drain, or for recovery when nobody holds the run-scoped
sheepdog.
