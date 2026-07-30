# SpecKit Workflow

The upstream /speckit.* skills are unmodified; they still talk about tasks.md.
This layer redirects them: state lives in beads, never tasks.md. The poured
`speckit-feature` molecule is the phase DAG and the only statement of step
order; nothing here restates it.

EXECUTION
MUST Invoke SpecKit commands through their runtime-native skill interface.
MUST Keep corrections with the same live agent through the runtime-native
  messaging operation until its assigned work passes review.
NOT Invoke deprecated `/speckit.implement`; route through the agent-assign chain
  (assign -> validate -> execute) and work the molecule steps.
NOT Proceed with open questions, unresolved gaps, or unapproved intent changes.

SETUP (once per repo)
MUST Copy `formulas/speckit-feature.formula.toml` into `.beads/formulas/` (or
  `~/.beads/formulas/`); verify with `bd formula show speckit-feature --json`.
DEFAULT Without a beads workspace, preserve upstream SpecKit artifact behavior.

SPEC IDENTITY
MUST Set `--spec-id <NNN-slug>` on every bead a spec produces -- molecule root,
  task bead, and decision record alike. It is the native field binding a bead to
  the spec that produced it; without it the bead survives and its provenance does
  not. This is the only statement of the convention; other sections rely on it.

MOLECULE PER FEATURE
MUST Pour one molecule per spec dir (`bd mol pour speckit-feature --var
  feature=<NNN-slug>`), then tag the root -- one spec dir = one root:
  `bd update <root-id> --spec-id <NNN-slug> --metadata
  '{"spec_dir":"specs/<NNN-slug>"}'`.
DEFAULT Track position with `bd mol current <root-id>`; `bd gate check` at
  phase boundaries.

SPEC START -- RECALL PARKED WORK
MUST At spec start (/speckit.specify), query parked work (`bd list --status
  deferred --json` plus `bd query "label=deferred AND status!=closed" --json`)
  and surface the hits to the user before writing the spec.

TASK STATE
MUST When /speckit.tasks instructs writing specs/*/tasks.md, create beads
  instead: `bd create "T00N <title>" --parent <implement-step-id> --spec-id
  <NNN-slug> -t task`; order with `bd dep add <later> <earlier>`; bulk
  `bd create -f <tmp>.md` OUTSIDE specs/.
MUST Use `discovered-from` deps for follow-up work found mid-task.
MUST When a later phase (analyze, verify-tasks, converge) instructs reading
  tasks.md for task state, query beads instead: `bd query "spec_id=<NNN-slug>"
  --json`, `bd ready`, or `bd swarm status <root-id>`.
MUST Keep the implement parent open until every implementation child is closed.
  `bd close` on a parent with open children succeeds silently.
DEFAULT Human review of the breakdown: `bd graph <implement-step-id>` or the
  bv TUI. A PostToolUse read advisory exists as backstop only.
DEFAULT Brownfield: an existing tasks.md gets a one-time read -> `bd create`
  migration, then stays inert (reads allowed, checkbox writes denied); never
  sync checkboxes back.

GATES
MUST Resolve a human gate with `bd gate resolve <gate-id>` then `bd close
  <step-id> --reason`, only after the user approves interactively.
DEFAULT Optional steps (critique, security-review): close `--reason skipped`
  once the user opts out.
DEFAULT Merge step with an open PR: `bd gate create --type=gh:pr
  --blocks <step-id> --await-id=<pr-number>` so the step waits on the merge.

EXECUTION ROUTING
DEFAULT Steps carry `labels = ["agent:<name>"]` plus `metadata`
  (`skill_hints`, `execution_agent_type`, `execution_mode`); read them with
  `bd show <id> --json` to pick the skill or subagent. `skill_hints` is the key
  orchestrate's domain-specialist reads, so one step routes to either driver.
MUST Work steps via `bd update <id> --claim` -> do the work ->
  `bd close <id> --reason`; end mutating sessions with `bd dolt push`.

WISPS -- PHASE CHATTER OFF THE STEP THREAD
Wisp roles, TTLs, and the promotion rule: [orchestration
doctrine](../../../beads/.apm/context/beads.orchestration-doctrine.context.md).
MUST Keep the step thread to outcome, artifact path, and close reason; route
  progress and retries to a `[wisp:worklog]`, one clarify/analyze question per
  escalation wisp (answer lands in spec.md or plan.md before the burn), gate
  nudges to a ping, and each fleet-review dimension to a review shell that
  `blocks` the downstream step. Every wisp links `relates-to` its step.

DECISIONS
MUST Register a hard-to-reverse or boundary-crossing choice when it lands, not at
  closeout. The `adr-as-beads` package owns the format, the path, and the gate;
  this section owns only which SpecKit phases produce one.
| phase | what earns a record |
|---|---|
| plan | a technology, contract, or boundary choice the plan depends on |
| critique + security plan review | a risk knowingly accepted rather than mitigated |
| analyze | a constraint discovered late that changes the approach |
| implement | a deviation from the approved plan, recorded before the deviation spreads |
| iterate | the reason an approved approach changed |
MUST Cite the record on the phase's bead before that phase closes. A phase that
  produced a choice and closed without a citation loses the alternatives.
NOT Defer recording to retro or closeout. By then the rejected options are gone, and
  the rejected option is the part worth keeping.
| observed condition | route |
|---|---|
| Approved intent is correct and implementation is incomplete | converge |
| Approved intent or approach changes | mol-speckit-iterate molecule |
| Implemented code has a defect | bugfix skill |
| Review, QA, or security finds actionable defects | mol-speckit-fix-findings molecule |
| Change fits one paragraph and needs no full lifecycle | tinyspec |

CLOSEOUT
MUST Close the feature root after its final step and follow the active Beads
  authority policy for the single terminal sync.

WHEN NOT TO USE
DEFAULT Tinyspec or bugfix scale (one-paragraph change): plain beads or no
  tracking -- do not pour the formula.
