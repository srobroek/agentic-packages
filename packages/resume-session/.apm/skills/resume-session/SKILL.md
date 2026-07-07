---
name: resume-session
description: Resume a prior agent session from its transcript. Triggers on "resume my session", "resume session <id>", "continue my last session".
---

# Resume Session

Reconstruct where a prior agent session left off using this skill's two scripts
for ALL discovery and reading, with two mandatory stops: **the user chooses the
session**, and **the user confirms before any work resumes**.

## Non-negotiable rules

MUST Use `scripts/list-sessions.py` and `scripts/read-session.py` for everything. Never identify sessions by reading `.jsonl` files, running `cat`/`tail`/`grep` on transcripts, or running `git log` yourself.
MUST Load **exactly one** session — the one the user picks. Never read a second session's transcript.
MUST The two STOP gates below are hard. Until gate 1 is cleared, only listing sessions is allowed. Until gate 2 is cleared, do not read files, run git, or start work.
MUST Session cwd in a different worktree than yours → confirm target worktree with the user before reading or editing any files.

## Workflow

1. **List sessions — your first and only action so far.** Run
   `python3 scripts/list-sessions.py` (auto-detects git repo root; pass
   `--project PATH` for another repo, `--agent claude|codex` to narrow). It
   prints a newest-first summary: id, agent, last-active, turns, branch,
   `worktree:`, title, and a `↳ left off:` line.
   - **Worktree-aware by default.** Enumerates every worktree (`git worktree list`)
     and scans each one's transcripts. Pass `--no-worktrees` to scan only current.
   - **Git-activity overview.** When the repo has more than one worktree, also
     prints a "Worktree git activity" block (most-recently committed first) with
     branch, last-commit time + subject, and a `✎ dirty` mark. Pass `--no-git` to skip.

2. **STOP. Present the list and let the user choose.** Show the newest few rows
   including `worktree:` and `↳ left off:` lines, and ask which to resume.
   You may recommend, but **wait for their answer** — do not pick for them.
   - Only exception: if the user already gave a session id, skip to step 3.

3. **Read that one session.** Run
   `python3 scripts/read-session.py --session <id>` (newest 8 turns, filtered,
   newest-first). Anchor on the **Latest plan / todo state** block. Stop reading
   when you can state what was being done and what remains. Page back with
   `--offset N --turns N` if still unclear. Never open another session.

4. **STOP. Summarize, surface ambiguities, and ask.** State: the goal, the last
   action, current todo/plan state, branch/cwd, and what is incomplete. List
   unrecorded decisions, half-done work, or paths that may be stale. Ask for
   confirmation and any new direction. **Wait.**

5. **Resume.** Only after the user confirms: run a quick reality check
   (`git status`, branch, referenced files exist), then continue from the agreed
   next step.

## Notes

- Current user instructions override anything in the transcript; it is evidence of the past.
- Do not silently re-run destructive or outward-facing actions (commits, pushes, deploys) — reconfirm first.
- Each script prints an estimated uncached-token cost; report the total used vs. full transcript size.
- Add `--include-thinking` only when the text record shows a logic gap, incomplete sentence, or unexplained branch that tool calls alone cannot resolve.
- This skill resumes a session transcript; it does not read saved handover files.

See `references/transcript-format.md` for store locations, record schema, and filtering/paging.
