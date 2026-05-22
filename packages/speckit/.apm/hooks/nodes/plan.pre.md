# /speckit.plan — before you run this

## Came from
- /speckit.checklist (preferred)
- /speckit.memory-md.plan-with-memory (preferred when memory-md installed)
- /speckit.clarify (acceptable if checklist skipped)

## Preconditions
- HARD-MISSING: specs/<feat>/spec.md
- HARD-EXISTS: specs/<feat>/plan.md
- SOFT: specs/<feat>/clarifications.md
- SOFT: specs/<feat>/memory-synthesis.md (when memory-md installed)

## Context absorbed from steering
- Full SpecKit projects keep `.specify/` workflow assets separate from durable project docs in `docs/`.
- If memory-md is installed and `memory-synthesis.md` is missing, STOP and run `/speckit.memory-md.plan-with-memory` first.
- If `plan.md` already exists, use `/speckit.refine.update` to amend rather than re-planning from scratch.
