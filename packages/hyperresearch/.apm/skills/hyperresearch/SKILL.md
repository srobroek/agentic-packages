---
name: hyperresearch
description: Run the third-party HyperResearch deep research harness. Use when the user asks for deep research, adversarial source-backed research, long-form research reports, or HyperResearch specifically.
---

# HyperResearch

This is a thin APM wrapper for the upstream `jordan-gibbs/hyperresearch`
package. Do not vendor HyperResearch's generated Claude skills, agents, hooks,
or research vault files into this repository.

## Use

1. Confirm the user wants a long-running research workflow.
2. Ensure the upstream command is available:

```bash
hyperresearch --help
```

3. If it is unavailable, install or run upstream HyperResearch through the
   project toolchain. Prefer a project-local or tool-managed install over a
   global install:

```bash
uv tool run --from hyperresearch hyperresearch install . --json
```

4. Then follow the runtime path below.

## Claude Code path

Follow upstream's generated `/hyperresearch` workflow after
`hyperresearch install`.

## Codex / other runtimes path

Treat this skill purely as a router to the upstream CLI and research vault --
no Claude-only orchestration (no subagents, no generated Claude skills):

1. Run the `hyperresearch` CLI directly with the user's research question.
2. Use the command output and the generated research vault files as the source
   of truth.
3. Do not manually recreate the 16-step pipeline from memory.

## Notes

- Upstream source: `https://github.com/jordan-gibbs/hyperresearch`
- License: MIT
- APM cannot install the upstream repository root directly because it does not
  currently expose an APM package, `SKILL.md` directory, or plugin root.
