# Planning and pluggable frameworks

You (the orchestrator) always own the **high-level** plan. How the work is
decomposed into executable units is **pluggable**: use an external framework when
the project already has one, otherwise build the default runtime DAG.

Owning the plan means owning the **decisions and the graph**, not doing the deep
reading yourself. Push codebase exploration and any large planning pass to
read-only agents (`Explore`, `Plan`) and keep only their conclusions — the
orchestrator stays lean so its context lasts the whole run.

## Decide the planning system

- **External framework in play (SpecKit or similar):** be aware of it and delegate
  the actual **speccing** to its agents (`speckit-research`, `speckit-implement-task`,
  the `speckit-*` verify/sync agents). Use *that* system's graph/tasks as the unit
  of work and **skip the default decomposition below**. A beads-managed SpecKit
  molecule (`bd swarm create <epic>`) already IS a dependency-aware run DAG —
  label its step beads `orc-node` and add `scope` metadata rather than building
  a second graph on top (`references/beads-store.md`). Questions the spec agents
  raise during speccing/grilling bubble to you as `ASK` and then to the user.
- **No framework:** build the default runtime DAG as node beads under the run
  epic (below).
- **Work spanning >3 tasks with cross-cutting deps, or an unfamiliar subsystem:**
  delegate a deep planning pass to the read-only `Plan` agent before committing
  the decomposition; you still own the final graph.

## Default DAG decomposition

The DAG is per-project and runtime-mutable — you add nodes/edges and agents update
state live. It is NOT a static authored graph.

1. Split the work into tasks small enough for one worker. Give every task a
   disjoint `scope`: tracked-file globs for git work, or canonical artifact and
   resource prefixes for non-git work. Serialize overlapping scopes with a
   dependency.
2. One child bead per task under the run epic: `bd create "<id>: <desc>"
   --parent <epic> --labels orc-node --metadata '<routing-envelope>'`.
3. Encode dependencies: `bd dep add <dependent> <dependency>` — the dependency
   must close before the dependent becomes ready. `bd dep cycles` must stay
   clean (bd also rejects cycle-creating edges at add time).
4. Drive execution off `bd ready --label orc-node --parent <epic> --json`.
   Run `scope-check.py --candidate <bead> --epic <epic>` for every node. Scope
   conflict → leave unclaimed and add a dependency to serialize.

## Routing envelope

Write the route before dispatch so recovery never has to infer it from prose.

| Field | Value |
|---|---|
| `scope` metadata | owned tracked-file globs or canonical non-git resource prefixes; never empty |
| `execution_kind` metadata | stable task kind such as `code`, `docs`, `research`, `review`, or `operations` |
| `execution_capabilities` metadata | JSON list of required capability slugs |
| `cap:<slug>` labels | one label per required capability; mirrors the metadata for queue admission |
| `execution_evidence` metadata | `git`, `artifact`, `comment`, or `external` |
| `execution_agent` metadata | selected agent type when directed; absent before generic pull |
| `execution_dispatch` metadata | `explicit`, `specialist`, or `generic` |
| `agent:<queue>` label | compatible generic queue; absent from directed work |

`execution_evidence=git` means tracked files change, even when the task is
documentation or configuration. It requires a worktree, commit, push, and
gatekeeper integration. Other evidence modes require an `output_ref` or
verifiable external-state reference and never require an empty commit.

## Dispatch ready work

Apply one route only, in this order:

1. **Explicit actor:** a bead with an assignee goes only to that actor. Confirm
   its declared task kinds, capabilities, access, and scope are compatible,
   then send the bead-specific brief. An incompatible explicit assignment
   remains pinned and unclaimed. Automatic correction may update only
   evidence-backed routing-envelope fields; it never changes the assignee. An
   actor change requires explicit release/requeue or coordinator/human
   reassignment under the handoff and dead-claim recovery contracts.
2. **Specialist:** for an unassigned bead, choose the narrowest catalogued
   specialist whose task kinds and capabilities cover the routing envelope.
   Set its actor as assignee before sending the brief.
3. **Generic pull:** use only when no compatible specialist is selected. Admit
   the bead to one `agent:<queue>` whose declared task kinds and capabilities
   cover every requirement. Leave it unassigned.

A generic worker claims the first ready bead in its admitted queue atomically:

```
bd ready --parent <epic> --label orc-node --label agent:<queue> \
  --metadata-field execution_kind=<kind> --unassigned --sort priority \
  --claim --json
```

The worker accepts the bead returned by `--claim`; it never lists candidates
and cherry-picks one. Spawn or wake a pull worker only for queues with observed
ready work. One activation owns at most one node and cannot claim another until
the first node is terminal. An empty result after a claim race changes no bead.

Pull is command-on-wake and requires only Beads 1.1.0 plus the agent harness;
it does not require Gas Town, a lease service, a poll loop, or a daemon.

The coordinator removes or changes `agent:<queue>` only while the bead is
unassigned. A capability mismatch discovered after claim is a routing defect:
the worker does no task work, records the mismatch, and sends `BLOCKED
kind:design` so the coordinator can repair the route.

## Merge order is not encoded

Do not encode merge order in the graph — you cannot predict which coders finish
when. Approved branches integrate under the exclusive merge slot
(`bd merge-slot acquire` without `--wait`); a held slot is advisory, so report
the holder, defer, and retry. Order follows successful acquisition, not a queue
or FIFO guarantee. Integrations remain conflict-guarded
by the gatekeeper (`conflict-probe.sh`). The graph expresses *dependencies* (what
must happen before what), not *integration sequence*.

For GitHub-backed runs, `release-queue-watch` priority affects which eligible
PR readiness hint arrives first. It does not rewrite the DAG or reserve the
merge slot. The orchestrator admits only an exact existing approved node, and
the gatekeeper's slot waiters remain the integration order after admission.

## Scope hygiene

Good scopes are the single most important planning decision:
- Prefer directory-level ownership (`src/auth/**`) over scattering one node across
  many trees.
- If two tasks must touch the same file, they are not concurrent — give one a
  dependency on the other (`bd dep add`) so the ready front serializes them.
- Shared contracts/interfaces that several nodes depend on should be their own
  early node that the others depend on.
- Artifact-only and external-state scopes use stable prefixes such as
  `artifact:/abs/path` or `external:<system>/<resource>` so overlap is checked
  the same way as file ownership.

## Concurrency cap

Cap concurrent state-changing workers at `min(16, cores − 2)`, and lower
further if disk is tight. Every git-backed worker carries its own build
artifacts. Queue workers that have not claimed a bead do not count as useful
parallelism; do not keep idle pollers running.
