# Bootstrap Flow

## Inputs

Collect every configurable choice that is not already supplied. Use
`interactive-options.md` as the checklist and `script-capabilities.md` as the
static executor contract. Do not silently assume project shape, stack,
orchestration, Spec mode, APM behavior, or GitHub behavior. Do not run setup
scripts for flag discovery during the interview.

## Execution

- New project: `scripts/project-setup.sh`
- Monorepo package: `scripts/package-add.sh`
- APM marketplace discovery: `scripts/apm-discover.sh`
- Language overlays: `scripts/setup-*.sh`
- Full SpecKit extension install: `scripts/speckit/speckit-setup-all.sh`

Execution starts only after the user confirms the generated command, selected
APM packages, selected agents, selected skills, and verification steps.

## Codex Sandbox Escalation

Run the main `scripts/project-setup.sh` executor outside the Codex sandbox when
it writes protected bootstrap paths. In `workspace-write`, Codex protects
`.git`, `.codex`, and `.agents` as read-only even when the repository root is
writable. Project setup owns those paths, so use
`sandbox_permissions = "require_escalated"` with a justification that the setup
executor writes protected bootstrap paths.

If the executor reports a protected-path preflight failure, rerun the exact same
command with escalation instead of trying to chmod, copy, or manually recreate
the protected directories from inside the sandbox.

## APM And AGENTS Layout

- APM owns shared steering.
- Project setup registers and browses the `srobroek-agentic` APM marketplace
  before recommending skills or agents. Use `scripts/apm-discover.sh`, which
  wraps `apm marketplace list`, registration/update, and marketplace browse.
  By default it registers and browses all known remote marketplaces:
  `srobroek-agentic`, `wshobson-agents`, and `voltagent-subagents`. Add
  `--extra-marketplace <name=owner/repo>` for more catalogues. Keep package
  names scoped as `<package>@<marketplace>`.
- Recommendation priority comes from the canonical preference index at
  `agentic-packages/indexes/apm-package-preferences.json` when available. The index is
  not the full selectable package set; every package shown by remote marketplace
  browse is selectable. When the user selects any package, including one not
  already in the preference index, rerun discovery with matching `--profile`
  values, repeatable `--select-package <package@marketplace>`, and a short
  `--selection-note` so the package is added or promoted for future setups.
- Use `apm marketplace browse <marketplace-name>` for the setup recommendation flow. Use scoped `apm search <query>@<marketplace>` only to narrow an already-known capability after browsing.
- If `apm` is not directly available, run the same commands through
  `mise exec -- apm ...` or `uv tool run --from apm-cli apm ...`.
- Do not inspect local skills checkouts, local `srobroek/agentic-packages`
  checkouts, `~/.config/agentic-tools`, or raw `marketplace.json` files for
  recommendation discovery.
- Codex receives generated scoped `AGENTS.md` through `apm compile --target codex`.
- Claude Code receives generated scoped `CLAUDE.md` through
  `apm compile --target claude`.
- Keep hand-written root `AGENTS.md` minimal when generated APM steering is in use.
- The main executor installs selected APM packages and compiles Codex and Claude
  steering by default. Use explicit opt-out flags only when APM work is
  intentionally deferred.

## Failure Handling

- If `specify init` fails, rerun the exact retry command emitted by the script.
- If extension install partially fails, rerun only failed `specify extension`
  steps.
- Do not replace supported package/setup commands with manual file copying.
