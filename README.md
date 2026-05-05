# srobroek/agentic-packages

APM package repository for shared agentic tooling:

- instructions and context for progressive steering
- Claude and Codex agent definitions
- Claude and Codex hook manifests
- finalizers that patch generated runtime agents after APM install

## Root package usage

The `core` bundle installs the local shared package contents, including shared
agents, personal workflow skills such as `activity-tracker` and
`sfdc-activity`, and Matt Pocock's `diagnose` skill as an upstream APM
dependency for the default bug-diagnosis loop.

From this package directory:

```bash
apm run build-marketplace
apm compile --validate --local-only --target codex
```

Use `uv tool run --from apm-cli apm ...` for local validation when `apm` is not
installed on the machine yet.

## Project usage

Register the marketplace, browse available packages, then add selected package
entries to the project `apm.yml`. Project setup should call the finalizers from
`apm_modules/_local/agentic-packages` or the installed Git dependency path. See
`templates/project-apm.yml`.

For marketplace installation:

```bash
apm marketplace add srobroek/agentic-packages --name srobroek-agentic
apm marketplace browse srobroek-agentic
apm install core@srobroek-agentic
```

For direct GitHub installation:

```yaml
dependencies:
  apm:
    - srobroek/agentic-packages
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
fields for first-party agents. External marketplace agents can be audited and
patched only through explicit project policy.

Shared agentic assets are authored here, not in generated runtime directories
or dotfiles. Add or update agents, skills, hooks, instructions, contexts, MCP
definitions, and project setup scripts under `.apm/`, then reinstall the package
in consuming projects.
