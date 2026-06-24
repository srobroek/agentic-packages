# SpecKit Setup (delegated)

SpecKit setup is owned by the **`speckit` APM package**, not by this skill.

When `--spec-mode full` (or `--speckit`) is selected, `project-setup.sh`:

1. Installs `speckit@<marketplace>` via apm (hard-fails if apm or the package is
   unavailable -- there is no inline fallback).
2. Runs the package's `setup-speckit.sh`, which scaffolds `.specify/`, registers
   the community extension catalog, installs + enables the required extension
   set (including `agent-assign`), and installs the workflow definitions
   (`speckit`, `speckit-quality`, `speckit-full`) from the package's local
   `workflows/` dir.

The authoritative extension list and workflow definitions live in the speckit
package under `.apm/skills/speckit-setup/scripts/`. Update them there; this skill
does not carry its own copy.
