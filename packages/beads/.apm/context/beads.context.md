# Beads (bd)

SCOPE
MUST Use bd for persistent, multi-session, or multi-agent work tracking when
  the repo has `.beads/` (`bd where` succeeds).
DEFAULT TaskCreate stays for single-session scratch lists; SpecKit artifacts
  (spec.md/plan.md) stay the source for WHAT to build — beads tracks execution
  state, not requirements.
NOT `bd edit` — opens $EDITOR and blocks the agent; use `bd update` flags.

MEMORY
DEFAULT `bd remember "insight" --key <slug>` for repo-scoped durable facts any
  agent or tool must see (gotchas, conventions, decisions); every memory is
  injected verbatim via bd prime each session — keep the set ≤30, prune stale
  keys with `bd forget` during session review.
DEFAULT MemPalace keeps cross-session semantic recall; user/global knowledge
  stays in Claude auto-memory (see mempalace steering).

IDENTITY
MUST Set `--actor <agent-name>` (or BEADS_ACTOR) on every mutating command when
  acting as a named subagent; audit trails and claim ownership depend on it.

CLAIMING
MUST Claim before working: `bd update <id> --claim` (atomic; first wins,
  idempotent for the holder). Never edit an issue another actor holds.
MUST On refusal ("already assigned"), coordinate with the holder — never
  `bd unclaim --force` a live claim; `--force` is for abandoned claims only.
DEFAULT Discover work with `bd ready --json`; release with
  `bd update <id> --status open` + clearing assignee.

STRUCTURE
| need | mechanism |
|---|---|
| workflow state | structured fields (status/priority/type) — never labels |
| categorical filtering | labels, lowercase-hyphenated, 5–10 core per repo |
| operational state cache | `bd set-state <id> dim=value --reason`; query `bd state` |
| machine routing hints | `--metadata` JSON, namespaced keys (`execution_*` convention) |
| rationale/prose | description + notes, never labels or metadata |
| requirements linkage | `--spec-id` + `discovered-from` deps |

DEPENDENCIES
DEFAULT `blocks` for ordering; `parent-child` for epics; `discovered-from` for
  follow-up work found mid-task; non-blocking types (`related`, `tracks`) never
  affect `bd ready`.
MUST Model fan-in with an aggregate issue depending on each part, not comments.

FINDINGS
DEFAULT Any skill or review that ends with findings the session will not act on
  (audit reports, deferred review items, advisory bumps, failed checks at
  handoff) files them as beads — `bd create` with `discovered-from` the active
  bead, one per finding, machine keys (CVE id, PR number, file:line) in
  metadata so re-runs dedupe instead of re-reporting.

JSON DETERMINISM
MUST Scripts and hooks parsing bd output set `BD_JSON_ENVELOPE=1` and read
  `.data` / `.error` + `schema_version`; agents reading ad hoc may use bare
  `--json`.
DEFAULT Non-interactive contexts export `BD_NO_PAGER=1 BD_NON_INTERACTIVE=1`.

SYNC
MUST End sessions that mutated beads with `bd dolt push` (issue data rides
  `refs/dolt/data`, NOT git commits; `git push` alone syncs nothing).
NOT Routine `bd import` of issues.jsonl — it is upsert-only passive export;
  `bd dolt pull` is the sync path.

SESSION CLOSE (when beads were touched)
MUST File beads for remaining/discovered work before reporting done, close
  finished issues with `--reason`, update in-progress state, then `bd dolt push`.
DEFAULT Git commit/push of code follows delivery steering, not bd's profiles.

SETUP
MUST Wire hooks natively, once, globally: `bd setup claude --global` (hook
  only) and `bd setup codex --global`; per repo, `bd init` only.
NOT Per-project `bd setup claude` — it appends a managed CLAUDE.md block that
  duplicates this steering and fights `apm compile`.
