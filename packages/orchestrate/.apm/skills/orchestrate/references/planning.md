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
  of work and **skip the built-in DAG**. Questions the spec agents raise during
  speccing/grilling bubble to you as `ASK` and then to the user.
- **No framework:** build the default runtime DAG with `graph.py` (below).
- **Work spanning >3 tasks with cross-cutting deps, or an unfamiliar subsystem:**
  delegate a deep planning pass to the read-only `Plan` agent before committing
  the decomposition; you still own the final graph.

## Default DAG decomposition

The DAG is per-project and runtime-mutable — you add nodes/edges and agents update
state live. It is NOT a static authored graph.

1. Split the work into tasks small enough for one coder, each with a **disjoint
   file scope** (glob set). Disjoint scope is the mechanism that lets coders run in
   parallel worktrees without colliding — the `ready` command enforces it.
2. Encode dependencies as edges (`--dep`/`add-edge`): `<from>` must finish before
   `<to>`. Keep the graph acyclic.
3. `graph.py … validate` — rejects cycles, dangling deps, and scope overlap between
   nodes that could run concurrently (no dep path between them). Fix overlaps by
   either narrowing scopes or adding a dependency edge to serialize them.
4. Drive execution off `graph.py … ready`: it returns nodes whose deps are cleared
   and whose scope is free of anything in flight. Spawn a coder per ready node.

## Merge order is not planned

Do not encode merge order in the graph — you cannot predict which coders finish
when. Approved branches integrate **first-come-first-served**, conflict-guarded by
the gatekeeper (`conflict-probe.sh`). The graph expresses *dependencies* (what must
happen before what), not *integration sequence*.

## Scope hygiene

Good scopes are the single most important planning decision:
- Prefer directory-level ownership (`src/auth/**`) over scattering one node across
  many trees.
- If two tasks must touch the same file, they are not concurrent — give one a
  dependency on the other so `ready`/`validate` serialize them.
- Shared contracts/interfaces that several nodes depend on should be their own
  early node that the others depend on.

## Concurrency cap

Cap concurrent coders at `min(16, cores − 2)`, and lower further if disk is
tight — each worktree carries its own copy of build artifacts.
