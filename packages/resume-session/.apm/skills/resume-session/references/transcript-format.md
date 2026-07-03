# Transcript Format & Reading Strategy

Reference for the two scripts. Stable details about where agent transcripts
live, their record schemas, and the filtering/paging the scripts apply so the
agent reconstructs the leftoff state without loading full history.

## Store locations

### Claude Code
- One JSONL file per session: `~/.claude/projects/<encoded-project>/<session-id>.jsonl`.
- The project directory name encodes the absolute repo path by replacing every
  `/` and `.` with `-`. Example: `/home/user/.config/fish` →
  `-home-user--config-fish` (note the double dash from `/.config`).
- The filename stem is the canonical session id (what `claude --resume` uses). A
  file may contain more than one `sessionId` value when a session was
  forked/resumed; the stem still identifies it.

### Worktrees: one transcript family, many project dirs
- Each git worktree (the main checkout and every linked worktree) has its own
  working directory, so each encodes to a **different** `~/.claude/projects/<encoded>`
  dir, and Codex rollouts are tagged with that worktree's `cwd`. A session
  started in one worktree therefore does not appear under another worktree's
  encoded dir.
- `git worktree list --porcelain` returns the **whole** worktree family from any
  member — the main checkout (always listed first) and every linked worktree —
  so the result is identical whether the skill starts in the main repo or in a
  linked worktree. Both of the user's cases ("started in a worktree" / "started
  in the parent") reduce to: enumerate the family, scan every member.
- `list-sessions.py` enumerates the family and scans each member's transcript
  dir, tagging every session with its worktree (`wt_path`/`wt_branch`). For
  Codex it walks the rollout tree **once** and matches each rollout's `cwd`
  against the set of worktree paths (a per-worktree walk would rescan the whole
  tree N times). Prunable / on-disk-missing worktrees are skipped.
- `read-session.py` resolves a bare session id across **all** worktree project
  dirs (`worktree_projects()`), so a session picked from a sibling worktree opens
  without `--project`. An id prefix that matches transcripts in more than one
  worktree is reported as ambiguous.
- `--no-worktrees` (list only) restricts the scan to the current checkout.

### Codex
- Rollups under `~/.codex/sessions/<YYYY>/<MM>/<DD>/rollout-<ts>-<session-id>.jsonl`.
- The working directory is not in the path; it lives in the first record's
  `session_meta.payload.cwd`. `list-sessions.py` reads that first record and
  skips files whose `cwd` does not match the target project before scanning the
  body.

## Record schema (essentials)

### Claude (`type` field per line)
- `user`: `message.content` is a string (real prompt) **or** a list of blocks. A
  list containing a `tool_result` block is tool output, not a user turn — the
  scripts attach a truncated result to the preceding assistant tool instead of
  treating it as a prompt.
- `assistant`: `message.content` is a list of blocks: `text`, `thinking`
  (filtered unless `--include-thinking`), and `tool_use` (`name` + `input`).
- `ai-title`: `aiTitle` — a short human title for the session (used as the list
  title when present).
- Each record also carries `cwd`, `gitBranch`, `version`, and `timestamp`.
- Other types (`mode`, `permission-mode`, `attachment`, `file-history-snapshot`,
  `last-prompt`) are ignored.

### Codex (`type` + `payload`)
- `session_meta`: `payload.id`, `payload.cwd`, `payload.cli_version`, timestamp.
- `event_msg` with `payload.type == "user_message"`: a user turn (`message`).
- `event_msg` with `payload.type == "agent_message"`: an assistant turn.
- `response_item` with `payload.type` in `function_call` / `local_shell_call` /
  `custom_tool_call`: a tool call, attached to the current assistant turn.
- `response_item` `reasoning`: filtered unless `--include-thinking` (content is
  usually encrypted anyway).
- `update_plan` function calls are parsed into the plan/todo state.

## Leftoff signal: plan / todo state

The single most useful signal is the latest task plan. `read-session.py` scans
the whole file for the last `TodoWrite` (Claude) or `update_plan` (Codex) call
and renders it at the top regardless of the current window, with glyphs:
`[x]` completed, `[~]` in progress, `[ ]` pending.

## Leftoff signal: per-worktree git activity

Transcript recency answers "which session was last active"; git activity answers
"which worktree is the live one". When more than one worktree exists,
`list-sessions.py` prints a **Worktree git activity** block (most recently
committed first) before the session list:

- One `git show -s --format=%H<NUL>%ct<NUL>%s <head>...` call resolves every
  worktree HEAD's commit epoch + subject in a single batch.
- Each row shows the worktree, its branch, the last-commit relative + absolute
  time, the commit subject, and a `✎ dirty` flag when
  `git status --porcelain` reports uncommitted changes.
- A recently-committed or dirty worktree is a strong hint for where work is
  ongoing — pair it with the session list's `↳ left off:` to pick the right
  thread. `--no-git` skips this block.

## Filtering (what the scripts strip)

Emitted output keeps only: real user prompts, assistant text, tool calls (name
+ a brief of the salient argument), truncated tool results, session metadata,
and the latest plan/todo state. Stripped or truncated: thinking/reasoning,
base64 attachments, encrypted content, and oversized tool output. Per-turn text
is capped (`TURN_CHARS`), as are tool args and results.

## Incremental paging

`read-session.py` renders a window **newest turn first**, so the most recent
state is read first and the agent can stop early. Empty turns (thinking-only)
are dropped. The window is also hard-capped by `--max-chars`; if a single window
would exceed it, rendering stops and the footer says so.

To go further back, the footer prints the exact next command using `--offset`
(turns to skip from the newest) and `--turns` (window size). Page back **only**
until the leftoff state is clear — never to the start of the session.

## Resume cost reporting

Both scripts end with an estimated **uncached** token count for what they
emitted (~4 chars/token). Because each window is freshly generated, all of it is
uncached input — that figure is the real context cost of the resume. The agent
sums the windows it actually read and reports the total against the full
transcript size, which is the whole point: a few thousand tokens instead of the
entire history.

## Script reference

- `list-sessions.py [--project PATH] [--agent claude|codex|all] [--limit N]
  [--no-worktrees] [--no-git] [--json]` — selectable table, newest first, across
  all worktrees of the repo by default; precedes it with a per-worktree git
  activity block when more than one worktree exists. `--no-worktrees` scans only
  the current checkout; `--no-git` drops the git block; `--json` emits
  `{project, worktrees[], sessions[]}` for machine output.
- `read-session.py (--session ID | --file PATH) [--project PATH] [--agent ...]
  [--turns N] [--offset M] [--max-chars N] [--include-thinking]` — filtered,
  newest-first window with metadata, latest plan, and a paging footer. A bare
  `--session` id resolves across every worktree of the repo.
