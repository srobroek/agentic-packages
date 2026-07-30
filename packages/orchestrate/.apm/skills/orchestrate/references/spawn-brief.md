# Claim-holder activation

Task data lives on the claimed bead or wisp. A claim-holder's activation
message is exactly `CLAIM {bead-or-wisp-id}` or `CLAIM queue:{filter}`. Do not
put scope, commands, role mechanics, review items, or questions in that
message.

Spawn and activation are separate operations. Never spawn a claim-holder with
`CLAIM`; the Agent call carries only the WAIT bootstrap. Bind the returned
routing handle to the hook context from its WAIT acknowledgement, stamp and
read back both identities, then send CLAIM as a separate message. Never repair
an ordering failure with a combined WAIT plus CLAIM.

## Build the bead brief first

Before allocating a runtime, write the complete machine envelope to metadata
and the narrative task to one `BRIEF` comment. Read both back before spawning.

Required node metadata:

- `scope`, `base_ref`, `base_sha`, `execution_task_kind`, `execution_kind`,
  and `artifacts_dir`
- `execution_dispatch`, `execution_agent`, and `complexity_tier`
- `actor`, the stable claim identity used by `BEADS_ACTOR`
- `branch`, `worktree`, and `lease_token` for a Worktrunk-backed actor

`artifacts_dir` is an absolute path under the primary checkout and outside
every Worktrunk checkout. Create it and read the stamped value back before
spawning. Relative or checkout-contained paths are invalid.

`base_ref` is the ref where the target work ACTUALLY lives, which is often not
`main`. Stamping `main` for a defect that exists only on an unmerged branch
forces the node to merge that branch inside its own checkout, and any conflict it
hits there belongs to another node. That is how a node ends up either resolving
someone else's conflicts or switching branches to escape them, which strands its
own lease anchors. Confirm the ref carries the target before stamping.

Set `metadata.integration_owner=orchestrate` on every merge bead this run
creates, or the repository-global `pr-shepherd` may drain the run's PRs mid-flight.

## Preflight before every dispatch

Read each back rather than assuming the write landed.

1. `prepare` returned `status=ready`, and `--source` was a BRANCH name. A
   filesystem path fails as `Branch <path> has no worktree`.
2. `base_ref` and `base_sha` name the ref that carries the target work.
3. Node metadata has all of `scope`, `base_ref`, `base_sha`,
   `execution_task_kind`, `execution_kind`, `artifacts_dir`,
   `execution_dispatch`, `execution_agent`, `complexity_tier`, `actor`, `branch`,
   `worktree`, and `lease_token`.
4. One `BRIEF` comment exists on the resource. `bd show --json` omits comments,
   so verify with plain `bd show`.
5. `scope-check.py` reports the candidate disjoint from every in-flight node.
6. The spawn prompt is one of the three bootstraps below, byte-exact, and carries
   no task text. Task data belongs on the resource.
7. `bind` returned `status=bound` before any `CLAIM` is sent.

The `BRIEF` comment carries the objective, acceptance checks, verification
method, dependencies, skill hints, and linked domain context. Review and
escalation wisps carry their question or review dimension in the wisp body and
link to the affected node. The activation message never repeats this content.

## Worktrunk handshake

Every independently dispatched tool user gets a separate prepared checkout.
The orchestrator performs this sequence:

1. Run `worktrunk-writer prepare` without `--bead`.
2. Stamp its exact `branch`, canonical `worktree`, `base_sha`, `actor`, and
   `lease_token` on the unclaimed bead or wisp.
3. Spawn using only the resource bootstrap shown below. Send it with no leading
   whitespace: the match is anchored, so an indented copy is rejected.

4. Record the returned `runtime_handle` and require the waiting actor's entire
   first response to be `WAIT context={runtime_context}`. Bind both values to
   the prepared path, actor, and lease without `--bead`.
5. Stamp `runtime_handle` and `runtime_context` on the activation resource and
   read both values back.
6. Send exactly `CLAIM {bead-or-wisp-id}`.

The role definition owns claim, validation, recovery, and reporting behavior.
Do not append commands or a protocol block to the release message. If any
stamp or bind fails, keep the actor waiting, reclaim the prepared checkout,
and retry with a fresh runtime identity.

The canonical WAIT text carries no task, command, question, review item, or
protocol appendix. The activation resource must exist and remain unclaimed.
Its canonical worktree and lease must already be stamped on that resource.

A claim-holder gets the resource form:

```text
WAIT checkout={absolute-worktree}
RESOURCE {bead-or-wisp-id}
Do not invoke tools or start work.
The controlling parent will release you with exactly CLAIM {bead-or-wisp-id}.
```

A queue actor uses its prepared checkout:

```text
WAIT checkout={absolute-worktree}
QUEUE {filter}
Do not invoke tools or start work.
The controlling parent will release you with exactly CLAIM queue:{filter}.
```

An actor that receives its task by resume rather than by claiming a resource uses
the generic form, whose last line differs:

```text
WAIT checkout={absolute-worktree}
Do not invoke tools or start work.
The controlling parent will send your task after binding your Worktrunk lease.
```

Those three are the whole accepted set, matched byte-exact against
`GENERIC_WAIT_RE`, `RESOURCE_WAIT_RE`, and `QUEUE_WAIT_RE`. Wording, line breaks,
and trailing full stops all count, and the checkout must be absolute. A spawn
carrying a `RESOURCE` line promises a `CLAIM`, so mixing the resource form with
the generic closing line is rejected. Everything else is denied with
`tool-using agent spawn is not parent-prepared`, including a bootstrap that is
correct except for one reworded line.

Claude has no checkout `cwd` field. Its wait bootstrap preserves the absolute
path so every Bash call can start with `cd -- {absolute-worktree}`. Codex sets
the command workdir to that path. File tools use absolute paths in both
runtimes.

## Domain specialist

Activate a directed specialist with `CLAIM {node-bead-id}`. The specialist
reads the node metadata, `BRIEF`, linked domain bead, comments, and worklog
wisp. It derives its stable actor from `metadata.actor`, claims under that
identity, validates the prepared lease, and only then starts repository work.

A fix or conflict wake uses the same activation. The specialist reads open
review or escalation wisps linked to its node; the parent does not paste FIX,
ADVICE, or CONFLICT content into the wake.

## Bounded implementation child

A domain specialist may delegate bounded implementation inside its existing
checkout:

1. Spawn the child with the same wait bootstrap and no bead ID.
2. Bind the child's routing handle and acknowledged hook context to the
   specialist's existing path, actor, and lease without `--bead`.
3. Send a bounded implementation brief limited to the specialist's scope.
4. Prohibit Beads claims, Worktrunk lifecycle commands, commits, pushes, and
   further write-capable delegation.
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
