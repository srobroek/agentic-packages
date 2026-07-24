# Implementation Plan: Bead-as-Brief Orchestration Contracts

**Branch**: `fix/orchestrate-agent-contracts` | **Date**: 2026-07-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-bead-as-brief/spec.md`

**Design authority**: `packages/orchestrate/.apm/skills/orchestrate/references/bead-as-brief.md` (bead orc-3v0). This plan sequences that design into deliverables; it does not restate mechanisms.

## Summary

Move all orchestrate task data onto beads (metadata + BRIEF), bind contracts to claims via a declarative rules engine enforced at SubagentStop, route ephemeral coordination over wisps/links/labels/gates, and collapse landing to a single draft-PR path through pr-shepherd. Delivered as: a cross-package doctrine section in beads steering, a rules-engine evaluator + per-agent rules files, hook wiring (per-agent + universal + orchestrator claim-deny), fleet changes in the orchestrate package (4 agents removed, domain-specialist variants added), pr-shepherd amendments, and rewritten orchestrate skill references.

## Technical Context

**Language/Version**: Bash (evaluator + hooks; bash 3.2-compatible per hooks-portability-ci), YAML (rules files), Markdown (steering/skills/agents), Python 3 only where already used by package scripts

**Primary Dependencies**: bd ≥ 1.1.0 (wisps, gates, graph links, merge slot, labels — verified against installed binary and beads source), Claude Code ≥ 2.1.198 (SubagentStop block, agent frontmatter hooks, SendMessage behind `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`), Codex CLI (SubagentStop with agent_type matcher, JSON-stdout requirement), APM (compile, build-native-plugins.py, agent TOML generation), jq (hook JSON)

**Storage**: beads store (`.beads/*.db`) — durable beads, wisps, gates, deps, labels; no new storage

**Testing**: package-local bash test scripts (existing `_test_*.sh` convention), hooks-portability-ci for hook scripts, conformance suite for the rules-engine evaluator (fixture beads → expected verdicts), one live end-to-end run as SC validation

**Target Platform**: macOS + Linux dev machines; Claude Code primary, Codex degraded mode (fresh-per-node, defense-in-depth hooks)

**Project Type**: APM package monorepo — steering, skills, agents, hooks

**Performance Goals**: hook overhead <1s per SubagentStop evaluation (single `bd show --json` + rules eval); healthy node ≤6 durable comments; orchestrator routing viable at sonnet-low

**Constraints**: hooks fail open (constitution III); no `ask` decisions; deny only agent-facing self-correctable; bash 3.2 / BSD tool portability; generated artifacts never hand-edited (constitution II); rules file is single source → definition contract blocks generated at compile

**Scale/Scope**: ~15 rules files (T1/T2/T3), 1 evaluator, 4 hook wirings, 4 agent definitions removed / 1 added (×4 effort variants), 2 packages amended (pr-shepherd, beads), ~9 skill reference docs touched, speckit adoption deferred to orc-pyq

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Self-contained packages | PASS | Rules engine evaluator ships in the beads package (doctrine owner); each agent package ships its own rules file + hook wiring; no runtime reach-across — hooks read rules files deployed with their own package |
| II. Generated artifacts not hand-edited | PASS | Definition contract blocks are compile-generated from rules files; plan adds them to build-native-plugins/apm compile flow; effort variants generated, not hand-written |
| III. Hooks fail open | PASS with justification | SubagentStop contract blocks are `decision:"block"` — agent-facing, self-correctable, with an unconditional escape (`state=failed`) and a 3-attempt bounce that force-allows. No `ask` anywhere. Orchestrator claim-deny is deny-with-self-correction, run-marker-scoped. Malformed input → allow (fail open) |
| IV. Conventional commits / release-please | PASS | Per-package changes land as scoped conventional commits; agent deletions are breaking-change commits for the orchestrate package |

Post-design re-check: no violations introduced by Phase 1 artifacts. Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/002-bead-as-brief/
├── plan.md              # This file
├── research.md          # Phase 0 — session-verified findings consolidated
├── data-model.md        # Phase 1 — entities, schema, states, links
├── quickstart.md        # Phase 1 — end-to-end validation guide
├── contracts/           # Phase 1 — rules-file schema, hook I/O, evaluator CLI
├── log.md               # Autonomous-run log (ambiguities, human-input items)
└── tasks.md             # NOT authored — task state lives in beads (speckit-beads)
```

### Source Code (repository root)

```text
packages/beads/.apm/
├── context/beads.doctrine.context.md      # NEW — wisps/links/labels/gates doctrine
├── skills/… (existing)                    # steering index gains doctrine pointer
└── scripts/rules-eval.sh                  # NEW — shared contract evaluator

packages/orchestrate/.apm/
├── agents/
│   ├── domain-specialist.agent.md         # NEW (source; ×4 effort variants generated)
│   ├── workflow-reviewer.agent.md         # amended (wisp claim, label swap, gh pr review/ready)
│   ├── workflow-advisor.agent.md          # amended (claims escalation wisps)
│   ├── workflow-researcher.agent.md       # amended (output_ref rules)
│   ├── ledger-scribe.agent.md             # amended (batch drain on timer gate)
│   ├── workflow-coder.agent.md            # DELETED
│   ├── workflow-worker.agent.md           # DELETED
│   ├── workflow-pull-worker.agent.md      # DELETED
│   └── integration-gatekeeper.agent.md    # DELETED
├── rules/*.rules.yml                      # NEW — per-agent contract rules files
├── hooks/                                 # NEW — per-agent SubagentStop + universal net + claim-deny
└── skills/orchestrate/
    ├── SKILL.md                           # rewritten spawn/route/wake flow
    └── references/                        # bead-as-brief.md authoritative; spawn-brief.md,
                                           # lifecycle.md, roles.md, queue-watcher.md,
                                           # message-grammar.md, teams.md rewritten/retired

packages/pr-shepherd/.apm/
├── context/pr-shepherd.context.md         # amended — fix-bead routing (orchestrator routes,
│                                          # never claims), content read-only, sheepdog lease
└── agents/pr-shepherd.agent.md            # amended + rules file

packages/agent-coder/, agent-pr-reviewer/, agent-external-repo-worker/,
speckit/, user-journeys/                   # T3 conditional rules files
```

**Structure Decision**: Doctrine and evaluator live in `packages/beads` (cross-package owner); every contract-holding agent package owns its rules file and hook wiring; orchestrate owns the run machinery. Matches constitution I — no package depends on another's internals, only on the deployed doctrine contract.

## Phase Sequencing (dependency order)

1. **Doctrine** — beads steering section (wisps, links, labels, gates, claim⟺contract). Everything else references it.
2. **Rules engine** — schema, evaluator, conformance fixtures; compile-time generation of definition contract blocks.
3. **Hooks** — per-agent SubagentStop, universal Start/Stop net, orchestrator claim-deny; portability CI.
4. **Fleet** — domain-specialist (+variants), agent deletions, reviewer/advisor/researcher/scribe amendments, rules files for T1/T2/T3.
5. **pr-shepherd amendments** — draft-flow, sheepdog, fix-bead routing, gate ticking.
6. **Orchestrate skill rewrite** — SKILL.md + references; wake mechanics; planner-node flow; capability probe.
7. **Validation** — quickstart end-to-end run (SC-001…SC-007).

Downstream (separate beads, not this feature): orc-pyq speckit adoption; settings env flag rollout.
