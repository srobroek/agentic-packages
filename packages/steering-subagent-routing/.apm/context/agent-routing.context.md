# Agent Routing

Model routing is applied by per-package `agent-models.yml` files, injected at build time via `inject-agent-models.py`.

## Criteria-based routing

Spawn an agent by name rather than choosing a tier by hand: every shipped agent
already carries a measured model+effort pin. Route by tier only when none fits.

| Task type | Claude tier | Claude effort | Codex fallback |
|-----------|-------------|----------------|----------------|
| review / verify / adversarial / design judgment | opus | high | gpt-5.6-sol high |
| scoped implementation, refactors, tests | opus | low--medium | gpt-5.6-luna xhigh |
| exploration, research, report writing | opus | low | gpt-5.6-luna high |
| mechanical readers: log/metric summarising, lint and doc gathering, diff smoke checks | sonnet | high | gpt-5.3-codex-spark low--medium |
| orchestration / planning | main session | inherit | parent session |
| explicit coding-agent override | -- | -- | gpt-5.6-luna high |

NOTE: `fable` is the frontier Claude model but is reserved for explicit user
opt-in only -- never auto-routed by steering or agents.

Do not route to `haiku`. Escalate on failed verification, not preemptively.

Do not encode MCP usage in model overrides. When delegating to coding or design
agents, pass task-specific instructions to use the project's available tools,
such as Context7 for library docs, semantic symbol tools for code exploration,
Playwright for browser verification, or Stitch for design work.

In beads repos (`bd where` succeeds), pass the bead id in the spawn prompt so
the worker claims it (`bd update <id> --claim`) -- an unpassed id leaves the
bead unclaimed and a parallel worker may take the same work.

## Repomix for bulk context

Repomix packs a whole tree into one document. Run it on demand, from the CLI;
there is no snapshot to keep fresh. A pack of this repository takes 1.3s and
repomix caches nothing, so a second pack costs the same as the first.

| Need | Command |
|------|---------|
| pack the tree | `repomix .` |
| scope to the files that matter | `repomix . --include "src/**/*.ts"` |
| read it without writing a file | `repomix . --stdout` |
| pack another repository | `repomix --remote <url> --remote-branch <ref>` |

Reach for `--include` first: scoping to code cut output 81 percent against a
whole-repo pack. Prefer semantic symbol tools and `rg` for a single lookup, and
a pack only when a task needs many files at once.

Decide `--compress` per language. It saved 21 percent on this repository and 0
percent on markdown and JSON. It grew 197 files of 4,107.
