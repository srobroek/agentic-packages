---
name: project-setup
description: Bootstrap a new repo or add a package with explicit setup choices, APM package selection, tooling, and verification. Use when creating a project, adding a monorepo package, choosing bundles/skills/agents/MCP packages, or running setup scripts.
---

# Project Setup

Interactive bootstrap orchestrator. Collect missing choices, recommend APM
packages from marketplace inventory, show the exact command and package plan,
then run scripts only after the setup shape is clear.

Install this skill at user/global scope: it runs before any project-local APM
skills exist, so it must be available before a project is set up.

## References

Read only what the task needs:

- `references/interactive-options.md` for question flow and defaults
- `references/script-capabilities.md` for supported script flags
- `references/skill-recommendations.md` for APM package recommendation rules
- `references/bootstrap-flow.md` for execution and failure handling
- `references/generated-files.md` for generated file ownership
- `references/language-overlays.md` for selected language overlays
- `references/serena.md` when Serena semantic code tooling is selected
- `../../indexes/serena-language-servers.json` when Serena is selected or
  semantic code tools are needed
- `references/bootstrap-skills.md` before moving skills in or out of global scope
- `references/speckit-extensions.md` when full SpecKit is selected

## Workflow

1. Classify setup mode: new project, package add, or existing repo retrofit.
   Route existing repo ingestion to `brownfield-project` when broad scaffolding
   is not requested.
2. Gather only choices not supplied by the prompt or existing repo state:
   identity, layout, targets, languages, orchestration, process level, APM
   packages, git/GitHub behavior, and verification.
3. Resolve APM and run `scripts/apm-discover.sh` to register/update known
   remote marketplaces, browse package inventory, and print preference-index
   recommendations. Stop and report if APM is unavailable. Do not replace this
   with local package checkout scans.
4. Recommend and select packages only from the APM marketplace browse output.
   Preference-index entries are ranked suggestions, not the full selectable
   set. Non-preferred packages shown in the browse output may be selected and
   promoted into the preference index. Do not inspect local package checkouts,
   raw `marketplace.json`, or runtime folders for recommendations.
5. Recommend bundles first, then deduped extra skills, agents, standalone MCP packages,
   hooks, and steering packages. Send missing capabilities to `find-tools`.
6. Present the final command, overlay commands, selected packages, generated
   file ownership, and verification steps. The setup command must include APM
   install/compile behavior unless the user explicitly opts out.
7. Run setup only when the user confirms or has clearly delegated end-to-end
   execution with all required choices supplied. When running
   `scripts/project-setup.sh`, use Codex sandbox escalation because the
   executor owns protected bootstrap paths such as `.git`, `.codex`, and
   `.agents`.
8. Fill only project-fact-dependent skeletons after scripts finish.
9. Verify with APM install/compile/finalizers and selected language checks.
10. Ask before committing.

## Execution Rules

- Treat scripts as executors, not discovery sources. Use references for flag
  discovery during the interview.
- APM is a required setup stage for new projects and broad retrofits. The
  default executor behavior installs selected APM packages and compiles Codex
  and Claude steering; use `--no-apm-install` or `--no-apm-compile` only when
  the user explicitly opts out or APM is unavailable.
- Before running setup, verify the command has an APM package plan: default
  `core@srobroek-agentic`, the standalone baseline MCP packages, selected
  bundles/agents/skills/MCP metadata, and any direct
  `--apm-dependency <package@marketplace>` entries.
- When the user selects APM packages, record those selections with
  `scripts/apm-discover.sh --profile <name> --select-package
  <package@marketplace> --selection-note <why>` so preferred and non-preferred
  selections gain future recommendation priority for the relevant profile.
- Do not create a hand-written `CLAUDE.md` by default. Compile Claude through
  APM so Claude Code receives the same distributed steering as Codex.
- Do not install bootstrap skills project-locally unless the user explicitly
  wants a self-bootstrapping repo.
- For coding/development agents, do not bake MCP usage into model metadata.
  Tell the parent orchestrator to pass task-specific Context7,
  codebase-memory-mcp, repomix, Playwright, Stitch, or other guidance.
- Prefer Serena for semantic code tools. When the project should use Serena,
  install `mcp-serena@srobroek-agentic`. Read the Serena reference and
  language-server index, run the listed `mise use ...` commands in the project
  root for detected runtime-supported languages, create `.serena/project.yml`
  with `serena project create`, and use Serena's
  project-from-cwd startup for CLI agents. For large projects, run
  `serena project index` after creation.
- If a script lacks a needed supported behavior, patch the script instead of
  hand-creating scaffold output.
- In Codex `workspace-write`, `.git`, `.codex`, and `.agents` are protected as
  read-only. Do not repeatedly retry project bootstrap inside the sandbox after
  a read-only error. Rerun the exact setup executor with
  `sandbox_permissions = "require_escalated"` and a justification that it writes
  protected bootstrap paths.
