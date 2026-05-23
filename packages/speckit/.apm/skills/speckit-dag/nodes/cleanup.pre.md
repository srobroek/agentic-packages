# /speckit.cleanup — before you run this

## Came from
- /speckit.code-review + /speckit.security-review (both clean)
- /speckit.qa.run (acceptable if code/security review skipped)

## Preconditions
- SOFT: implementation diff present

## Context absorbed from steering
- Post-impl hygiene: dead-code removal, unused imports, debug statements. Our override enables aggressive dead-code removal.
