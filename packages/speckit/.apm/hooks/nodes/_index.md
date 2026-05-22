# SpecKit DAG node index

Each `<id>.pre.md` and `<id>.post.md` declares the lifecycle position
of `/speckit.<id>` for the dispatcher at
`packages/speckit/.apm/hooks/scripts/dispatcher.sh`.

## File contents per phase

`<id>.pre.md` — Pre-tool phase. Read by the dispatcher on
`UserPromptExpansion` (Claude), `UserPromptSubmit` (Codex), and
`PreToolUse` (both). Contains:

- **Came from** — legitimate predecessors with preferred / acceptable
  annotations. Class-based entries appear in parentheses
  (e.g., "any active implementation phase").
- **Preconditions** — `HARD-MISSING:` / `HARD-EXISTS:` /
  `HARD-DEPRECATED:` lines (block the invocation) and `SOFT:` lines
  (advisory only).
- **Context absorbed from steering** — optional; carries any prose
  from previously-scattered steering docs that pertains to this
  command.

`<id>.post.md` — Post-tool phase. Read by the dispatcher on
`PostToolUse` (both runtimes; on Codex only when the slash command
actually goes through a tool surface). Contains:

- **Going to** — legitimate successors with default / conditional
  annotations.
- **Postconditions** — files this command is expected to produce.
- **Conditional branching** — if/then guidance.
- **Context absorbed from steering** — optional.

## Hard-block evaluation

Lines beginning `HARD-DEPRECATED:` always block.
Lines `HARD-MISSING: <path>` block when `<path>` (after `<feat>`
substitution) does NOT exist.
Lines `HARD-EXISTS: <path>` block when `<path>` (after `<feat>`
substitution) DOES exist.

`<feat>` resolves from `.specify/feature.json` (SpecKit's canonical
current-feature pointer) — specifically the trailing path component
of `feature_directory`. The dispatcher uses `$CLAUDE_PROJECT_DIR` if
set, otherwise the current working directory, to locate
`feature.json`. When no `feature.json` exists (e.g., very early in
project setup), `<feat>` stays empty and `HARD-MISSING` /
`HARD-EXISTS` checks that reference it become no-ops.
`HARD-DEPRECATED` still fires unconditionally regardless of feature
resolution.

## Class-based predecessors / successors

Entries in parentheses — e.g., `(any active implementation phase)`,
`(any phase before /speckit.checkpoint.commit)`, `(return to invoker)`
— are informational for the agent. The dispatcher does not validate
class membership; it just shows the text. The agent uses judgement.

## Total

~75 commands × 2 phases = ~150 markdown files. 1 carries
`HARD-DEPRECATED` (`implement.pre.md` — `/speckit.implement` is
deprecated; redirect to the `/speckit.agent-assign.*` trio).
