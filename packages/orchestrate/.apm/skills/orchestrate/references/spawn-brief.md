# Claim-holder activation

Task data lives on the claimed bead or wisp. The activation names the durable
resource; it does not carry a second brief, runtime protocol, or checkout path.
A task agent runs in the parent checkout with isolation off.

## Build the bead brief first

Before dispatch, write the machine envelope to metadata and the narrative task to
one `BRIEF` comment. Read both back before dispatch.

Required node metadata:

- `scope`, `base_ref`, `base_sha`, `execution_task_kind`, `execution_kind`, and
  `artifacts_dir`
- `execution_dispatch`, `execution_agent`, and `complexity_tier`

`artifacts_dir` is an absolute path under the primary checkout and outside every
Worktrunk checkout. Create it and read the stamped value back before dispatch.
Relative or checkout-contained paths are invalid.

`base_ref` and `base_sha` identify the ref that actually carries the target work.
Do not substitute `main` when the target lives on another branch.

Set `metadata.integration_owner=orchestrate` on every merge bead this run
creates, or the repository-global shepherd may drain the run's PRs.

## Claim, then create the linked Worktrunk checkout

A directed activation names the node or wisp id. A queue activation names its
admitted queue. The task agent starts in the parent checkout and claims before it
creates a worktree:

```text
BEADS_ACTOR="$ACTOR" BD_ACTOR="$ACTOR" bd update <bead-or-wisp-id> --claim
```

For a queue actor, atomically claim one compatible ready bead and accept the
returned bead; never list candidates and cherry-pick one. An empty result writes
`NO_WORK` on the run epic and changes no node.

After a successful claim, create the linked checkout from the recorded base:

```text
wt switch -y --create --no-cd --base <base> --format json omp/agent/<bead-id>
```

Read the JSON result, record its absolute path and branch on the claimed bead,
and continue work from that path using absolute file paths. The agent may run
`wt step copy-ignored` in the new worktree when the repository requires copied
gitignored dependencies. Do not pre-create the checkout, pre-assign the actor,
bind a runtime, or stamp an activation resource before dispatch.

The claim is the ownership lock. If claim or checkout creation fails, leave the
bead's durable state and report the failure; do not guess a path or reuse another
actor's worktree.

## Validate before editing

1. Re-read the claimed bead, its `BRIEF`, comments, links, and scope metadata.
2. Confirm the Worktrunk JSON returned the requested `omp/agent/<bead-id>` branch
   and an absolute path.
3. Record `metadata.branch` and `metadata.worktree` on the claimed bead and read
   them back.
4. Confirm the path is clean and writable before editing.
5. Work only inside the stamped scope. A needed file outside scope becomes a
   discovered bead or an escalation, not an expansion of this claim.

A reviewer or advisor uses the same claim-then-linked-worktree sequence when it
needs a checkout. A read-only actor that needs no repository files does not create
one.

## Domain specialist

The specialist reads the node metadata, `BRIEF`, linked domain bead, comments,
and worklog after claiming. A fix or conflict wake reclaims the same durable node,
reads its open review or escalation wisps, and resumes from the recorded branch.
The parent does not paste FIX, ADVICE, or CONFLICT content into the activation.

## Bounded implementation child

A domain specialist may delegate bounded implementation inside its existing linked
checkout. The child receives a bounded implementation brief and never claims,
creates worktrees, commits, pushes, or delegates another writer. The specialist
reviews the child edits before reporting.

## Reviewer, advisor, and researcher

- Reviewer: create and link the review-wisp shell, then activate it by id. If the
  reviewer needs repository files, it claims the wisp and creates its own linked
  checkout from the exact writer base.
- Advisor or bounded-question researcher: put the question on an escalation wisp,
  activate it by id, and create a linked checkout only when tools require it.
- Artifact researcher: create a normal research node with its output boundary,
  then claim it and create a linked checkout only when repository files are needed.

These actors communicate findings through their claimed wisps and promote
material outcomes to the linked node. The orchestrator supplies only the durable
resource id and never relays their content.

## Scribe and shepherd

Activate a scribe drain by its query-wisp id. It claims the wisp and creates a
linked checkout only if its report needs repository files.

The bundled run shepherd claims its merge bead or supported queue claim and uses
the same linked-worktree flow when it needs an integration checkout. PR identity,
CI state, bounce evidence, and landing authority remain on the merge bead and
GitHub; activation carries no merge instructions.
