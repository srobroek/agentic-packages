# Claude agent-teams — the exception, not the norm

> **Default to subagents. Do not spawn teammates for ordinary parallel work.**
> Claude Code proactively *proposes* agent-teams whenever it sees "parallel work"
> — decline that here. The decompose → parallel worktree coders → review → merge
> pipeline runs entirely on **background subagents via the Agent tool**, never on
> teammates. Reach for a team only when a case below is unmistakably met; when
> unsure, use subagents.

The default coordination model in this skill is **persistent/ephemeral background
subagents addressed via SendMessage**, brokered by the orchestrator. That is
cheaper and it composes with everything else here (coder→advisor nesting,
persistent gatekeeper/scribe, worktree isolation). Teammates also cannot spawn
background subagents, so the coder→advisor exception and the persistent
gatekeeper/scribe do not even work inside a team.

Reach for Claude **agent-teams** only when agents must genuinely talk **peer-to-
peer** and share a live task list in a way that routing every exchange through the
orchestrator would bottleneck.

## When teams are worth it

- **Adversarial multi-hypothesis debugging** — several agents hold competing
  theories and challenge each other directly until one survives.
- **Live cross-layer negotiation** — teammates owning frontend/backend/tests must
  agree on a shared interface interactively as they build.
- **Parallel independent review** — several reviewers apply different lenses to the
  same artifact and compare findings.

For everything else — the normal decompose → fan-out coders → review → merge
pipeline — use subagents.

## Constraints (know these before choosing teams)

- **Experimental + off by default.** Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
  in settings/env. Without it, no team is formed. Teams add coordination overhead
  and use **significantly more tokens** (each teammate is a full session).
- **Small teams only.** 3–5 members; efficient models (sonnet/haiku), not a uniform
  opus team. Three focused teammates beat five scattered ones.
- **Teammates can't spawn background subagents** (in-process). So the
  coder→advisor exception and the persistent gatekeeper/scribe **do not work
  inside a team** — keep those on the subagent pipeline. Use a team as a bounded
  *burst* for the collaborative sub-problem, then return to the pipeline.
- **No nested teams; one team per session; lead is fixed.** Address teammates by
  name; give each a full spawn brief (they don't inherit your history).
- File-ownership discipline still applies — two teammates editing one file clobber
  each other exactly like two coders would.

## How to run one

Spawn teammates in natural language, naming the models and giving each a complete
brief and a distinct lens (see the Claude Code agent-teams docs). Cap the size,
keep the burst short, monitor and synthesize, then shut the teammates down and
continue the main run on subagents. Log the team's outcome to the ledger like any
other step.
