# Validation Run -- Iteration 1: starforge (cosmic ASCII CLI)

Goal: exercise the bead-as-brief machinery on a real creative build in an
isolated playground (`/tmp/starforge-run`, own git + beads DB, prefix
`starforge-run`). Orchestrator = this session. Workers = real spawned
subagents activated only by `CLAIM <bead-id>`, reading their brief from the
bead. My proven `rules-eval.sh` acts as the SubagentStop hook against their
output.

Project: `starforge` -- a CLI that prints a framed "star chart": a whimsical
constellation name over a rendered ASCII starfield. Decomposed into:
- N1 starfield generator (`starfield.py`) -- parallel
- N2 constellation namer (`constellations.py`) -- parallel
- N3 CLI assembler (`starforge.py`) -- depends on N1+N2

## Mechanism observations (as they happen)

### Beads -- DAG & ready frontier
- **WORKS.** `bd init --skip-hooks` in a fresh dir created an isolated store
  (embeddeddolt). Epic + 3 children created with hierarchical ids
  (`...2nw.1/.2/.3`).
- **WORKS.** `bd dep add N3 N1` + `bd dep add N3 N2` correctly held N3 out of
  the ready frontier; `bd ready --parent <epic>` returned exactly {N1,N2} in
  parallel. Dependency scheduling behaves per contract.
- **[gotcha] `--db` flag needed per-command.** The shell cwd resets between
  tool calls in this harness, and `bd` auto-discovers `.beads` from cwd -- so
  every command needs an explicit `--db /tmp/starforge-run/.beads/embeddeddolt`
  or a stable cwd. Real orchestrate runs pin cwd; noted so worker briefs carry
  the explicit --db. Not a bd defect, an environment interaction.

### Bead-as-brief -- activation
- **WORKS.** Full task instruction written as a `BRIEF` comment on each node;
  workers spawned with only `CLAIM <bead-id>` + protocol boilerplate. No task
  data in the spawn prompt beyond the verb and the DB path. FR-002 shape held.

### Metadata
- **WORKS.** JSON metadata (`scope`, `execution_kind`, `complexity_tier`,
  `artifacts_dir`) set at creation and read back via `bd show`.

### Workers (real spawned subagents, sonnet) -- WORKED
- Both N1 + N2 spawned in parallel with only `CLAIM <bead-id>` + protocol.
  Both atomically claimed (`in_progress`, assignee = `<role>-<node-bead>`),
  read their BRIEF, wrote correct code, ran verify, reported. Produced
  `starfield.py` (weighted-glyph ASCII field, deterministic) and
  `constellations.py` (whimsical name generator) -- both independently
  re-verified by the orchestrator. Bead-as-brief activation works with real
  agents.

### [bug -- bd tooling, found by both workers] flag names
- `bd update --label <x>` → **rejected** `unknown flag: --label`. Correct flag
  is **`--add-label`**. N1 discovered this and self-corrected; N2 took the
  metadata fallback and never set its label → left its node incomplete.
- `bd update --status reported` → **rejected**; `reported` is not a built-in
  status. Custom states go in `--metadata '{"state":"..."}'`.
- **Impact on spec:** the activation-protocol contract and all worker briefs
  MUST specify `--add-label` and the metadata-state convention. The design
  doc's prose used `--label`-style shorthand loosely; N3+ briefs corrected.

### [bug -- evaluator vs real bd, found by the live hook run] KEYSTONE HARDENED
- Running `rules-eval.sh` against REAL beads (not fixtures) exposed two shape
  mismatches my fixtures never had:
  1. `bd show --json` returns an **ARRAY**, not an object → evaluator read an
     empty id and blocked everything.
  2. `bd show --json` carries **no `comments`** (only `comment_count`);
     comments come from a separate `bd comments <id> --json` (also an array,
     text in `.text`). My `comment.verb` predicate silently saw zero comments.
- **Fix:** live mode now unwraps the `bd list` array AND fetches
  `bd comments <id> --json`, splicing them into `.comments` so both fixture
  and live paths read one shape. Fixture suite still 13/13.
- **Lesson (logged for the real build):** fixtures alone don't prove a hook --
  they proved the LOGIC but not the bd JSON contract. The real N3 build must
  keep a live-shape test alongside the fixtures. This is precisely why the
  user asked for a live orchestration test; it earned its keep on the first
  iteration.

### Enforcement loop -- DEMONSTRATED END-TO-END
- After the fix, the evaluator run against real output:
  - **N1 → ALLOW** (complete: output_ref + `agent:reviewer` + REPORTED).
  - **N2 → BLOCK: handoff** (the ONE real defect -- missing label). The
    SubagentStop hook would have blocked N2's exit with exactly
    `failed_checks:[handoff]` and nothing else -- failure-specific, correct.
  - Applied the contract-demanded fix (`--add-label agent:reviewer`) →
    **N2 → ALLOW**. Full enforce→diagnose→fix→pass loop works on live agents.
- Closing N1+N2 cleared N3's deps; `bd ready` advanced to exactly {N3}.
  Crash-resumable dependency handoff (US1) confirmed on real state.

### Verdict so far (iteration 1)
| Mechanism | Status |
|---|---|
| Beads DAG + ready frontier | WORKS |
| Metadata read/write | WORKS |
| Bead-as-brief activation (CLAIM-only) | WORKS |
| Atomic claim + actor naming | WORKS |
| Rules-engine contract enforcement | WORKS (after live-shape fix) |
| `--add-label` / custom-state | bd flag gotchas → briefs corrected |
| Wisps / gates / GitHub PR flow | not yet exercised (iteration 2+) |
