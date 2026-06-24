# SpecKit orchestration

SpecKit turns ad-hoc "vibe coding" into a gated, spec-driven pipeline. It is delivered as **three opt-in packages** so you can adopt exactly the layer you want:

- **`speckit`** -- the mechanism: six SpecKit sub-agents, the `speckit-bugfix` skill, the `speckit-setup` bootstrap skill, the `speckit-dag` node store, and the SpecKit workflow guard hooks (issue/PR conventions, commit checks, stop gate).
- **`steering-speckit`** -- the opinionated mandatory-gated Phase 1/2/3 workflow steering. Opt in to adopt the process.
- **`speckit-dag-hooks`** -- the enforcement layer: the Python DAG dispatcher + `nodes.json` + hooks that hard-block out-of-order `/speckit.*` calls. Depends on `speckit`.

The pipeline:

```
specify -> clarify -> plan -> tasks -> checklist -> critique + security-review
        -> analyze -> issues -> checkpoint
        -> assign -> validate -> execute (checkpoint per task)
        -> verify-tasks -> verify -> review -> qa -> code-review + security-review
        -> cleanup -> sync + conflicts -> retro -> docs -> final checkpoint
```

Conditional loop-backs branch off this spine: `iterate` (scope/intent change),
`bugfix` (defect in built code), `fix-findings` (review/QA findings), and
`converge` (spec is right but code is incomplete -- assesses the code against
spec/plan/tasks and appends the unbuilt work as new tasks, append-only, to be
implemented via the agent-assign flow).

## The six sub-agents

Read-only analysts except where noted:

| Agent | Role |
| --- | --- |
| `speckit-research` | Pulls current library/API docs (Context7, official sources) tied to a spec decision; returns cited findings. |
| `speckit-implement-task` | Executes scoped tasks from `tasks.md`, or delegates substantial code work to a coder. |
| `speckit-verify` | Checks implementation against the spec's functional requirements and success criteria. |
| `speckit-verify-tasks` | Detects *phantom completions* -- tasks marked done with no real implementation evidence. |
| `speckit-sync` | Detects drift between specs and implementation. |
| `speckit-sync-conflicts` | Detects contradictions between specs or against shared contracts. |

## Setting up a SpecKit project

