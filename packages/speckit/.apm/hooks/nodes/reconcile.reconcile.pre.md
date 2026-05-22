# /speckit.reconcile.reconcile — before you run this

## Came from
- (drift detected — any post-checkpoint phase where spec ↔ implementation diverged)
- /speckit.sync.conflicts

## Preconditions
- SOFT: specs/<feat>/sync-report.md

## Context absorbed from steering
- After /speckit.checkpoint.commit, refine and iterate are no longer appropriate — reconcile is the drift-handling tool because it updates the spec to match the as-shipped implementation.
