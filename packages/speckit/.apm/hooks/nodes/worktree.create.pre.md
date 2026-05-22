# /speckit.worktree.create — before you run this

## Came from
- (parallel-work request from any implementation phase)

## Preconditions
- (none)

## Context absorbed from steering
- Spawns an isolated git worktree so parallel features don't trample each other. Pair with the worktree-isolation pattern in agent-assign.execute when running multiple agents.
