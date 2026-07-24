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
- **[human?] AGENT_TEAMS flag.** `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is
  not in settings; warm-tier features (SendMessage wake, FIX-round resume)
  need it. I will add it to the project/global settings env during the hooks
  phase unless the user objects — flagging because it's an experimental-flag
  change to shared settings.
