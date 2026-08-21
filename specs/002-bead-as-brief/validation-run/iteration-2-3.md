# Validation Run -- Iterations 2 & 3

Iteration 2: integration node (N3 assembler, depends on N1+N2).
Iteration 3: exercise the mechanisms iteration 1 didn't -- wisps, graph-link
verdict aggregation, gates, ledger burn.

## Iteration 2 -- N3 CLI assembler (inter-generation handoff)

- **WORKS.** Spawned with `CLAIM starforge-run-2nw.3`. The specialist read
  its BRIEF, then **read the two dependency files N1/N2 left on disk** to
  discover their APIs (`render_starfield`, `name_constellation`), and
  assembled `starforge.py`. This is the bead-as-brief inter-generation
  handoff: N3 was a fresh agent with zero context from N1/N2, recovered
  everything from the bead + filesystem. Produced a working framed star chart.
- **WORKS.** This time the worker used the corrected `--add-label` flag
  (carried in its brief) -- all bd commands behaved, no anomalies. Confirms the
  iteration-1 flag findings, once in the brief, are sufficient.
- Independently re-verified: `starforge.py --seed 7` renders
  "Hourglass Infinita Obscura" over a fresh starfield. Contract check: ALLOW.

Final artifact (seed 42):
```
╔══════════════════════════════════════════════════╗
║                The Lesser Lantern                ║
╠══════════════════════════════════════════════════╣
║  ... rendered ASCII starfield ...                ║
╚══════════════════════════════════════════════════╝
```

## Iteration 3 -- wisps, aggregation, gates

### Wisps -- WORK, with a discovery
- **[finding] Ephemeral wisps live in a separate id namespace and are hidden
  from `bd list`.** A wisp created with `--ephemeral --wisp-type escalation`
  got id `starforge-run-wisp-nsb` (note the `-wisp-` infix) and did NOT appear
  in `bd list` OR `bd list --all` -- only in `bd mol wisp list`. Discovery of
  wisps MUST use `bd mol wisp list` or graph-link traversal, never `bd list`.
  Design impact: the doctrine's "discover linked wisps via `bd show` links"
  holds, but any code enumerating wisps needs the wisp-specific command.
- **[finding] `bd create` uses `-l/--labels`; `bd update` uses `--add-label`.**
  Inconsistent flag names between the two verbs -- a real footgun. Both briefs
  and the activation-protocol contract must spell out which verb takes which.

### Graph-link verdict aggregation -- WORKS (keystone architectural claim)
- Created review wisp, `dep add <merge-bead> <wisp>` (wisp blocks merge bead).
- Merge bead was **NOT** in `bd ready` while the wisp was open.
- Closing the wisp (approve) made the merge bead **immediately ready**.
- This proves the central design claim: *merge readiness = last review wisp
  closes, computed by the dependency graph, no actor counts dimensions.*
  Works on real bd with zero custom logic.

### Gates -- WORK (both types)
- **human gate**: blocked the merge bead; `bd gate resolve` unblocked it.
- **timer gate** (`--timeout=2s`): blocked its bead; stayed blocked until
  `bd gate check --type=timer` ran after the timeout, then auto-resolved.
  Confirms: **gates never self-resolve -- a ticker must run `bd gate check`**
  (the shepherd patrol / orchestrator wake, per doctrine). Exactly as designed.
- **[finding] gate ids are top-level** (`starforge-run-co9`), resolvable and
  independent of the blocked bead -- clean.

### Ledger + burn -- WORKS
- Created a `gc_report` ledger wisp, closed it, ran `bd purge --force` →
  "No wisps found" (all closed ephemerals gone, including the review wisp).
  The durable node beads and merge bead survived. Wisp burn is real and
  scoped to closed ephemerals only.

## Cross-cutting

- **Isolation held.** Entire run in `/tmp/starforge-run` with its own beads DB
  (prefix `starforge-run`); zero contamination of the real repo's store.
- **My own git-safety hook fired correctly** on `rm -rf "$PLAY"` (unexpanded
  variable) during setup -- the deblock policy working as designed, caught in
  the wild.
