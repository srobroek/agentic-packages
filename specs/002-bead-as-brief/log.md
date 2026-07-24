# 002-bead-as-brief — autonomous run log

Purpose: everything out of the ordinary, ambiguous, human-input-worthy, or
likely to change later. Append-only during the run.

## 2026-07-24

- **[info] Agent context pointer stale by design.** `speckit-agent-context-update`
  wrote CLAUDE.md pointing at `specs/001-agent-conformance/plan.md` — 002 has no
  plan.md yet. Rerun after `/speckit-plan` produces one.
- **[human?] Push path.** Direct `git push` is blocked by Code Defender on this
  machine (unapproved external repo); pushes go through `dgit`. Worked, but if
  the orchestrate run spawns agents in worktrees, every agent that pushes needs
  the same path. May need to teach subagent briefs `dgit push` or run pushes
  from the primary session.
- **[ambiguity] Planner tier.** Spec's own doctrine says planning runs
  opus/fable-class high. This session is Fable — the planner-node role is
  fulfilled by the main session this run; recording that we're consciously NOT
  spawning a separate planner node for the plan phase (bootstrap exception:
  the orchestrate v2 machinery this spec builds yet to host it).
- **[directive] Live validation run.** User: after the build, orchestrate a
  creative/fun project of my choosing end-to-end, multiple iterations, as the
  real-world test of the new machinery. This doubles as SC-001..SC-007
  validation. Will design the test project when the machinery is runnable.
- **[directive] Validation-run observability writeup.** User: during the live
  test, keep a dedicated log beyond the normal orchestrator role — do beads
  work, do wisps work, do agents behave per contract — and produce a writeup.
  Plan: a `validation-run/` observations journal per iteration + a final
  mechanism-by-mechanism report (what worked, what broke, what surprised).
  Added to quickstart V7 as a deliverable.
- **[decision] Not pouring the speckit-feature molecule for the build.** The
  26-step formula has human gates (clarify-approval, analyze-approval,
  verify-signoff) that would block autonomous progress — contradicts the
  standing "don't pause to ask" directive. The design was already grilled to
  completion, so clarify/analyze gates would be no-ops anyway. Tracking the
  build as plain beads under an epic instead (the design doc itself sanctions
  plain beads for tinyspec/direct work). speckit formula still applies to
  future features; this one bootstrapped by hand.
- **[decision] Build scope this session.** Full production system (≈15 rules
  files × 2 runtimes, live hook install, skill rewrites, fleet deletions +
  apm compile) is multi-day → beads. This session builds the KEYSTONE: the
  rules-engine evaluator + conformance suite that makes the enforcement
  guarantee (US2 / SC-002) real and testable, then runs the creative
  orchestration test to exercise the bd primitive layer (beads/wisps/links/
  gates/labels) the whole design rests on. Rationale: the convention layer is
  bd-native and already works; the evaluator is the novel provable artifact.
- **[superseded] orc-dc9** (prior-session verification bead) partially
  obsolete: 4 of its 6 target agents are deleted by 002. Annotated,
  unassigned, left open for the survivor sweep.

### N1 doctrine — DONE
- Added `packages/beads/.apm/context/beads.orchestration-doctrine.context.md`,
  wired into the beads context WORKFLOWS index. Pure steering.

### N2 rules-engine (KEYSTONE) — DONE, PROVEN
- Built `packages/beads/scripts/rules-eval.sh` (SubagentStop evaluator, bash
  3.2, fail-open, jq+yq), `domain-specialist.rules.yml`, and a 13-case
  conformance suite `rules-eval-test.sh`. **13/13 pass.**
- **[bug found+fixed] Greedy-sed label pattern bug.** Extracting the regex
  from `require: label ~ "^agent:"` with `sed -E 's/^label ~ "?(.*)"?$/\1/'`
  captured the trailing quote into the pattern (`^agent:"`), so the handoff
  label check never matched → false blocks on otherwise-complete nodes. This
  is EXACTLY the class in memory `hook-guard deblock policy` (regex/anchoring
  fragility). Fixed with bash parameter expansion (`${req#label ~ }` then
  strip quotes). Lesson for the real hooks build: prefer param-expansion over
  sed for predicate parsing; the conformance suite caught it immediately —
  vindicates rules-as-data + fixtures over hand-written per-agent checks.
- **[decision] Fixture mode in the evaluator.** Added a `._bead` /
  `._rules_file` payload path so the suite runs with no bd/live state. Keeps
  SC-002 provable in CI (hooks-portability-ci) without a scratch beads DB.
- **[later] yq dependency.** Evaluator shells to `yq` for YAML→JSON. yq is on
  PATH here and in toolchain-defaults, but the real hook must fail open if
  absent (it does) and CI must ensure yq is present. Flag for N3 packaging.

### Live orchestration test (starforge) — DONE, 3 iterations
- Full writeup: `validation-run/REPORT.md`; per-iteration journals
  `iteration-1.md`, `iteration-2-3.md`; artifact + sample renders in
  `validation-run/starforge-artifact/`.
- **[HUMAN INPUT NEEDED] custom bead states.** bd `--status` rejects
  `reported`/`approved`/`changes_requested`/etc. — only built-in states are
  accepted. The v2 design assumes a rich node state machine. Two options:
  (a) register custom statuses in bd (if it supports it — needs investigation),
  or (b) keep the state machine entirely in `metadata.state` and treat bd
  `status` as coarse (open/in_progress/closed). The evaluator already reads
  `metadata.state` first, so (b) works today. RECOMMEND (b) unless bd gains
  first-class custom states — but this is a real design decision, flagging.
- **[finding] bd flag inconsistency** (create `-l/--labels` vs update
  `--add-label`) and **ephemeral wisps hidden from `bd list`** (use
  `bd mol wisp list`). Both must land in the generated contract blocks + the
  doctrine discovery note (N4/N6 work).
- **[finding→fixed] evaluator only fixture-tested missed the real bd JSON
  shape** (array + separate comments). Fixed in live mode. Real build MUST
  keep a live-shape test. Logged as the top recommendation.
- **[validated] the enforcement guarantee is real:** N2 left its handoff
  label unset (took a wrong-flag fallback); the contract evaluator blocked it
  with exactly `failed_checks:[handoff]`, nothing else. Fix → ALLOW. This is
  the whole thesis of the spec, demonstrated on a live agent.
- **[human?] AGENT_TEAMS flag.** `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is
  not in settings; warm-tier features (SendMessage wake, FIX-round resume)
  need it. I will add it to the project/global settings env during the hooks
  phase unless the user objects — flagging because it's an experimental-flag
  change to shared settings.
