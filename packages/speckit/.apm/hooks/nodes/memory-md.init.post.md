# /speckit.memory-md.init — what to do next

## Going to
- /speckit.constitution (preferred for greenfield)
- /speckit.specify (acceptable if constitution already exists)
- (return to bootstrap workflow)

## Postconditions
- `docs/memory/INDEX.md`
- `docs/memory/{ARCHITECTURE,BUGS,DECISIONS,WORKLOG,PROJECT_CONTEXT}.md`
- `.specify/memory/{constitution,architecture_constitution,DECISIONS,BUGS}.md` (templates)

## Conditional branching
- If `constitution.md` already exists, skip `/speckit.constitution` and go directly to `/speckit.specify`.
