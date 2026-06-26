---
name: example-hybrid
description: Use to <do the thing>. The hybrid's own skill primitive.
---

# Example Hybrid Skill

A hybrid can ship a skill just like a pure skill package. The SAME nesting rule
applies: scripts this SKILL.md references with a file-relative path must live
under THIS skill directory.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run.sh` | The skill's own helper. |

`scripts/run.sh` resolves to
`.apm/skills/example-hybrid/scripts/run.sh` -- nested under the skill dir,
because SKILL.md uses file-relative paths.

Do NOT confuse this with the package-root `scripts/` directory, which in this
same hybrid holds the HOOK scripts referenced via `${PLUGIN_ROOT}/scripts/`.
Both directories exist in a hybrid; each primitive type uses its own.
