# Research: Bead-as-Brief Orchestration Contracts

All unknowns were resolved during the design session (recorded in the design
doc, bead orc-3v0). This file consolidates the verified findings and their
sources. No NEEDS CLARIFICATION markers remain.

## R1 — SubagentStop blocking semantics

**Decision**: Enforce contracts at SubagentStop with `decision:"block"` +
structured JSON reason; 3-attempt bounce with force-allow.

**Rationale**: Verified on both runtimes. Claude (code.claude.com/docs:
sub-agents, hooks): exit 2 or `decision:"block"` prevents the stop; reason is
fed back; stdin carries `agent_type`, `agent_id`, `transcript_path`; no
documented loop protection → we count `stop_attempts` on the bead. Codex
(learn.chatgpt.com/docs/hooks): same block semantics; requires JSON stdout;
provides `stop_hook_active` re-entrancy flag; >~2500-token outputs spill to a
temp file with head/tail preview.

**Alternatives considered**: PreToolUse deny on every `bd` write — rejected:
Codex shell interception is partial, bd-command parsing is fragile (fuzz
history), and wrong writes on beads are recoverable; stop-time validation is
the honest enforcement point.

## R2 — Per-agent hook attachment

**Decision**: Claude — `hooks:` in agent frontmatter (runs only while that
agent is active). Codex — matcher on `agent_type` in the SubagentStop entry.
Universal net — matcher-less hooks on both.

**Rationale**: Both documented. Claude also supports settings-level matchers
on agent type (`^name$` anchoring required ≤ v2.1.194). Codex has no per-agent
hook declaration in agent TOMLs — config-level matcher is the only path.

**Alternatives considered**: Single dispatcher script keyed on `agent_type` —
kept as the mechanism *inside* the universal net, but per-agent attachment
keeps known-role hooks package-owned (constitution I).

## R3 — Wisp types and lifecycle

**Decision**: Map our vocabulary onto bd's TTL classes: review/escalation →
`escalation` (7d), worklog/ledger → `gc_report` (24h), sheepdog → `patrol`
(24h), probe chatter → `ping`/`heartbeat` (6h), recovery → `recovery` (7d).

**Rationale**: Verified in beads source (`internal/types/types.go`): types are
TTL categories for compaction of **closed** wisps (6h/24h/7d). GC never
deletes open wisps; `bd mol wisp gc` flags open wisps untouched 24h as
abandoned → freshness doubles as the liveness signal (sheepdog).
`bd promote` un-wisps content that proves durable; `bd purge` bulk-deletes
closed ephemerals.

**Alternatives considered**: Custom wisp types — not supported (fixed enum);
title prefixes (`[wisp:review]`) carry our semantics instead.

## R4 — Graph links

**Decision**: `relates-to` (tether), `discovered-from` (follow-up work),
`caused-by` (bounce/recovery provenance), `supersedes` (re-planning),
`duplicates` (dedup). `replies-to` for wisp threads with a caveat.

**Rationale**: All verified in `bd dep add --type` on 1.1.0 except
`replies-to`, which is absent from the CLI dep-type enum — docs create it via
orchestrator mail. `bd show --thread` exists.

**Open implementation check** (not a design blocker): whether `replies-to`
edges can be created outside the mail path; fallback is `relates-to` +
chronological comments. Also verify burn cleans link edges (no dangling refs).

## R5 — Gates

**Decision**: `human` for ASK/approvals, `timer` for the scribe drain cycle,
`gh:run`/`gh:pr` for CI/PR waits. Tickers: shepherd patrol runs
`bd gate check --type=gh`; orchestrator runs `bd gate check` at every wake.

**Rationale**: Verified: gates evaluate on-demand only (`bd gate check` shells
to `gh run view`/`gh pr view`); no polling daemon. Existing constraint
honored: never a `gh:pr` gate blocking a merge bead (deadlock; pr-shepherd
steering).

## R6 — Wake/resume mechanics

**Decision**: Suspend-and-resume via SendMessage where available; bounded
poll (60s / 15–30min) then checkpoint-exit elsewhere; respawn-from-bead is a
first-class fallback everywhere.

**Rationale**: Claude docs: SendMessage to a finished subagent auto-resumes
with full history; requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (absent
from current settings — run-start capability probe required). Handles are
session-registry-scoped and die on compaction/overnight (claudefa.st
persistent-subagents guide; measured context growth 199k→324k over 8 rounds →
prefer respawn after ~2 rounds or post-compaction). Codex: no resume API
(officially undocumented multi-agent surface) → degraded mode.

## R7 — Landing path

**Decision**: One landing path: draft PRs + merge beads + per-repo shepherd +
merge slot. integration-gatekeeper deleted; in-run integration = PRs against
the integration base (stacked landing already supported).

**Rationale**: pr-shepherd landing contract verified: per-bead
claim→probe→slot→release is already serial (exit codes 2/10/11/75 all release
the claim); `pr-base` vs `landing-base` params handle stacked merges; drafts
are already invisible to the shepherd ("ignore while isDraft=true") — which
makes draft→ready the natural review promotion and forced the
reviewer-undrafts decision.

## R8 — Model/effort routing for specialists

**Decision**: Model per spawn (Agent tool `model:` param; hooks-subagent-model
already requires explicitness). Effort via compiled variants
`domain-specialist-{low,medium,high,xhigh}` — Agent calls carry no effort
field. Codex mirrors via `model_reasoning_effort` in generated TOMLs.

**Rationale**: Platform constraint (no per-spawn effort) verified in the
subagent-model hook design notes and Claude docs. Orchestrator tier table maps
`complexity_tier` → (variant, model). Routing tier for the orchestrator
itself: sonnet-low (post-planner-split, routing is table lookups; BOUNCE
triage is the floor-setting judgment call).

## R9 — Rules-as-data

**Decision**: Per-agent YAML rules files; one shared evaluator; definition
contract prose generated at compile time; tiny predicate vocabulary
(metadata-key-exists, label-match, comment-verb, state-in-set,
wisp-open/closed).

**Rationale**: Hook-portability history (bash 3.2 parse errors, GNU-only
constructs, string-payload jq crashes) argues for writing the fragile part
once. Two-sources-drift risk (prose contract vs rules) resolved by
generation — rules file is the single source of truth.

**Alternatives considered**: Central authority-matrix file — rejected
(single-owner bottleneck, violates package self-containment); hand-written
prose + rules — rejected (drift).
