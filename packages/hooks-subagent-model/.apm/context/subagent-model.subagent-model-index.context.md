# Subagent Model Routing

LEGEND: Rules carry stable IDs (SM-n) cited by the enforcing hook.

subagent-model-guard.sh enforces SM-1..SM-2.

MUST SM-1: Claude Agent/Task spawns whose `subagent_type` has no pinned model must pass an explicit `model`. Codex Agent spawns must select a named semantic `agent_type` whose nearest project or global custom profile pins both `model` and `model_reasoning_effort`; a project profile shadows a same-named global profile and must never fall through when incomplete.

MUST SM-2: pick the model by workload when SM-1 requires one. See the
  criteria-based routing table in steering-subagent-routing for tier
  definitions and Codex fallback models.

The deny message for a Codex ad-hoc/default spawn lists profiles from the
installed catalog (project `.codex/agents/` walking up to the filesystem root,
then `$CODEX_HOME/agents`), formatted as `name (model/effort)`. When no
profiles are found the message instructs the agent to create one. This avoids
recommending agent names that may not be installed in the consuming project.

The inherit-by-default subagent_type list (agent types with no pinned model:
`general-purpose`, `Explore`, `Plan`, `claude`, `fork`) is overridable per
project via the `SUBAGENT_MODEL_GUARD_INHERIT_TYPES` environment variable
(comma-separated) without a package release — set it when a project defines
its own unpinned custom agent types that should also be gated, or to shrink
the list if a project's `general-purpose` usage is intentionally cheap.

NOTE SM-3 (enforcement boundary): Claude's Agent input does not expose a
reasoning-effort field, so reusable Claude definitions must pin `effort:`.
Codex custom profiles must pin `model_reasoning_effort`; the guard verifies the
resolved profile before spawn. Set `SUBAGENT_MODEL_GUARD_ALLOW_AD_HOC=1` only
when an intentionally ad-hoc Codex spawn passes both `model` and
`reasoning_effort` explicitly.
