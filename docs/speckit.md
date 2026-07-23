# SpecKit orchestration

SpecKit turns ad-hoc "vibe coding" into a gated, spec-driven pipeline. It is delivered as **three opt-in packages** so you can adopt exactly the layer you want:

- **`speckit`** -- the mechanism: the `speckit-bugfix` skill, the `speckit-setup` bootstrap skill, SpecKit workflow guard hooks, and its bundled task agents. APM deploys the agents to both Claude and Codex.
- **`steering-speckit`** -- the opinionated mandatory-gated Phase 1/2/3 workflow steering. Opt in to adopt the process.
- **`speckit-beads`** -- the enforcement layer: a beads (`bd`) formula whose poured molecule IS the phase DAG (human gates included), plus guards that keep task state in beads. Depends on `speckit` and `beads`.

The pipeline:

```
specify -> clarify -> plan -> tasks -> checklist -> critique + security-review
        -> analyze -> checkpoint
        -> assign -> validate -> execute (checkpoint per task)
        -> verify-tasks -> verify -> review -> qa -> code-review + security-review
        -> cleanup -> sync + conflicts -> retro -> docs -> final checkpoint
```

In repos with a beads workspace (the `speckit-beads` package), task state lives
in beads (`bd ready` / `bd update --claim` / `bd close`), not in tasks.md or
GitHub issues.

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
| `speckit-verify` | Checks implementation against FR/SC (mode: requirements) or detects phantom completions (mode: tasks). |
| `speckit-sync` | Detects drift between specs and implementation (scope: drift) or contradictions between specs (scope: conflicts). |

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
apm install speckit-beads@srobroek-agentic           # opt-in: beads-molecule enforcement
apm compile --target codex,claude --no-constitution
```

Enforcement keys off the feature molecule: `speckit-setup` runs `bd init --skip-hooks` and installs the `speckit-feature` formula; pouring it (`bd mol pour speckit-feature --var feature=<NNN-slug>`) creates the phase DAG whose dependency edges and human-gate beads do the ordering.

## Architecture: the how and why

**Why.** LLM coding agents skip steps. Left to their own judgment they call a security review "overkill," mark tasks complete that were never implemented, and let specs drift from code. The orchestration system removes that discretion: every step is mandatory by default, the ordering is fixed, and a hook layer can hard-block out-of-order or precondition-violating moves before the model acts.

**How -- three layers.**

1. **Declarative workflow** -- [`packages/steering-speckit/.apm/instructions/50-speckit-workflow.instructions.md`](../packages/steering-speckit/.apm/instructions/50-speckit-workflow.instructions.md) defines the full Phase 1 (spec, human-gated) -> Phase 2 (implementation) -> Phase 3 (post-implementation QA) DAG and the standing rules: *all steps mandatory, always invoke via the Skill tool, always get approval between phases.*

2. **The workflow molecule** -- [`packages/speckit-beads/formulas/speckit-feature.formula.toml`](../packages/speckit-beads/formulas/speckit-feature.formula.toml) is the single hand-authored source for the graph: 26 `[[steps]]` with `needs` edges plus human-gate beads at clarify, analyze, and verify sign-off. Pouring it instantiates real beads; `bd ready` exposes only unblocked steps, so ordering is graph-native rather than hook-enforced.

3. **The guard layer** -- [`packages/speckit-beads/scripts/speckit-beads-tasks-guard.sh`](../packages/speckit-beads/scripts/speckit-beads-tasks-guard.sh) keeps state in the molecule: it denies Write/Edit of `specs/*/tasks.md` (the deny reason teaches the `bd create`/`bd dep add`/`bd ready` replacement), advises on Bash mentions of tasks.md and on deprecated `/speckit.implement` invocations, and stays inert in repos without a beads workspace. Human gates are resolved with `bd gate resolve`; `bd gate check` closes gh:pr/gh:run gates.

**Hook events.** Claude wires `UserPromptExpansion`, `PreToolUse`, and `PostToolUse`. The deprecated DAG adapter uses only Codex `UserPromptSubmit`, which can gate an explicit `/speckit.*` prompt before invocation; Codex has no exact skill-completion event. The current `speckit` package separately uses supported Bash, prompt, edit, and stop hooks.

**Mandatory-step enforcement.** Node `pre` blocks phrase skips as *"only if the user explicitly skips X"* rather than *"acceptable if X skipped"* -- combined with the standing rule that steps are mandatory, the agent suggests the next step every time and only omits one on explicit user request. The May-2026 DAG reorder moved `critique` and `security-review` to run in parallel right after `tasks`, and made the post-implementation QA steps (verify-tasks, verify, review, qa, code-review, security-review) mandatory rather than optional.

**The payoff.** Security review and phantom-completion detection can't be silently dropped; specs can't be hand-edited around the Skill tool; and the same gated flow compiles to both Claude and Codex from one definition.

---

See also: [bundles](bundles.md) · [skills](skills.md) · [agents](agents.md) · [steering](steering.md) · [hooks and MCP](hooks-and-mcp.md) · [external repos](external-repos.md)
