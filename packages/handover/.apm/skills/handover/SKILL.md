---
name: handover
description: Save a self-contained recovery prompt in the shared handover store. Use when pausing work, switching context, or ending a session with incomplete work.
---

# Handover

Create a durable recovery prompt that `catchup` can read before doing fresh discovery.

## Workflow

1. Detect repo root, branch, and active worktree.
2. If the session changed architecture, introduced tech debt, or has open corrections → run `session-review` first.
3. Gather the current implementation state:
   - changed areas and incomplete work
   - active spec/task progress
   - architectural decisions made this session
   - open risks or blockers
   - next concrete steps
4. Invoke `scripts/new-handover.py` to scaffold the file in `~/.local/state/agentic-tools/handovers/`. Pass `--task` when a spec id, issue id, or user-stated task is known; otherwise let the script use the branch.
5. Replace the older handover for the same project/worktree/branch.
6. Verify the written file exists and is readable.
7. Tell the user where the handover was written and what the next session should load first.

## Rules

MUST The saved handover must be self-contained: no hidden chat context needed to resume.
MUST Include enough metadata for selection: repo root, worktree path, branch, timestamp, and task/spec/issue identifiers when present.
MUST Include a copy-pastable Next Session Prompt.
MUST Include Blockers, Verification / Commands, Runtime State, and Avoid / Do Not Redo sections, even when they say `None known`, `Not run`, or `None`.
MUST Before handing off, commit and push completed work to its remote branch — a handover is not a substitute for pushing. Never leave completed work only as uncommitted local state, especially in a disposable (`/tmp`) worktree.
MUST Record exact file paths and next steps, not vague summaries.
MUST Do not store secrets, tokens, or raw credential values.
MUST Never commit handover files — they are ephemeral local state.
DEFAULT Include a short Summary section with 2-4 factual bullets.
DEFAULT Use repo-relative plain paths for files inside the repo; absolute paths for repo root, worktree metadata, and external local-state paths.
DEFAULT Include task-local user corrections or latest explicit instructions in Decisions when they affect continuation.
DEFAULT When branch divergence or mid-rebase state would affect the next step, include commit hashes or branch-base details.
- Remove or replace TODO placeholders before reporting the handover complete.
- If work is mid-refactor, explain the incomplete state explicitly.
- Do not store volatile session state in global memory. Handover files are the session bridge.
- Do not write generated runtime copies or compiled agent files as part of handover creation.

## References

When structuring the handover file, LOAD references/template.md.

## Scripts

`scripts/new-handover.py` creates the shared handover directory, generates the filename and frontmatter, and writes the required markdown sections with user-private permissions where supported. If the script is unavailable, create the same file contract manually.
