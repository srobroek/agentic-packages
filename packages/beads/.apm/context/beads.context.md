# Beads (bd)

SCOPE
MUST Use bd for persistent, multi-session, or multi-agent work tracking when
  the repo has `.beads/` (`bd where` succeeds).
NOT Track tasks in markdown task lists — use bd issues instead.
DEFAULT TaskCreate stays for single-session scratch lists; SpecKit artifacts
  (spec.md/plan.md) stay the source for WHAT to build — beads tracks execution
  state, not requirements.
NOT `bd edit` — opens $EDITOR and blocks the agent; use `bd update` flags.

QUICK REFERENCE
  bd ready                # find available work
  bd show <id>            # view issue details
  bd update <id> --claim  # claim work (atomic)
  bd close <id>           # complete work
  bd prime                # refresh Beads context into session

MEMORY
DEFAULT `bd remember "insight" --key <slug>` for repo-scoped durable facts any
  agent or tool must see (gotchas, conventions, decisions); every memory is
  injected verbatim via bd prime each session — keep the set ≤30, prune stale
  keys with `bd forget` during session review.
MUST Run `bd prime` when Beads context is missing or stale before issuing bd
  commands; Codex 0.129.0+ loads it automatically via native hooks — use
  `/hooks` in Codex to inspect or toggle them.
DEFAULT MemPalace keeps cross-session semantic recall; user/global knowledge
  stays in Claude auto-memory (see mempalace steering).

IDENTITY
MUST Set BEADS_ACTOR (`<harness>/<agent-name>/<session-id>`) on every mutating
  command when acting as a subagent; audit trails and claim ownership depend
  on it, and the session id distinguishes dead claims from live ones.
MUST Keep the exact BEADS_ACTOR value for the full live claim and use it as the
  actor on messages, comments, and audit events; recovery assigns a new value
  only after the prior holder is proven dead or releases the claim.

CLAIMING
MUST Claim before working: `bd update <id> --claim` (atomic compare-and-swap;
  first wins, idempotent for the holder). Never claim via labels — labels are
  not atomic and bypass anti-steal protection.
MUST Discover work with `bd ready --unassigned --json`; never pick up an issue
  assigned to another actor unless the parent explicitly hands you its id.
MUST On claim refusal ("already assigned"), coordinate with the holder;
  `bd unclaim --force` only after confirming the holding session is dead
  (stale heartbeat or gone) — it is the abandoned-claim escape hatch.
DEFAULT Release with `bd unclaim <id>` (assignee cleared, status open).

