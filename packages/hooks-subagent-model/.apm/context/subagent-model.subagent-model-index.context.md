# Subagent Model Routing

LEGEND: Rules carry stable IDs (SM-n) cited by the enforcing hook.

subagent-model-guard.sh enforces SM-1..SM-2.

MUST SM-1: pass an explicit `model` on every Agent/Task spawn whose `subagent_type` has no pinned model in its own definition (or when `subagent_type` is omitted) — otherwise the spawn silently inherits the parent session's model, which is often an expensive top-tier one.
MUST SM-2: pick the model by workload when SM-1 requires one, routing via the tiers defined in steering-subagent-routing — the cheap tier for mechanical work (CI watching/shepherding, log triage, batched gh/git operations, file sweeps, formatting), the mid tier for bounded coding, standard research, PR fix rounds, doc writing, and test authoring, and the top tier (or an explicit pass-through of the session's own model, chosen deliberately) for deep/adversarial research, architecture, cross-cutting synthesis, and judge/verification passes. The hook's deny message carries the concrete tier→model mapping so a blocked caller can self-correct on retry.

The inherit-by-default subagent_type list (agent types with no pinned model:
`general-purpose`, `Explore`, `Plan`, `claude`, `fork`) is overridable per
project via the `SUBAGENT_MODEL_GUARD_INHERIT_TYPES` environment variable
(comma-separated) without a package release — set it when a project defines
its own unpinned custom agent types that should also be gated, or to shrink
the list if a project's `general-purpose` usage is intentionally cheap.

NOTE SM-3 (enforcement boundary): reasoning effort is NOT enforceable by this
hook — the Agent tool_input carries no `effort` field for it to inspect, so it
only ever gates `model`. Pin `effort:` in an agent definition's frontmatter
(low for mechanical lanes, high or above for verification/judge lanes) for
reusable agents; workflow scripts that spawn ad hoc agents may pass effort per
call instead.
