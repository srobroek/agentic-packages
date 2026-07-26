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
3. Spawn using only this bootstrap:

   ```text
   WAIT checkout={absolute-worktree}
   RESOURCE {bead-or-wisp-id}
   Do not invoke tools or start work.
   The controlling parent will release you with exactly CLAIM {bead-or-wisp-id}.
   ```

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

A queue actor uses its prepared checkout:

```text
WAIT checkout={absolute-worktree}
QUEUE {filter}
Do not invoke tools or start work.
The controlling parent will release you with exactly CLAIM queue:{filter}.
```

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
