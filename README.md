# agentic-packages

APM package repository for shared agentic tooling:

- instructions and context for progressive steering
- Claude and Codex agent definitions
- Claude and Codex hook manifests
- finalizers that patch generated runtime agents after APM install

## Root package usage

From this package directory:

```bash
apm run sync-agent-metadata
apm compile --validate --local-only --target codex
```

Use `uv tool run --from apm-cli apm ...` for local validation when `apm` is not
installed on the machine yet.

## Project usage

Add this package to a project `apm.yml`, then expose project-local scripts that
call the finalizers from `apm_modules/_local/agentic-packages` or the installed
Git dependency path. See `templates/project-apm.yml`.

For GitHub installation:

```yaml
dependencies:
  apm:
    - git@github.com:srobroek/agentic-packages.git
```

The important order is:

```bash
apm install --target claude,codex,agent-skills
apm compile --target codex
apm run patch-agentic-tools
apm run audit-agentic-tools
```

Do not compile Claude by default. APM install deploys Claude Code rules under
`.claude/rules`; compiling Claude additionally writes `CLAUDE.md` and duplicates
that steering. Compile Claude only for workflows that explicitly need a single
runtime summary file.

`patch-agentic-tools` is required because APM's conversion does not preserve
all Codex and Claude runtime-specific model, effort, sandbox, and permission
fields.

Shared agentic assets are authored here, not in generated runtime directories
or dotfiles. Add or update agents, skills, hooks, instructions, contexts, MCP
definitions, and project setup scripts under `.apm/`, then reinstall the package
in consuming projects.
