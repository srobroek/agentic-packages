---
description: SpecKit workflow overview, command reference, and human gating rules.
applyTo: "{.specify/**,specs/**,**/spec.md,**/tasks.md,**/pending-iteration.md}"
---

# SpecKit Workflow

## Rules

- All workflow steps are mandatory by default. Always suggest the next step in
  the default path; skip a step only on explicit user request, never because it
  seems "overkill" or "trivial."
- Invoke speckit via the Skill tool only. Never write spec artifacts manually.
- Get user approval between phases unless the user says "run unattended."
  Unattended mode only skips approval gates between non-interactive steps;
  interactive commands (clarify, analyze, checklist) still require user input.
- Never proceed past a stage with open questions, unresolved gaps, or items
  requiring review. Present them to the user and resolve together first.
- Never silently deviate from spec. Material deviation: stop, explain, get
  approval, route through iterate. Minor deviation: flag in commit.
- Record every architecture/design decision as an ADR. When a non-trivial,
  hard-to-reverse decision is made (a technology choice, a constraint, an
  approach picked over alternatives), capture it with the
  `/architecture-decision-records` skill as a one-file MADR-format ADR under
  `docs/adr/NNNN-title.md` (status proposed/accepted/superseded; never delete a
  superseded ADR, mark it). This is a continuous process, not a workflow stage:
  do it at the moment the decision lands, in any phase. Reference the ADR from
  the spec/plan and from the roadmap entry's `governed-by:` field.
- `/speckit.implement` is deprecated; do not invoke it. Use the agent-assign
  flow (`assign` -> `validate` -> `execute`), which routes each task to a
  specialized sub-agent for better quality.
- Orchestrator review gate: when sub-agents deliver work (execution, review, or
  fixes), review the actual code changes against the task requirements before
  accepting -- agent summaries describe intent, not necessarily what landed.
  Keep the sub-agent alive after it reports back; use `SendMessage` to send
  corrections to the same agent so it retains full context and fixes only the
  specific issues. Dismiss the agent only once the work passes review. This
  holds under parallel (worktree-isolated) execution too: review each agent's
  emitted diff before its worktree is reconciled.
- Requires the `agent-assign` specify extension (`specify extension add
  agent-assign`). Included in the canonical extension set for new projects.

## Workflow Steps

Phases run in order (1 -> 2 -> 3); within a phase, steps run in numeric order
and "parallel with" pairs run concurrently. Phase 3 starts only after 9c
completes and is a pipeline (10 -> 11 -> 11b -> 11c -> 12 + 13); all of it must
finish before 14. Scope changes route through iterate (below) and resume at
the triggering step.

### Phase 1 -- Specification (human-gated)

| Step | Command | Mode | Notes |
|------|---------|------|-------|
| 1 | `/speckit.specify` | auto -> approval | Creates spec.md |
| 2 | `/speckit.clarify` | interactive | Ask questions, incorporate feedback |
| 3 | `/speckit.plan` | auto -> approval | Architecture and approach |
| 4 | `/speckit.tasks` | auto -> approval | Task breakdown with dependencies |
| 5 | `/speckit.checklist` | interactive | Requirements-quality gate over spec + plan + tasks |
| 5b | `/speckit.critique.run` | parallel with 5c | Plan + task quality gate |
| 5c | `/speckit.security-review` | parallel with 5b | Security review of plan/tasks |
| 6 | `/speckit.analyze` | interactive | Risk analysis, resolve before impl |
| 7 | `/speckit.taskstoissues` | auto | Creates GitHub/GitLab issues |
| 8 | `/speckit.checkpoint.commit` | auto | Snapshot before implementation |

### Phase 2 -- Implementation

| Step | Command | Mode | Notes |
|------|---------|------|-------|
| 9a | `/speckit.agent-assign.assign` | auto -> approval | Route tasks to specialized sub-agents |
| 9b | `/speckit.agent-assign.validate` | auto | Validate agent assignments |
| 9c | `/speckit.agent-assign.execute` | auto | Execute with assigned agents. Checkpoint after each task. |

### Phase 3 -- Post-implementation quality (all mandatory)

| Step | Command | Mode | Notes |
|------|---------|------|-------|
| 10 | `/speckit.verify-tasks` | subagent | Fresh context; phantom completion detection |
| 11 | `/speckit.verify` | subagent, after 10 | Validate code against spec |
| 11b | `/speckit.review.run` | auto, after 11 | Full review cycle; findings -> `fix-findings` after triage |
| 11c | `/speckit.qa.run` | auto, after 11b | QA retest; failures -> `fix-findings` |
| 12 | `/speckit.code-review` | parallel with 13, after 11c | Subagent |
| 13 | `/speckit.security-review` | parallel with 12, after 11c | Subagent |
| 14 | `/speckit.cleanup` | main thread | Auto-fix small, issue for large |
| 15 | `/speckit.sync.analyze` | parallel with 16 | Subagent; drift detection between spec and code |
| 16 | `/speckit.sync.conflicts` | parallel with 15 | Subagent; inter-spec contradiction check |
| 17 | `/speckit.retro.run` | main thread | Retrospective; needs full session context |
| 18 | Documentation update | main thread | Update affected docs |
| 19 | `/speckit.checkpoint.commit` | auto | Final commit |

