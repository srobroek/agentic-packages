# /speckit.brownfield.validate — what to do next

## Going to
- /speckit.brownfield.migrate (if validation surfaces fixable gaps)
- /speckit.brownfield.bootstrap (if validation passes cleanly)

## Postconditions
- `.specify/brownfield-validation.json`

## Conditional branching
- If validation flags `migrate-required: false`, skip directly to bootstrap.
