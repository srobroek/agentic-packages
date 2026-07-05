# Roles, models, escalation

Route each role to the **cheapest capable model**; escalate up only on hard
cases. Discover the concrete agents available with `scripts/discover-agents.py`
(the catalog shows each agent's real `model`); the mapping below is the default
starting point, refined by what the catalog actually offers.

| Role | Agent (default → alternatives) | Model / effort | Persistence | Escalation |
|---|---|---|---|---|
| **Orchestrator** | you (lead session) | your session model | whole run | delegate deep planning / disputes |
| **Researcher** | `Explore` → `general-purpose`, `speckit-research` | **haiku** low/med | ephemeral (reuse for follow-ups) | → sonnet when a single task is synthesis-heavy; broad research → orchestrator pipelines several haiku gatherers into one sonnet synthesizer |
| **Workflow-coder** | `workflow-coder` (bundled) | **sonnet** medium | per node, kept alive across fix rounds | do **not** upgrade the coder — it spawns an Advisor |
| **Advisor** | `adversarial-challenger` → `general-purpose` | **opus** high, read-only | ephemeral, the coder's child | already top tier |
| **Reviewer** | `code-reviewer`/`pr-reviewer` → `adversarial-challenger` | **sonnet** medium, read-only | kept alive per node (re-reviews deltas) | → opus for complex or security-critical diffs |
| **Integration Gatekeeper** | `integration-gatekeeper` (bundled) | **sonnet** medium | **persistent** | → opus only if merge reasoning is genuinely gnarly |
| **Ledger Scribe** | `ledger-scribe` (bundled) | **haiku** low, read-only | **persistent** | — |
| **Tiebreaker** | `general-purpose` (fresh) | **opus** high, read-only | ephemeral, gated | → xhigh only if genuinely complex |

Model aliases: `haiku` (cheap/fast, mechanical + search), `sonnet` (implementation,
review, integration judgment), `opus` (deep reasoning — advisor, tiebreaker, hard
escalations). Set effort with the agent's `effort` field or per-invocation.

"Persistent" means the role is always available for the run, not that it is one
never-restarted process: the Gatekeeper and Scribe keep their state in the shared
stores, so recycle them to shed context (see `references/lifecycle.md`).

The **Orchestrator does not execute work** — it only coordinates. It spends its
context on decomposition, routing, brokering review, gating merges, and the
deterministic scripts; every token-heavy action (reading files, coding,
research, diff review, tests) is delegated to a subagent so the lead session's
context is never burned on content it could have handed off. Doing work yourself
is not a shortcut — it is the fastest way to starve the run of its scarcest
resource.

## Spawn authority (who may spawn what)

- **Orchestrator** spawns everything *except* the Advisor, and owns **all**
  shutdowns/dismissals.
- **Workflow-coder** is the only worker that may spawn a child, and only:
  - one read-only **Advisor** when blocked on reasoning (not a lookup), or
  - a strictly-**cheaper** model to offload mechanical bulk (token savings).
- **Everyone else** spawns nothing. No agent nests beyond these carve-outs even
  though the platform would allow it — this is a cost/anchoring policy.

## Escalation ladder

1. Coder stuck on reasoning → coder spawns Advisor (opus).
2. Diff too complex/security-sensitive for a sonnet reviewer → orchestrator
   re-spawns the reviewer on opus (or adds `adversarial-challenger`).
3. Coder⇄reviewer deadlock after bounded fix rounds, or gatekeeper⇄coder conflict
   a rebase can't settle → orchestrator spawns a fresh **Tiebreaker** (opus,
   clean context, read-only); its `RULE` is logged and binding.
4. A decision needs product intent not in the brief → bubble `ASK` to the human.

Never silently upgrade a whole role to opus to paper over a one-off hard case;
escalate the specific instance.
