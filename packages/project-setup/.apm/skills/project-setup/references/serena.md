# Serena Setup

Use this reference when a project selects Serena for semantic code tools.

## Install Shape

Install Serena through APM MCP packages, not by hand-writing MCP config:

```bash
apm install mcp-serena@srobroek-agentic
```

The package starts Serena with `--project-from-cwd` so the same global MCP
package can resolve the active project per repository. Its launcher selects
Serena's `codex` or `claude-code` context from the parent harness and supports
an explicit `SERENA_MCP_CONTEXT` override for unusual launchers.

Serena itself is installed globally through the chezmoi-managed mise config as
`pipx:serena-agent` with Python 3.13:

```toml
"pipx:serena-agent" = { version = "latest", uvx_args = "--python 3.13 --prerelease=allow" }
```

## Project Setup

1. Detect project languages from source files, package manifests, and existing
   toolchain config.
2. Read the Serena language-server index `serena-language-servers.json`. It
   ships with the `mcp-serena` package (under its `references/`); locate it in
   that installed package, or skip if `mcp-serena` is not installed.
3. For each detected Serena-supported language, run the listed `mise use ...`
   commands from the project root. If the index cannot be found, skip the
   `mise` pre-install and let `serena project create` detect languages.
4. Do not write docs-only language keys listed under
   `runtime_validation.docs_language_keys_not_in_installed_runtime` to
   `.serena/project.yml`.
5. Create or repair Serena project config from the project root:

```bash
serena project create
```

For an empty project or an explicit language choice, pass languages directly:

```bash
serena project create --language python --language typescript
```

For large repositories, index after creation:

```bash
serena project index
```

Use `.serena/project.yml` for versioned project facts: languages, ignored paths,
write access, additional workspace folders, initial prompt, and project-specific
mode defaults. Use `.serena/project.local.yml` for local-only overrides.
If the user's global git ignore excludes `.serena/`, add a repo-level unignore
for `.serena/project.yml` and keep `.serena/project.local.yml` plus
`.serena/memories/` ignored.

For TypeScript monorepos, configure `additional_workspace_folders` only for
workspace folders that need cross-package reference discovery. Serena currently
documents this support for TypeScript.

## Modes

Serena modes are selected at startup or project activation, not through an
ordinary in-session toggle.

Global default:

```yaml
base_modes: []
default_modes:
  - interactive
  - editing
```

Do not globally enable `planning`, `one-shot`, or `query-projects`:

- `planning` excludes editing and shell tools, so use it for read-only planning
  sessions.
- `one-shot` is for autonomous single-task sessions and should not normally be
  combined with `interactive`.
- `query-projects` exposes cross-project query tools and should be enabled only
  for projects or sessions that have related Serena projects to query.

Installed Serena 1.2.0 supports `base_modes`, `default_modes`, and repeatable
CLI `--mode`. Current docs also mention `added_modes` and `--add-mode`, but the
installed 1.2.0 CLI does not expose `--add-mode`. Do not generate `added_modes`
or `--add-mode` until the runtime supports them.

Because `--mode` overrides default modes, re-state defaults when adding a
temporary mode:

```bash
serena start-mcp-server --context codex --project-from-cwd \
  --mode interactive \
  --mode editing \
  --mode query-projects
```

## Hooks

Serena docs recommend hooks for Codex and Claude Code to reduce agent drift.
Do not install them project-locally by default during setup. Report them as an
optional global follow-up unless the user explicitly wants hook rollout.

Codex hook shape from the docs:

- enable `[features].codex_hooks = true`
- add `serena-hooks activate --client=codex` on `SessionStart`
- add `serena-hooks remind --client=codex` on `PreToolUse` with Bash matcher
- add `serena-hooks cleanup --client=codex` on `Stop`

Claude Code docs also recommend starting Claude Code with:

```bash
claude --system-prompt="$(serena prompts print-cc-system-prompt-override)"
```

Do not change Claude Code global startup behavior unless the user explicitly
asks, because Claude may be managed separately.

## Memories

Serena project memories live in `.serena/memories/`. Global memories live under
`~/.serena/memories/global/`.

Keep archived memories out of normal Serena memory listings with the global
configuration:

```yaml
ignored_memory_patterns:
  - "_archive/.*"
  - "_episodes/.*"
```

Serena has a `no-memories` mode if a session should disable Serena memory
tools. Do not assume this disables Codex's own memory or steering injection.
No verified Codex CLI setting was found here that disables Codex memory because
Serena is present.
