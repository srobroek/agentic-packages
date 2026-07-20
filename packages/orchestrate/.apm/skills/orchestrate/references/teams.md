# Claude agent-teams — the exception, not the norm

Default to subagents (Agent tool, background, brokered by the orchestrator via
SendMessage) for the normal decompose → fan-out coders → review → merge
pipeline. Decline the harness's proposal to spawn agent-teams for ordinary
parallel work; use a team only when a trigger below is unmistakably met — if
unsure, use subagents.

## Triggers (teams worth it)

| Trigger | Why teams |
|---|---|
| Adversarial multi-hypothesis debugging | competing theories challenge each other directly until one survives |
| Live cross-layer negotiation | frontend/backend/tests teammates must agree on a shared interface interactively as they build |
| Parallel independent review | multiple reviewers apply different lenses to the same artifact, compare findings |

Everything else → subagents.

## Constraints

- **Experimental, off by default.** Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
  in settings/env. Without it, no team forms. Teams cost significantly more
  tokens (each teammate is a full session).
- **Small teams only.** 3–5 members on efficient tiers — not a
  uniform top-tier team (see steering-subagent-routing).
- **Teammates cannot spawn background subagents** (in-process) — the
  orchestrator-brokered advisor and the persistent gatekeeper/scribe, which rely
  on that, do not work inside a team. Use a team only as a bounded burst for the
  collaborative sub-problem, then return to the subagent pipeline.
- **No nested teams; one team per session; lead is fixed.** Address teammates by
  name; give each a full spawn brief (they don't inherit your history).
- File-ownership discipline still applies — two teammates editing one file
  clobber each other exactly like two coders would.

## How to run one

1. Spawn teammates in natural language, naming the models and giving each a
   complete brief and a distinct lens.
2. Paste `references/comms-block.md` verbatim into each teammate brief — no
   `SubagentStart` hook reaches teammates; this is the only channel that gives
   them the comms protocol.
3. Cap the size, keep the burst short, monitor and synthesize.
4. Shut the teammates down, continue the main run on subagents.
5. Log the team's outcome to beads (audit record + comment) like any other step.
