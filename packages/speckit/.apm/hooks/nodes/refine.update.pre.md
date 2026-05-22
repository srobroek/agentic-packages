# /speckit.refine.update — before you run this

## Came from
- /speckit.specify · /speckit.clarify · /speckit.checklist · /speckit.plan · /speckit.critique.run · /speckit.tasks · /speckit.diagram.dependencies · /speckit.analyze · /speckit.taskstoissues
- /speckit.reconcile.reconcile
- (any phase before /speckit.checkpoint.commit)

## Preconditions
- HARD-MISSING: specs/<feat>/spec.md

## Context absorbed from steering
- Refine is for INCREMENTAL edits to existing artefacts. If the change is actually a scope pivot, exit refine and run `/speckit.iterate.define` or specify a new feature.
- After `/speckit.checkpoint.commit`, drift handling moves to `/speckit.reconcile.reconcile` instead.
