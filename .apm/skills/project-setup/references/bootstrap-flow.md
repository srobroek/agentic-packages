# Bootstrap Flow

## Inputs

Collect every configurable choice that is not already supplied. Use
`interactive-options.md` as the checklist and do not silently assume project
shape, stack, orchestration, Spec mode, APM behavior, or GitHub behavior.

## Execution

- New project: `scripts/project-setup.sh`
- Monorepo package: `scripts/package-add.sh`
- Language overlays: `scripts/setup-*.sh`
- Full SpecKit extension install: `scripts/speckit/speckit-setup-all.sh`

## APM And AGENTS Layout

- APM owns shared steering.
- Codex receives generated scoped `AGENTS.md` through `apm compile --target codex`.
- Claude Code receives `.claude/rules` through `apm install`; do not compile
  Claude unless explicitly selected.
- Keep hand-written root `AGENTS.md` minimal when generated APM steering is in use.

## Failure Handling

- If `specify init` fails, rerun the exact retry command emitted by the script.
- If extension install partially fails, rerun only failed `specify extension`
  steps.
- Do not replace supported package/setup commands with manual file copying.
