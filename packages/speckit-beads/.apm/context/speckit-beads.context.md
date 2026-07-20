# SpecKit on Beads (speckit-feature formula)

The upstream /speckit.* skills are unmodified; they still talk about
tasks.md. This layer redirects them: state lives in beads, never tasks.md.

SETUP (once per repo)
MUST Copy `formulas/speckit-feature.formula.toml` from this package into
  `.beads/formulas/` (or `~/.beads/formulas/`), then verify with
  `bd formula show speckit-feature --json`.

SPEC START — RECALL PARKED WORK
MUST At spec start (/speckit.specify), query parked work — `bd list
  --status deferred --json` plus open beads labeled deferred (`bd query
  "label=deferred AND status!=closed" --json`) — and surface the hits to
  the user for inclusion before writing the spec.

IMPLEMENT ROUTING
MUST /speckit.implement is deprecated here; route through the
  agent-assign chain (assign → validate → execute). If it is invoked,
  stop and work the molecule steps instead.

MOLECULE PER FEATURE
MUST Pour one molecule per spec dir:
  `bd mol pour speckit-feature --var feature=<NNN-slug>`.
MUST After pour, tag the root: `bd update <root-id> --spec-id <NNN-slug>
  --metadata '{"spec_dir":"specs/<NNN-slug>"}'` — one spec dir = one root.
DEFAULT Track position with `bd mol current <root-id>`; run `bd gate check`
  at phase boundaries.

TASKS PHASE — tasks.md IS NEVER AUTHORED
MUST When /speckit.tasks instructs writing specs/*/tasks.md, create beads
  instead (a PreToolUse hook denies the write): each task becomes
  `bd create "T00N <title>" --parent <implement-step-id> --spec-id <NNN-slug>
  -t task`; ordering via `bd dep add <later> <earlier>`; bulk via
  `bd create -f <tmpfile>.md` with the temp file OUTSIDE specs/.
MUST Use `discovered-from` deps for follow-up work found mid-task.
MUST When a later phase (analyze, verify-tasks, converge) instructs reading
  tasks.md for task state, query beads instead: `bd query
  "spec_id=<NNN-slug>" --json`, `bd ready`, or `bd swarm status <root-id>`.
DEFAULT Human review of the breakdown: `bd graph <implement-step-id>` or the
  bv TUI. A PostToolUse read advisory exists as backstop only.

LEGACY tasks.md (brownfield)
DEFAULT Repos with an existing tasks.md get a one-time read →
  `bd create` migration pass; the file then stays inert (reads allowed,
  checkbox updates denied). Never sync checkboxes back.

GATES
MUST Human gates at clarify-approval, analyze-approval, and verify-signoff:
  resolve only after the user approves interactively
  (`bd gate resolve <gate-id>`, then `bd close <step-id> --reason`).
DEFAULT Optional steps (critique, security-review): skip by closing with
  `--reason skipped` after the user opts out.
DEFAULT Merge step with an open PR: `bd gate create --type=gh:pr
  --blocks <step-id> --await-id=<pr-number>` so the step waits on the merge.

EXECUTION ROUTING
DEFAULT Steps carry `labels = ["agent:<name>"]` plus `metadata`
  (`execution_skill`, `execution_agent_type`, `execution_mode`); read them
  with `bd show <id> --json` to pick the skill or subagent for the step.
MUST Work steps via `bd update <id> --claim` → do the work →
  `bd close <id> --reason`; end mutating sessions with `bd dolt push`.

WHEN NOT TO USE
DEFAULT Tinyspec or bugfix scale (one-paragraph change): plain beads or no
  tracking — do not pour the formula.