The `/speckit.*` slash commands come from the upstream [`github/spec-kit`](https://github.com/github/spec-kit) `specify` CLI plus community extensions. This repo's packages supply the orchestration on top.

**Recommended -- via the `speckit-setup` skill** (shipped in the `speckit` package):

```bash
apm install speckit@srobroek-agentic --target claude,codex
```

Then invoke the skill (it is self-describing -- ask the agent to "set up SpecKit"). It bootstraps end-to-end:

1. `specify init --here --integration codex --script sh` -- scaffolds `.specify/` (constitution, feature dirs, workflow state).
2. Registers the community extension catalog: `https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.community.json`
3. Installs and enables the required extension set (including `agent-assign`).
4. Installs the workflow definitions `speckit`, `speckit-quality`, `speckit-full` via `specify workflow add` from the package's own `workflows/` dir. These are this repo's opinionated definitions, not upstream catalog entries -- the `speckit` one overrides the upstream `Full SDD Cycle` that `specify init` bundles. Since spec-kit 0.11.x, workflows are a first-class primitive (`specify workflow`), not extensions.

**Manual setup** -- if you prefer to drive `specify` yourself:

```bash
# 1. Install the specify CLI (see github/spec-kit for current install)
uv tool install specify-cli

# 2. Scaffold .specify/ in your project
specify init --here --integration codex --script sh

# 3. Register the community extension catalog
specify extension catalog add --name community --install-allowed \
  https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.community.json

# 4. Install this repo's speckit layers
apm install speckit@srobroek-agentic --target claude,codex
apm install steering-speckit@srobroek-agentic        # opt-in: the gated workflow
apm install speckit-dag-hooks@srobroek-agentic       # opt-in: hard-block enforcement
apm compile --target codex,claude --no-constitution
```

The enforcement hooks key off `.specify/feature.json` (or the git branch) to resolve the active feature, so a scaffolded `.specify/` directory is a prerequisite for the DAG's precondition checks to work.

## Architecture: the how and why

**Why.** LLM coding agents skip steps. Left to their own judgment they call a security review "overkill," mark tasks complete that were never implemented, and let specs drift from code. The orchestration system removes that discretion: every step is mandatory by default, the ordering is fixed, and a hook layer can hard-block out-of-order or precondition-violating moves before the model acts.

**How -- three layers.**

1. **Declarative workflow** -- [`packages/steering-speckit/.apm/instructions/50-speckit-workflow.instructions.md`](../packages/steering-speckit/.apm/instructions/50-speckit-workflow.instructions.md) defines the full Phase 1 (spec, human-gated) -> Phase 2 (implementation) -> Phase 3 (post-implementation QA) DAG and the standing rules: *all steps mandatory, always invoke via the Skill tool, always get approval between phases.*

2. **The DAG node store** -- [`packages/speckit-dag-hooks/scripts/nodes.json`](../packages/speckit-dag-hooks/scripts/nodes.json) is the single hand-authored source for the graph. Each node id holds a `pre` block (legitimate predecessors via `came_from`, plus `hard_missing` / `hard_exists` / `hard_deprecated` preconditions) and a `post` block (default next step via `going_to`, plus `postconditions` and conditional branching). Edges live in this JSON, not in code; the dispatcher reads it at runtime and renders the injected markdown from these structured fields.

3. **The hook dispatcher** -- [`packages/speckit-dag-hooks/scripts/dispatcher.py`](../packages/speckit-dag-hooks/scripts/dispatcher.py) (a self-contained Python script, no build step) runs on every `/speckit.*` invocation, wired through [`speckit-claude-hooks.json`](../packages/speckit-dag-hooks/.apm/hooks/speckit-claude-hooks.json) and [`speckit-codex-hooks.json`](../packages/speckit-dag-hooks/.apm/hooks/speckit-codex-hooks.json):
   - **Pre phase** evaluates hard-block directives from `nodes.json` and **denies** the call if violated:
     - `HARD-MISSING: specs/<feat>/spec.md` -- blocks if a required artifact is absent (e.g. `plan` before `spec`)
     - `HARD-EXISTS: <path>` -- blocks if an artifact that shouldn't exist yet does (routes to a refine path)
     - `HARD-DEPRECATED:` -- blocks unconditionally
   - It resolves the `<feat>` placeholder from `$SPECIFY_FEATURE_DIRECTORY`, then `.specify/feature.json`, then the git branch -- so preconditions are feature-aware.
   - Otherwise it injects the node body as `additionalContext` (soft steering -- "you came from X, go to Y next").

**Hook events.** Claude wires `UserPromptExpansion`, `PreToolUse`, `PostToolUse`; Codex wires `UserPromptSubmit`, `PreToolUse`, `PostToolUse`. Pre fires before the skill runs (can deny); post fires after (only steers).

**Mandatory-step enforcement.** Node `pre` blocks phrase skips as *"only if the user explicitly skips X"* rather than *"acceptable if X skipped"* -- combined with the standing rule that steps are mandatory, the agent suggests the next step every time and only omits one on explicit user request. The May-2026 DAG reorder moved `critique` and `security-review` to run in parallel right after `tasks`, and made the post-implementation QA steps (verify-tasks, verify, review, qa, code-review, security-review) mandatory rather than optional.

**The payoff.** Security review and phantom-completion detection can't be silently dropped; specs can't be hand-edited around the Skill tool; and the same gated flow compiles to both Claude and Codex from one definition.

---

See also: [bundles](bundles.md) · [skills](skills.md) · [agents](agents.md) · [steering](steering.md) · [hooks and MCP](hooks-and-mcp.md)
