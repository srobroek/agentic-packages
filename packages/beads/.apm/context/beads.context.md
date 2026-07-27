# Beads (bd)

SCOPE
MUST Use bd for all task tracking when the repo has `.beads/` (`bd where`
  succeeds); do not use TaskCreate or markdown task lists.
DEFAULT SpecKit artifacts (spec.md/plan.md) stay the source for WHAT to build;
  beads tracks execution state, not requirements.
NOT `bd edit` -- opens $EDITOR and blocks the agent; use `bd update` flags.

MEMORY
DEFAULT `bd remember "insight" --key <slug>` for repo-scoped durable facts any
  agent or tool must see (gotchas, conventions, decisions); every memory is
  injected verbatim via bd prime each session -- keep the set ≤30, prune stale
  keys with `bd forget` during session review.
DEFAULT MemPalace keeps cross-session semantic recall; user/global knowledge
  stays in Claude auto-memory (see mempalace steering).

IDENTITY
MUST Set BEADS_ACTOR (`<harness>/<agent-name>/<session-id>`) on every mutating
  command when acting as a subagent -- the session id distinguishes dead claims.
DEFAULT BD_ACTOR is legacy (Beads 1.1.0 commit trailer only); export the same
  value in both until the hook accepts BEADS_ACTOR.

CLAIMING
MUST Claim before working: `bd update <id> --claim` (atomic CAS; first wins,
  idempotent). Never claim via labels -- not atomic.
MUST Discover work with `bd ready --unassigned --json`; never pick up work
  assigned to another actor unless the parent hands you its id.
MUST On refusal, coordinate with holder; `bd unclaim --force` only after
  confirming the holding session is dead.
DEFAULT Release with `bd unclaim <id>`.

FIELD TAXONOMY
| purpose | mechanism | writer |
|---|---|---|
| lifecycle | status (open/in_progress/blocked/deferred/closed) | worker |
| ownership | assignee (atomic via `--claim`) | worker |
| urgency | priority 0 to 4 | orchestrator/user |
| work kind | type (bug/feature/task/epic/chore) | creator |
| bounce-back | fix bead `discovered-from` + `bd dep add` + comment; release | integrator |
| routing queue | label `agent:<name>` | orchestrator/formula |
| group dispatch | assignee = pool alias (`claim.pools`) | orchestrator |
| category | labels, lowercase-hyphenated, ≤10/repo | any |
| state cache | `bd set-state <id> dim=value --reason` | owning agent |
| execution hints | metadata `execution_*` (type, model, effort, group) | orchestrator, BEFORE spawn |
| git anchors | metadata (repo, branch, base_sha, worktree, pr, merge_sha) | worker/integrator |
| scope globs | metadata `scope` | orchestrator |
| dedupe keys | metadata (CVE, PR#, file:line) | finder skills |
| rationale | description + notes, never labels/metadata | any |
| requirements | `--spec-id` + `discovered-from` deps | creator |

ROUTING
DEFAULT Workers poll `bd ready --label agent:<kind> --unassigned --json` and
  `--claim` what they take; labels route by KIND, assignee pins INSTANCE.
MUST Orchestrators set routing labels and `execution_*` metadata at creation --
  model/effort are fixed at spawn, too late after delegation.
NOT Labels as locks or gate substitutes -- gate beads + `bd gate check` own
  blocking waits; `bd set-state` is non-blocking only.

DEPENDENCIES
DEFAULT `blocks` for ordering; `parent-child` for epics; `discovered-from` for
  follow-up work found mid-task; non-blocking types (`related`, `tracks`) never
  affect `bd ready`.
MUST Model fan-in with an aggregate issue depending on each part, not comments.

WORKFLOWS
DEFAULT Read only the relevant workflow contract:
- [Carriers: comments, decision beads, wisps, artifacts](beads.carriers.context.md)
- [Lifecycle and gates](beads.lifecycle.context.md)
- [Semantic audit and reporting](beads.audit.context.md)
- [Formulas, molecules, bonds, and wisps](beads.composition.context.md)
- [Swarms and merge slots](beads.coordination.context.md)
- [Orchestration doctrine: claim⟺contract, wisps, links, labels, gates](beads.orchestration-doctrine.context.md)

FINDINGS
DEFAULT Unactioned findings (audits, deferred items, failed checks) become beads
  via `bd create --discovered-from <active>`, one per finding, with machine keys
  (CVE, PR#, file:line) in metadata for dedupe.

JSON DETERMINISM
MUST Scripts and hooks parsing bd output set `BD_JSON_ENVELOPE=1` and read
  `.data` / `.error` + `schema_version`; agents reading ad hoc may use bare
  `--json`.
DEFAULT Non-interactive contexts export `BD_NO_PAGER=1 BD_NON_INTERACTIVE=1`.

SYNC
MUST `bd dolt pull`/`push` only with explicit sync authority from user,
  repo config, or orchestrator; `git push` does not sync `refs/dolt/data`.
DEFAULT Local: no routine pull; one push at orchestrator handoff.
DEFAULT Cross-machine: one pull before fan-out, one push after updates.
NOT `bd import` of issues.jsonl by hand -- `bd dolt pull` is the sync path,
  and in a JSONL-over-git repo (below) the hooks own both halves.

JSONL OVER GIT (fallback where `bd dolt push` cannot run)
DEFAULT Off. `bd dolt push` stays the sync path; this exists for repos where it
  is blocked -- it writes `refs/dolt/blobstore/`, which corporate push guards
  reject as an unapproved-remote push and which needs credentials Dolt cannot
  prompt for.
MUST Opt in per repo with `bd config set custom.jsonl-git-sync true`, commit
  `.beads/issues.jsonl merge=union` to `.gitattributes`, and confirm the file is
  not git-ignored (a stealth `bd init` excludes `.beads/` via
  `.git/info/exclude`, which makes `git add` fail silently).
MUST Leave both halves to the hooks: `beads-jsonl-export.sh` refreshes and
  stages the file on `git commit`, `beads-jsonl-import.sh` hydrates at session
  start. Neither commits; the agent's own commit carries the file.
DEFAULT Trust the importer's resolution: newer `updated_at` wins, ties keep
  local, comments/labels/dependencies merge, local-only beads are never deleted,
  and stale rows are skipped and reported. `union` deliberately leaves duplicate
  ids in the file for the importer to resolve.
NOT `--allow-stale` unless deliberately restoring an older snapshot -- it
  overwrites newer local state.
MUST On a stale-skip warning at session start, commit a fresh export before
  pulling peer changes: the committed file is behind the local database, so the
  next export would overwrite what a peer committed.
NOT A substitute for `bd dolt push` where that works -- export carries issue
  records only, no Dolt branches, commit history, or non-issue tables.

GITHUB MIRROR -- see [beads.github-mirror.context.md](beads.github-mirror.context.md)

SESSION CLOSE (when beads were touched)
MUST File beads for remaining/discovered work, close finished with `--reason`.
MUST Before closing a bead whose work continues elsewhere, write residual
  context onto it (`bd comments add`: approach, tricky spots, failure triage) --
  the bead is the handover, not PR bodies.
MUST Verify landed work by content per GW-3 (git-workflow steering).
DEFAULT Git commit/push follows delivery steering; sync per SYNC rules above.

SETUP -- see [beads.setup.context.md](beads.setup.context.md)
