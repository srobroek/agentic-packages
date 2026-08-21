# Validation Run Report -- bead-as-brief v2 machinery

**What was tested:** the bead-as-brief orchestration machinery, exercised by
building **starforge** (a cosmic ASCII-chart CLI) end-to-end in an isolated
playground (`/tmp/starforge-run`, own git + beads DB). Three real subagent
domain-specialists were driven purely by `CLAIM <bead-id>`, and the proven
`rules-eval.sh` contract evaluator was run against their real output as the
SubagentStop hook. Three iterations: parallel wave (N1+N2) → dependency-gated
integration (N3) → mechanism sweep (wisps, gates, aggregation, burn).

**Bottom line:** the architecture holds on real `bd`. Every load-bearing
claim -- bead-as-brief activation, atomic claims, dependency scheduling,
contract enforcement, graph-link verdict aggregation, gates, wisp burn --
worked. The live run caught one real evaluator bug and a cluster of `bd` flag
gotchas that fixture testing alone would have missed. starforge itself works:
deterministic framed star charts with whimsical constellation names.

## Mechanism-by-mechanism

| Mechanism | Verdict | Evidence |
|---|---|---|
| Beads DAG + `bd ready` scheduling | **WORKS** | N3 held out of the frontier until N1+N2 closed; frontier advanced exactly on contract |
| Bead metadata (read/write) | **WORKS** | scope/execution_kind/tier/output_ref set at create, read back, evaluated |
| Bead-as-brief activation | **WORKS** | 3 agents ran from `CLAIM <id>` + BRIEF comment; no task data in prompts |
| Atomic claim + actor naming | **WORKS** | both parallel workers claimed atomically; assignee = `<role>-<node-bead>` (hook-derivable) |
| Inter-generation handoff | **WORKS** | N3 (fresh agent) recovered N1/N2 APIs from bead + files, zero shared context |
| Rules-engine contract enforcement | **WORKS** (after fix) | complete node → ALLOW; incomplete node → BLOCK with the one failed check; enforce→fix→pass loop demonstrated live |
| Graph-link verdict aggregation | **WORKS** | merge bead blocked while review wisp open, ready the instant it closed -- no dimension counting |
| Wisps (create/close/burn) | **WORKS** | escalation + gc_report wisps; `bd purge` burned all closed ephemerals |
| Human gate | **WORKS** | blocked merge bead until `bd gate resolve` |
| Timer gate | **WORKS** | auto-resolved after timeout, but only when `bd gate check` ran |
| Isolation | **WORKS** | zero contamination of the real repo store |

## What broke / was hardened

1. **Evaluator vs real `bd` JSON shape (fixed).** `bd show --json` returns an
   **array**, and carries **no comments** (only `comment_count`); comments
   come from `bd comments <id> --json`. The evaluator, fixture-tested only,
   blocked everything against real beads. Fixed: live mode unwraps the array
   and splices a separate comments fetch. **Lesson: fixtures prove the logic,
   not the tool contract -- the real hook build needs a live-shape test beside
   the fixtures.** This alone justified the live run.

2. **Greedy-sed predicate bug (fixed during N2 build).** Extracting the regex
   from `label ~ "^agent:"` with a greedy sed captured the trailing quote.
   Fixed with bash parameter expansion. Same fragility class as the historic
   hook-guard anchoring bugs -- argues for the rules-as-data + fixture approach.

## `bd` flag gotchas (for the real build's briefs & contract)

- `bd update` label flag is **`--add-label`**, not `--label` (which errors).
- `bd create` label flag is **`-l/--labels`** (comma-separated) -- *different
  verb, different flag name*. Inconsistent; both must be documented.
- `--status` accepts only built-in states; custom states
  (`reported`/`approved`/…) go in `--metadata '{"state":"..."}'`. The v2
  design's rich state machine will need custom-status registration in bd, or
  it lives in metadata -- **decision needed** (see log.md).
- Ephemeral wisps are hidden from `bd list`/`--all`; enumerate via
  `bd mol wisp list` or link traversal.
- Gates never self-resolve; a ticker must run `bd gate check`.

## Agent behavior notes

All three specialists (sonnet) followed the protocol faithfully: claimed,
read the brief, stayed in scope, verified their own work, reported, stamped
metadata, set handoff. The two that hit the `--label` error handled it
differently -- N1 discovered `--add-label` and self-corrected; N2 took the
metadata fallback and left its handoff label unset. **The contract caught
exactly that gap** (N2 → BLOCK: handoff), which is the entire point: agents
make small protocol errors, and the SubagentStop hook is what makes them
non-silent. Once the correct flag was in N3's brief, zero anomalies.

## Recommendations for the production build (N3--N7)

- Keep a live-shape test in the rules-engine package tests, not just fixtures.
- Bake the exact `bd` flag forms into the generated agent contract blocks and
  the activation-protocol reference (workers copy what the brief shows).
- Resolve the custom-status question: register states in bd vs metadata-only.
- The wisp-discovery command (`bd mol wisp list`) belongs in the doctrine's
  discovery note.
- Everything else in the design is validated as-is -- proceed.
