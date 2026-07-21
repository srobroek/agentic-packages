# Templates

Reference configs for this repo. Two kinds live here:

- **Package templates** (`<type>-package/`) -- one complete, minimal, working
  example per APM package type. Copy a directory into `packages/<your-name>/`,
  drop the `-package` suffix, rename the inner files, and fill in the content.
- **Manifest template** -- `project-apm.yml`, a per-project `apm.yml` starter.

The package templates are **templates, not catalog entries**. They live under
`templates/`, which is outside the `packages/**` glob and is not listed in the
marketplace `packages:` block in the root `apm.yml`. `apm pack` and the
marketplace enumerate `./packages/*` explicitly, so nothing here is ever
installed or published. The names all start with `example-` so they are
obviously not real.

## The six package types

Each lives in `templates/<type>-package/`:

| Type | Use when | Canonical layout (under the package dir) | #1 gotcha |
|------|----------|------------------------------------------|-----------|
| `skill` | One skill: a SKILL.md + helper scripts the model runs. | `apm.yml` + `.apm/skills/<name>/SKILL.md` + `.apm/skills/<name>/scripts/*.sh` | Skill scripts NEST under the skill dir, because SKILL.md uses file-relative `scripts/x.sh`. Root `scripts/` will NOT resolve. |
| `hooks` | Cross-tool lifecycle guards/automation (PreToolUse, etc.). | `apm.yml` + `.apm/hooks/<name>-claude-hooks.json` + `.apm/hooks/<name>-codex-hooks.json` + `scripts/*.sh` at package ROOT | Hook scripts live at the package ROOT, referenced as `${PLUGIN_ROOT}/scripts/x.sh`. Also: do NOT gate with the `"if"` matcher -- it can silently no-match; self-gate inside the script. |
| `agent` | One subagent definition the main thread delegates to. | `apm.yml` (`type: hybrid`, explicit `target`) + `.apm/agents/<name>.agent.md` + `.apm/agent-models.yml` | There is no `type: agent` in this repo. APM transforms portable agents for both runtimes; the package-local map restores Codex model fields after deployment. |
| `instructions` | Opt-in steering: path-scoped rules + on-demand context. | `apm.yml` + `.apm/instructions/<NN>-<name>.instructions.md` + `.apm/context/<name>.context.md` | Keep the always-on `.instructions.md` tiny and link to the heavier `.context.md`; set `applyTo` so the rule only loads for relevant paths. |
| `bundle` | Aggregate other packages; ship NO primitives of your own. | `apm.yml` ONLY (no `.apm/`), with a `dependencies.apm` list | `dependencies.apm` needs REPO-LOCATORS (`owner/repo/path#ref`), not `name@marketplace`. A bundle has no primitives. |
| `hybrid` | Ship your OWN primitives (e.g. skill + hooks) AND deps together. | `apm.yml` + `.apm/skills/<name>/...` + `.apm/hooks/...` + root `scripts/` + `dependencies.apm` | A hybrid has BOTH a root `scripts/` (hook scripts) and nested `.apm/skills/<name>/scripts/` (skill scripts). Put each script in the right one. |

## The two gotchas worth repeating

### 1. Skill scripts nest; hook scripts sit at the root

This is the script-location bug these templates exist to prevent:

- **Skill** scripts are referenced from SKILL.md with a **file-relative** path
  (`scripts/check.sh`), so they must live at
  `.apm/skills/<name>/scripts/check.sh` -- nested under the skill dir.
- **Hook** scripts are referenced from hook JSON as
  `${PLUGIN_ROOT}/scripts/guard.sh` -- resolved from the plugin root -- so they
  must live at the package-root `scripts/`.
- A **hybrid** has both at once. See `hybrid-package/`: `run.sh` is nested under
  the skill, `notify.sh` sits at the package root.

### 2. Self-gate hooks; do not rely on the `"if"` matcher

The `"if": "Bash(git push*)"` filter on a hook entry has been observed to
SILENTLY no-match -- the hook simply never fires, with no error -- which can let
the thing it was guarding through. Use a broad `matcher` (e.g. `"Bash"`) and
have the script read the payload from stdin, decide whether the command is in
scope, and exit 0 early when it is not. See `hooks-package/scripts/guard.sh`.

When parsing the payload, branch on `tool_input` type: it may be an object
(`{command: "..."}`) or a bare string, and `.tool_input.command // .tool_input`
throws on a string in jq, which would silently bypass the guard.

## Conventions shared by all types

- `apm.yml` keys: `name`, `version`, `description`, `author`, `license`,
  `type`, `target` (`all` | `claude` | `codex`), `includes: auto`, `category`,
  `tags`. `includes: auto` lets APM discover primitives under `.apm/`.
- Hook JSON ships as a Claude/Codex pair (`<name>-claude-hooks.json` /
  `<name>-codex-hooks.json`) so the package is cross-tool.
- Shell scripts must pass `/bin/bash -n` and
  `shellcheck -S warning` and target the bash 3.2 / BSD floor.
- A real package adds a `CHANGELOG.md` (release-please manages it); the
  templates omit it on purpose.
