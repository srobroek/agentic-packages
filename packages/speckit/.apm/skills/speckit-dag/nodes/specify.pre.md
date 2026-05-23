# /speckit.specify — before you run this

## Came from
- /speckit.constitution
- (project bootstrap)
- /speckit.github-issues.import
- /speckit.brownfield.bootstrap
- /speckit.refine.status (mandatory re-entry from refine loop)
- /speckit.iterate.apply (mandatory re-entry from iterate)

## Preconditions
- SOFT: `.specify/memory/constitution.md`

## Context absorbed from steering
- For minimal scope, prefer `/speckit.tinyspec.classify` — heavier `/speckit.specify` is overkill for trivial work. For a bug, `/speckit.bugfix.report` is the right entry.
- If re-entered from `/speckit.refine.status` or `/speckit.iterate.apply`, walk briefly through every downstream stage to assess impact rather than restarting from scratch.
