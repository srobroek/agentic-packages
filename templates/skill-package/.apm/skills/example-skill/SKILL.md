---
name: example-skill
description: Use to <do the thing>. Trigger phrases go here so the model knows when to load this skill.
---

# Example Skill

This is the canonical SKILL.md layout. The frontmatter `name` MUST match the
directory name (`.apm/skills/example-skill/`) and the `apm.yml` `name`.

## Preferred Flow

1. Run `scripts/check.sh`.
2. If issues are auto-fixable, run `scripts/fix.sh`.
3. Re-run `scripts/check.sh` to confirm.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/check.sh` | Run the read-only check. |
| `scripts/fix.sh`   | Apply the auto-fixable subset. |

## Why script paths are RELATIVE here

The `scripts/check.sh` references above are resolved **relative to this
SKILL.md file**. That is the single most important convention for skill
packages and the source of the most common packaging bug:

- This SKILL.md lives at `.apm/skills/example-skill/SKILL.md`.
- So `scripts/check.sh` must live at
  `.apm/skills/example-skill/scripts/check.sh` -- i.e. NESTED under the skill
  directory, NOT at the package root.
- If you put the script at the package-root `scripts/` (which is correct for
  HOOKS, see the hooks template), the relative path `scripts/check.sh` will
  NOT resolve after install and the skill will be broken.

Contrast: hook packages reference scripts as `${PLUGIN_ROOT}/scripts/x.sh`
(absolute-from-plugin-root), so their scripts live at the package ROOT. Skills
use file-relative paths, so their scripts nest under the skill dir.
