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

1. Split the work into tasks small enough for one coder, each with a **disjoint
   file scope** (glob set). Disjoint scope is the mechanism that lets coders run in
   parallel worktrees without colliding — `scope-check.py` enforces it at claim
   time.
2. One child bead per task under the run epic: `bd create "<id>: <desc>"
   --parent <epic> --labels orc-node --metadata '{"node":"<id>","scope":[…]}'`.
3. Encode dependencies: `bd dep add <dependent> <dependency>` — the dependency
   must close before the dependent becomes ready. `bd dep cycles` must stay
   clean (bd also rejects cycle-creating edges at add time).
4. Drive execution off `bd ready --label orc-node --parent <epic> --json`,
   filtered per candidate through `scope-check.py --candidate <bead> --epic
   <epic>`. Spawn a coder per ready, scope-clean node; the coder claims it
   atomically. Scope conflict → leave unclaimed, pick another (or add a dep
   edge to serialize).

## Merge order is not encoded

Do not encode merge order in the graph — you cannot predict which coders finish
when. Approved branches integrate **first-come-first-served** under the exclusive
merge slot (`bd merge-slot acquire`; waiters queue = FCFS order), conflict-guarded
by the gatekeeper (`conflict-probe.sh`). The graph expresses *dependencies* (what
must happen before what), not *integration sequence*.

## Scope hygiene

Good scopes are the single most important planning decision:
- Prefer directory-level ownership (`src/auth/**`) over scattering one node across
  many trees.
- If two tasks must touch the same file, they are not concurrent — give one a
  dependency on the other (`bd dep add`) so the ready front serializes them.
- Shared contracts/interfaces that several nodes depend on should be their own
  early node that the others depend on.

## Concurrency cap

Cap concurrent coders at `min(16, cores − 2)`, and lower further if disk is
tight — each worktree carries its own copy of build artifacts.
