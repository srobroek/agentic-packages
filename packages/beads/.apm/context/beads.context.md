# Beads (bd)

SCOPE
MUST Use bd for all task tracking when the repo has `.beads/` (`bd where`
  succeeds); do not use TaskCreate or markdown task lists.
DEFAULT SpecKit artifacts (spec.md/plan.md) stay the source for WHAT to build;
  beads tracks execution state, not requirements.
NOT `bd edit` — opens $EDITOR and blocks the agent; use `bd update` flags.

MEMORY
DEFAULT `bd remember "insight" --key <slug>` for repo-scoped durable facts any
  agent or tool must see (gotchas, conventions, decisions); every memory is
  injected verbatim via bd prime each session — keep the set ≤30, prune stale
  keys with `bd forget` during session review.
DEFAULT MemPalace keeps cross-session semantic recall; user/global knowledge
  stays in Claude auto-memory (see mempalace steering).

IDENTITY
MUST Set BEADS_ACTOR (`<harness>/<agent-name>/<session-id>`) on every mutating
  command when acting as a subagent; audit trails and claim ownership depend
  on it, and the session id distinguishes dead claims from live ones.
DEFAULT Treat BD_ACTOR as a legacy compatibility variable only for Beads
  1.1.0's `prepare-commit-msg` identity trailer; when that product hook is
  enabled, export the same value in BEADS_ACTOR and BD_ACTOR until the hook
  accepts BEADS_ACTOR. Never use BD_ACTOR as the policy authority.

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

WORKFLOWS
DEFAULT Read only the relevant workflow contract:
- [Lifecycle and gates](beads.lifecycle.context.md)
- [Semantic audit and reporting](beads.audit.context.md)
- [Formulas, molecules, bonds, and wisps](beads.composition.context.md)
- [Swarms and merge slots](beads.coordination.context.md)

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
MUST Run `bd dolt pull` or `bd dolt push` only when the active user,
  repository, or orchestrator instructions grant external-sync authority;
  `git pull` and `git push` do not synchronize `refs/dolt/data`.
DEFAULT Single-machine local orchestration performs no routine pull and uses
  one authorized push at orchestrator handoff when durable bead state changed.
DEFAULT Cross-machine or team orchestration uses one authorized pull before
  claims or fan-out and one authorized push after durable updates; conservative
  profiles report the exact pending command instead of running it.
NOT Routine `bd import` of issues.jsonl — it is upsert-only passive export;
  `bd dolt pull` is the sync path.

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
  finished issues with `--reason`, and update in-progress state.
MUST Before closing a bead whose work continues elsewhere (PR awaiting CI,
  follow-up expected), write residual context onto the bead itself
  (`bd comments add`: approach, tricky spots, what to check first on failure) —
  the bead is the cross-session handover; PR bodies and handover files are not.
MUST Before closing a bead as landed, or filing one claiming work is missing from main, verify by content per GW-3 (git-workflow steering).
DEFAULT Git commit/push of code follows delivery steering, not bd's profiles.
DEFAULT Synchronize bead state at the authority-aware boundary defined under
  SYNC; otherwise report the pending `bd dolt pull` or `bd dolt push` command.

SETUP
MUST Let the bd CLI own initialization and generated integration: bootstrap
  with `bd init --init-if-missing`, then verify with `bd where`, `bd setup
  claude --check`, `bd setup codex --check`, and `bd hooks list`.
MUST Repair an existing project's runtime integration with product commands:
  `bd setup claude --project` and `bd setup codex`.
MUST Use `bd hooks install --beads` only when the active project chose the
  product Git-hook bundle.
NOT Copies of product lifecycle hooks, managed instruction blocks, skill, or
  Git-hook shims in APM.
DEFAULT Project setup follows the repository's Beads version; global setup is
  for repositories that do not install project integration, not redundancy.
NOT `bd preflight` as an application quality gate — Beads 1.1.0 hard-codes
  checks for the Beads Go repository; use repository-owned quality commands.
