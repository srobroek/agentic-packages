# /speckit.doctor.check — what to do next

## Going to
- (return to whatever phase you were in)

## Postconditions
- (no artefact; report printed to stdout)

## Conditional branching
- If doctor flags missing extensions or stale workflows, run `speckit-upgrade-project` (fish) to refresh `.specify/` and `specify extension update` to refresh extensions.