## Scope Change (iterate)

Trigger: user changes requirements, or agent discovers the spec approach won't
work. Iterate is mandatory once tasks.md exists; before tasks.md, go back to
the relevant earlier step directly.

1. `/speckit.iterate.define "<change>"` -> writes `pending-iteration.md`
2. Always present the iteration plan to the user
3. `/speckit.iterate.apply` -> updates spec/plan/tasks
4. Update issues for changed/removed/new tasks
5. If cross-spec impact: `/speckit.sync.conflicts` immediately
6. `/speckit.roadmap.write` -> re-sync the roadmap entry to the iterated
   spec/plan/tasks. MANDATORY after every iterate: an iteration changes scope,
   so the roadmap (and each entry's `governed-by:` field) is stale until
   rewritten. Do not commit the iteration without it.
7. `/speckit.checkpoint.commit`
8. Resume at the step where the change was triggered

## Gap Closing (converge)

Trigger: during Phase 3 QA, a step (verify, verify-tasks, sync.analyze) finds
that the code does not yet implement everything the spec/plan/tasks call for,
and the gap is unbuilt work -- not a scope change and not a defect in built
code. Conditional, not a mandatory step: skip it when verify/verify-tasks pass
clean. Converge is a no-op when the code already satisfies the spec.

Use the right tool for the gap:
- Spec is right, code is incomplete -> `converge` (this section).
- Spec/intent must change -> `iterate` (edits spec/plan/tasks).
- Built code has a defect -> `bugfix`.
- Review/QA surfaced findings to fix -> `fix-findings`.

1. `/speckit.converge` -> assesses code vs spec/plan/tasks and appends the
   remaining work as new tasks under a `## Phase N: Convergence` heading in
   `tasks.md`. Append-only: it never edits spec/plan or existing tasks, and
   leaves `tasks.md` byte-for-byte unchanged when nothing is missing.
2. If it appended tasks, implement them via the agent-assign flow
   (`assign` -> `validate` -> `execute`), not `/speckit.implement`. Then re-run
   the Phase 3 QA steps.
3. If it reported clean, resume the QA step you came from.

## On Resume

1. Determine the last completed step; `/speckit.status.show` shows current
   spec state
2. Resume at the appropriate workflow step

## Command Reference

Commands outside the numbered workflow above.

### Tinyspec (small changes)
- `tinyspec.classify` -- classify a change as spec-worthy or tiny
- `tinyspec.tinyspec` -- lightweight spec for small changes
- `tinyspec.implement` -- execute a tinyspec task (only after
  tinyspec.classify -> tinyspec.tinyspec)

### Review
- `review.run` -- full review cycle (step 11b in the numbered workflow)
- `review.code` -- code review
- `review.tests` -- test review
- `review.types` -- type safety review
- `review.errors` -- error handling review
- `review.simplify` -- simplification review
- `review.comments` -- comment review

### Process
- `qa.run` -- QA cycle (step 11c in the numbered workflow)
- `fix-findings` -- fix issues from verify/review/qa
- `reconcile.run` -- reconcile divergent state
- `doctor.check` -- diagnose speckit health

### Diagrams
- `diagram.status` -- status diagram
- `diagram.dependencies` -- dependency diagram
- `diagram.workflow` -- workflow diagram

### Git/Worktree
- `worktree.create` -- create isolated worktree
- `worktree.list` -- list active worktrees
- `worktree.clean` -- clean up worktrees
- `archive.run` -- archive completed spec

### GitHub Issues
- `github-issues.link` -- link issues to spec
- `github-issues.sync` -- sync issue state
- `github-issues.import` -- import issues as tasks

### Brownfield
- `brownfield.scan` -- scan existing codebase
- `brownfield.validate` -- validate scan results
- `brownfield.bootstrap` -- bootstrap spec from scan
- `brownfield.migrate` -- migrate to speckit workflow

### Onboarding
- `onboard.start` -- start onboarding
- `onboard.explain` -- explain a concept
- `onboard.quiz` -- knowledge check
- `onboard.mentor` -- mentoring session
- `onboard.badge` -- award badge
- `onboard.trail` -- learning trail
- `onboard.team` -- team onboarding

### Optimization
- `optimize.run` -- optimization pass
- `optimize.tokens` -- token optimization
- `optimize.learn` -- learn from optimization

### Fleet
- `fleet.run` -- fleet operations
- `fleet.review` -- fleet review

### Refine
- `refine.update` -- refine spec
- `refine.diff` -- show refinement diff
- `refine.propagate` -- propagate refinement
- `refine.status` -- refinement status

### Governance
- `conduct.run` -- code of conduct check
- `constitution` -- constitution review
- `/architecture-decision-records` (skill, not a speckit command) -- record an ADR
  for every non-trivial decision, as `docs/adr/NNNN-title.md` (MADR). Continuous
  process; see the ADR rule under "Rules" above.
