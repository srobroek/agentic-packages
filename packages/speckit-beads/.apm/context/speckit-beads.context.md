# SpecKit on Beads (speckit-feature formula)

The upstream /speckit.* skills are unmodified; they still talk about
tasks.md. This layer redirects them: state lives in beads, never tasks.md.

SETUP (once per repo)
MUST Copy `formulas/speckit-feature.formula.toml` into `.beads/formulas/` (or
  `~/.beads/formulas/`); verify with `bd formula show speckit-feature --json`.

SPEC START -- RECALL PARKED WORK
MUST At spec start (/speckit.specify), query parked work (`bd list --status
  deferred --json` plus `bd query "label=deferred AND status!=closed" --json`)
  and surface the hits to the user before writing the spec.

IMPLEMENT ROUTING
MUST /speckit.implement is deprecated here; route through the agent-assign
  chain (assign → validate → execute) and work the molecule steps instead.

MOLECULE PER FEATURE
MUST Pour one molecule per spec dir (`bd mol pour speckit-feature --var
  feature=<NNN-slug>`), then tag the root -- one spec dir = one root:
  `bd update <root-id> --spec-id <NNN-slug> --metadata
  '{"spec_dir":"specs/<NNN-slug>"}'`.
DEFAULT Track position with `bd mol current <root-id>`; `bd gate check` at
  phase boundaries.

TASKS PHASE -- tasks.md IS NEVER AUTHORED
MUST When /speckit.tasks instructs writing specs/*/tasks.md, create beads
  instead (a PreToolUse hook denies the write): `bd create "T00N <title>"
  --parent <implement-step-id> --spec-id <NNN-slug> -t task`; order with
  `bd dep add <later> <earlier>`; bulk `bd create -f <tmp>.md` OUTSIDE specs/.
MUST Use `discovered-from` deps for follow-up work found mid-task.
MUST When a later phase (analyze, verify-tasks, converge) instructs reading
  tasks.md for task state, query beads instead: `bd query "spec_id=<NNN-slug>"
  --json`, `bd ready`, or `bd swarm status <root-id>`.
DEFAULT Human review of the breakdown: `bd graph <implement-step-id>` or the
  bv TUI. A PostToolUse read advisory exists as backstop only.
DEFAULT Brownfield: an existing tasks.md gets a one-time read → `bd create`
  migration, then stays inert (reads allowed, checkbox writes denied); never
  sync checkboxes back.

GATES
MUST Human gates at clarify-approval, analyze-approval, and verify-signoff:
  `bd gate resolve <gate-id>` then `bd close <step-id> --reason`, only after
  the user approves interactively.
DEFAULT Optional steps (critique, security-review): close `--reason skipped`
  once the user opts out.
DEFAULT Merge step with an open PR: `bd gate create --type=gh:pr
  --blocks <step-id> --await-id=<pr-number>` so the step waits on the merge.

EXECUTION ROUTING
DEFAULT Steps carry `labels = ["agent:<name>"]` plus `metadata`
  (`skill_hints`, `execution_agent_type`, `execution_mode`); read them with
  `bd show <id> --json` to pick the skill or subagent. `skill_hints` is the key
  orchestrate's domain-specialist reads, so one step routes to either driver.
MUST Work steps via `bd update <id> --claim` → do the work →
  `bd close <id> --reason`; end mutating sessions with `bd dolt push`.

WISPS -- PHASE CHATTER OFF THE STEP THREAD
Wisp roles, TTLs, and the promotion rule: [orchestration
doctrine](../../../beads/.apm/context/beads.orchestration-doctrine.context.md).
MUST Keep the step thread to outcome, artifact path, and close reason; route
  progress and retries to a `[wisp:worklog]`, one clarify/analyze question per
  escalation wisp (answer lands in spec.md or plan.md before the burn), gate
  nudges to a ping, and each fleet-review dimension to a review shell that
  `blocks` the downstream step. Every wisp links `relates-to` its step.

WHEN NOT TO USE
DEFAULT Tinyspec or bugfix scale (one-paragraph change): plain beads or no
  tracking -- do not pour the formula.
