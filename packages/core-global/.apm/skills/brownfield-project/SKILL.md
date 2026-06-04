---
name: brownfield-project
description: Retrofit an existing repository into APM-managed agentic tooling without broad scaffolding. Use when onboarding, ingesting, or repairing a brownfield repo, especially when the agent must first discover project purpose, requirements, and workflow needs interactively.
---

# Brownfield Project

Use this when an existing repository needs APM-managed agents, skills, hooks,
steering, or setup repair. Ingest the repo as it is; do not turn it into a new
project scaffold.

## Scope

- Owns: brownfield classification, source-of-truth preservation, and retrofit
  plan.
- Delegates package/drift review to `project-hygiene`.
- Delegates all package, agent, skill, hook, MCP, connector, CLI, and reusable
  tool selection to `find-tools`.
- Delegates concrete APM add/update/remove operations to `agent-management`.
- Uses `grill-me` when repo evidence is not enough to understand the project's
  purpose, requirements, constraints, or desired agentic workflow.

## Workflow

1. Inspect before changing anything:
   - `git status --short`
   - `apm.yml`, `apm.lock.yaml`
   - `AGENTS.md`, `CLAUDE.md`
   - `.agents/skills`, `.codex/agents`, `.claude/agents`
   - `.codex/hooks.json`, `.claude/settings.json`
   - root and scoped `AGENTS.md` files
   - package manifests, lockfiles, toolchain files, CI, docs, specs, ADRs
2. Discover the project before selecting tools. Infer purpose from README/docs,
   specs, manifests, source layout, tests, examples, CI, and deploy config.
   Identify users, workflows, critical data, external services, runtime targets,
   release path, and safety/security concerns. Separate current reality from
   aspiration, and record evidence plus confidence.
3. If purpose or requirements remain unclear, use `grill-me` before recommending
   packages. Ask one question at a time with a recommended answer. Start with
   the highest-impact unknown blocking tool selection. Prefer repo exploration
   over asking when the answer is discoverable. Stop once project goal, users,
   workflow, write boundaries, and quality gates are clear enough; go deeper
   only when the answer materially changes installed tooling or steering.
4. Classify existing agentic assets:
   - source-owned: `apm.yml`, `apm.lock.yaml`, package-managed source
   - generated: compiled `AGENTS.md`, `.claude/rules`, runtime agents/skills
   - legacy/manual: copied agents, copied skills, legacy `CLAUDE.md`, old hooks
   - bootstrap-only: global setup helpers that should not be project-managed
5. Identify existing source-of-truth docs and conventions. Preserve them; route
   into APM instructions or scoped `AGENTS.md` only when that clarifies
   ownership.
6. Resolve APM in order: `apm`, `mise exec -- apm`,
   `uv tool run --from apm-cli apm`. Stop and report if none work.
7. Build a capability brief and delegate package/tool selection to `find-tools`.
   Include:
   - discovered purpose, requirements, users, workflows, and open questions
   - project type, languages, frameworks, package managers, CI, deploy target
   - current APM state, registered marketplaces, and installed assets
   - existing agentic assets classified as source-owned, generated,
     legacy/manual, or bootstrap-only
   - needed capabilities: bundles, agents, skills, hooks, MCP servers,
     connectors, CLIs, steering, workflow tools, and quality gates
   - constraints: Codex/Claude target, local vs hosted, secrets, network,
     write access, security posture, and whether Claude Code is used
   Require `find-tools` to start with the primary marketplace baseline, normally
   `core@srobroek-agentic`. Install the mandatory baseline MCPs as standalone packages: `mcp-codebase-memory@srobroek-agentic`, `mcp-context7@srobroek-agentic`, `mcp-package-version@srobroek-agentic`, and `mcp-repomix@srobroek-agentic`. Recommend optional MCP-only packages, including `mcp-playwright` and `mcp-serena@srobroek-agentic`, only when the repository needs that capability. For Serena, read the global Serena language-server index, run the listed `mise use ...` commands in the project root for detected languages, create or repair `.serena/project.yml` with `serena project create`, and consider `serena project index` for large repositories. Then recommend first-party
   extras, registered external marketplace packages, and public-source discovery
   only for gaps. For Serena details, use the global project-setup reference
   `references/serena.md` and do not generate docs-only language keys or
   `added_modes` for Serena 1.2.0.
8. Run or apply `project-hygiene` to identify stale assets, missing packages,
   duplicate skills, generated-file edits, and bootstrap leakage.
9. Ask before removing legacy/manual assets. Archive only files that contain
   useful project knowledge; remove generated copies only after confirming APM
   can recreate them.
10. Use `agent-management` for approved APM installs, compiles, patching, and
   audit commands. For dual Codex/Claude projects, compile both
   `apm compile --target codex` and `apm compile --target claude` after install.
11. Report changed files, installed assets, archived/removed assets, skipped
   checks, and remaining manual decisions.

## Rules

- No broad scaffold unless the user explicitly asks for one.
- Do not treat APM package selection as the first step. Understand purpose and
  requirements first, then choose tooling.
- Ask only for requirements that are unclear, consequential, and not reasonably
  discoverable from the repository.
- Keep discovery bounded. The goal is enough shared understanding for retrofit
  choices, not a full product specification unless the user asks for one.
- Preserve existing package managers, CI, build commands, docs, and issue
  workflow unless the user chooses a migration.
- Treat project-local generated assets as APM-owned.
- Keep bootstrap skills global unless the user explicitly chooses a
  self-bootstrapping project.
- Do not select packages directly except for obvious already-approved baseline
  repair. Use `find-tools` for reusable tool recommendations.
- If baseline MCPs are missing, install or repair the standalone MCP packages through `apm install <package>@srobroek-agentic` instead of adding duplicate MCP declarations by hand.
- Use `srobroek-agentic` as the deterministic first-pass marketplace for
  brownfield migrations, but let `find-tools` own marketplace registration,
  browsing, public registry discovery, candidate verification, and
  adopt/trial/reject/build classification.
- Do not skip directly to external marketplaces unless `find-tools` identifies a
  clear gap or the user asks for an external source.
- Never edit generated runtime copies directly during retrofit.

## Output

Lead with:

1. Discovered project purpose, requirements, confidence, and open questions
2. Existing state and risks
3. Source-of-truth map
4. Legacy/manual assets to keep, archive, or remove
5. Recommended APM actions or delegated follow-up
6. Verification commands and skipped checks
