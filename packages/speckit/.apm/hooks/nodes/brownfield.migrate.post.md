# /speckit.brownfield.migrate — what to do next

## Going to
- /speckit.brownfield.bootstrap (default)

## Postconditions
- (project file mutations per the validation report)

## Conditional branching
- If migrate touched anything risky, run `/speckit.doctor.check` before bootstrap.
