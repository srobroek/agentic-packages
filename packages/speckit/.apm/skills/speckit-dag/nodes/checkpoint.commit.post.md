# /speckit.checkpoint.commit — what to do next

## Going to
- /speckit.agent-assign.assign (after the mid-cycle checkpoint that follows taskstoissues)
- /speckit.archive.archive (after the final checkpoint that follows retro.run)
- (next phase per workflow)

## Postconditions
- git commit (+ tag for the final checkpoint)

## Conditional branching
- After `checkpoint.commit`, drift handling moves from `/speckit.refine.update` / `/speckit.iterate.define` to `/speckit.reconcile.reconcile`.
