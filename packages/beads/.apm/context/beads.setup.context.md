# Beads Setup

MUST Let the bd CLI own initialization and generated integration: bootstrap
  with `bd init --init-if-missing`, then verify with `bd where`, `bd setup
  claude --check`, `bd setup codex --check`, and `bd hooks list`.
MUST Repair an existing project's runtime integration with product commands:
  `bd setup claude --project` and `bd setup codex`.
MUST Use `bd hooks install --beads` only when the active project chose the
  product Git-hook bundle.
NOT Copies of product lifecycle hooks, managed instruction blocks, skill, or
  Git-hook shims in APM.
DEFAULT Project setup follows the repository's Beads version; global setup is
  for repositories that do not install project integration, not redundancy.
NOT `bd preflight` as an application quality gate -- Beads 1.1.0 hard-codes
  checks for the Beads Go repository; use repository-owned quality commands.
