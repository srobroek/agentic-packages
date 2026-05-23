# /speckit.memory-md.init — before you run this

## Came from
- (project bootstrap, once — see project-setup SKILL.md step 10)

## Preconditions
- (none; this is the entry point that creates docs/memory/)

## Context absorbed from steering
- Idempotent. Re-running this command no-ops if `docs/memory/INDEX.md` already exists.
- Invoked once per project after `specify init` + extension install. Subsequent feature cycles use `/speckit.memory-md.plan-with-memory`.
