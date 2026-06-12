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
and "parallel with" pairs run concurrently. Steps 10-13 start only after 9c
completes; all four must finish before 14. Scope changes route through iterate
(below) and resume at the triggering step.

### Phase 1 -- Specification (human-gated)

| Step | Command | Mode | Notes |
|------|---------|------|-------|
| 1 | `/speckit.specify` | auto -> approval | Creates spec.md |
| 2 | `/speckit.clarify` | interactive | Ask questions, incorporate feedback |
| 3 | `/speckit.checklist` | interactive | Quality gate on requirements |
| 4 | `/speckit.plan` | auto -> approval | Architecture and approach |
| 5 | `/speckit.tasks` | auto -> approval | Task breakdown with dependencies |
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
| 10 | `/speckit.verify-tasks` | parallel with 11 | Subagent, fresh context; phantom completion detection |
| 11 | `/speckit.verify` | parallel with 10 | Subagent; validate code against spec |
| 12 | `/speckit.code-review` | parallel with 13 | Subagent |
| 13 | `/speckit.security-review` | parallel with 12 | Subagent |
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
6. `/speckit.checkpoint.commit`
7. Resume at the step where the change was triggered

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
- `review.run` -- full review cycle
- `review.code` -- code review
- `review.tests` -- test review
- `review.types` -- type safety review
- `review.errors` -- error handling review
- `review.simplify` -- simplification review
- `review.comments` -- comment review

### Process
- `qa.run` -- QA cycle
- `fix-findings` -- fix issues from verify/review/qa
- `reconcile.reconcile` -- reconcile divergent state
- `doctor.check` -- diagnose speckit health

### Memory
- `memory-md.init` -- initialize layered memory
- `memory-md.capture` -- capture findings to memory
- `memory-md.capture-from-diff` -- capture from git diff
- `memory-md.prepare-context` -- load relevant memory before work
- `memory-md.plan-with-memory` -- plan using memory context
- `memory-md.log-finding` -- log a single finding
- `memory-md.audit` -- audit memory health
- `memory-md.token-report` -- memory token usage
- `memory-md.share-lesson` -- share lesson across projects
- `memory-md.sync-shared` -- sync shared lessons

### Diagrams
- `diagram.status` -- status diagram
- `diagram.dependencies` -- dependency diagram
- `diagram.workflow` -- workflow diagram

### Git/Worktree
- `worktree.create` -- create isolated worktree
- `worktree.list` -- list active worktrees
- `worktree.clean` -- clean up worktrees
- `archive.archive` -- archive completed spec

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
- `fleet.fleet` -- fleet operations
- `fleet.review` -- fleet review

### Refine
- `refine.update` -- refine spec
- `refine.diff` -- show refinement diff
- `refine.propagate` -- propagate refinement
- `refine.status` -- refinement status

### Governance
- `conduct.conduct` -- code of conduct check
- `constitution` -- constitution review