FIELD TAXONOMY
| purpose | mechanism | who writes |
|---|---|---|
| lifecycle | status (open/in_progress/blocked/deferred/closed) — never phase/role | claiming worker |
| live ownership | assignee (structured field, atomic via `--claim`) | claiming worker |
| urgency | priority 0–4 | orchestrator/user only |
| work kind | type (bug/feature/task/epic/chore) | creator |
| bounce-back (integrator → author) | fix bead `discovered-from` + `bd dep add <merge> <fix>` + comment; release claim | integrator |
| routing queue (agent kind) | label `agent:<name>` | orchestrator/formula only |
| group dispatch | assignee = pool alias (`claim.pools`) | orchestrator |
| category/component | labels, lowercase-hyphenated, ≤10 per repo | any agent |
| operational state cache | `bd set-state <id> dim=value --reason` | owning agent, own bead |
| execution hints (agent type, model tier, effort, parallel group) | metadata `execution_*` | orchestrator, BEFORE spawn |
| git anchors (repo, branch, base_sha, worktree, pr, merge_sha) | metadata | worker at claim (branch/worktree); integrator (pr/merge_sha) |
| scope globs for disjointness | metadata `scope` | orchestrator |
| dedupe keys (CVE, PR#, file:line) | metadata | finder skills |
| rationale/prose | description + notes, never labels/metadata | any agent |
| requirements linkage | `--spec-id` + `discovered-from` deps | creator |

ROUTING
DEFAULT Pull-queue by kind: workers poll
  `bd ready --label agent:<kind> --unassigned --json` and `--claim` what they
  take; labels route by KIND, assignee pins an INSTANCE, pool alias dispatches
  to a group.
MUST Orchestrators set routing labels and `execution_*` metadata at creation
  or pour time — model/effort are fixed at spawn, too late after delegation.
NOT Labels as locks (assignee owns "taken") or as gate substitutes (no
  `ci:green`/`pr:merged` labels — gate beads + `bd gate check` own blocking
  waits; `bd set-state` is for non-blocking dimensions only).

DEPENDENCIES
DEFAULT `blocks` for ordering; `parent-child` for epics; `discovered-from` for
  follow-up work found mid-task; non-blocking types (`related`, `tracks`) never
  affect `bd ready`.
MUST Model fan-in with an aggregate issue depending on each part, not comments.

COORDINATION
DEFAULT Use native message wisps with non-blocking `replies-to` edges for live
  threads: a root replies to its work bead; a reply targets an open message in
  the same run and work context.

MUST Treat harness notification as an advisory wake only; the recipient reads
  the Beads thread after resume, and a failed wake does not remove the message.

NOT Require Gas Town, a daemon or poll loop, or a replacement routing queue for
  threaded coordination; harness delivery and existing claim routing stay
  separate from Beads persistence.

MUST Promote a material message before acting on it or closing work: a choice
  local to one bead becomes an actor-attributed comment; a choice affecting
  another bead, agent, package, shared contract, ordering rule, or later work
  becomes a linked `decision` bead.

MUST Give each decision bead a run-unique `decision_key`, one
  `decision_owner`, a `decision_disposition`, objective acceptance evidence,
  and non-blocking `relates-to` links to affected work; use `validates` links
  for work that supplies or checks the evidence.

NOT Treat message wisps or artifact files as policy; comments and decision
  beads remain authoritative after acknowledgement, compaction, or restart.

AMBIGUITY
MUST Record `owner`, `scope`, `evidence`, `unknown`, `default`, `bounds`, and
  `revisit` before applying an autonomous default; local records are comments,
  while cross-boundary records use decision metadata `ambiguity_<field>`.

DEFAULT Apply a recorded default only when it is reversible, local to the
  bead's owned resources, bounded, and compatible with accepted evidence and
  user intent; otherwise hold for one exact human decision.

MUST Make `revisit` an objective event, evidence change, dependency transition,
  or RFC3339 deadline; when it fires, the owner re-reads the cited evidence and
  records resolution before further use of the default.

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
DEFAULT Architecture: issues live in a local Dolt DB; sync uses
  `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive
  export only. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md
  for details and anti-patterns.

GITHUB MIRROR (only where beads mirror out to GitHub issues)
MUST Mirror with `bd github push <ids>`, never by hand-creating the issue —
  the push records the `External:` back-link on the bead, so a hand-made issue
  leaves the two unlinked. `--dry-run` first.
DEFAULT Supply credentials per invocation
  (`GITHUB_TOKEN="$(gh auth token)" GITHUB_REPOSITORY=<owner/repo> bd github
  push ...`) rather than `bd config set github.token`, which persists a PAT to
  disk in the repo's beads config.
MUST Expect mirrored issues to carry bd's OWN label scheme (`priority::medium`,
  `type::task`, `status::in_progress`), derived from bd's structured fields. A
  repo with its own vocabulary (`priority-p2`, `spec:NNN`, component labels)
  will not match, so mirrored issues drop out of every existing triage query
  while looking correctly filed.
NOT Hand-correcting those labels on GitHub — `bd github push` REPLACES the whole
  label set from bd on every sync, so any manual fix is silently undone the next
  time that bead is pushed (verified 2026-07-20: labels applied via `gh api`
  were wiped by the next push, twice). `bd update` has no `--label` flag, so the
  scheme cannot be corrected from the bd side either.
DEFAULT Treat the mismatch as an upstream gap rather than per-issue toil: it
  needs configurable label mapping in bd itself. Until then, either accept the
  `::` scheme as the mirror's vocabulary and build triage queries that tolerate
  both, or keep mirrored issues out of label-driven workflows.

SESSION CLOSE (when beads were touched)
MUST File beads for remaining/discovered work before reporting done, close
  finished issues with `--reason`, update in-progress state, then `bd dolt push`.
MUST Before closing a bead whose work continues elsewhere (PR awaiting CI,
  follow-up expected), write residual context onto the bead itself
  (`bd comments add`: approach, tricky spots, what to check first on failure) —
  the bead is the cross-session handover; PR bodies and handover files are not.
DEFAULT Git commit/push of code follows delivery steering, not bd's profiles.

SETUP
MUST Wire hooks natively, once, globally: `bd setup claude --global` (hook
  only) and `bd setup codex --global`; per repo, `bd init` only.
NOT Per-project `bd setup claude` — it appends a managed CLAUDE.md block that
  duplicates this steering and fights `apm compile`.
