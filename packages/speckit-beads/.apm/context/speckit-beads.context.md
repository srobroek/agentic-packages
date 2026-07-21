# SpecKit on Beads

SETUP
MUST Install all formulas from the APM `speckit` package into project
  `.beads/formulas/`; never source project policy from `~/.beads/formulas/`.
MUST Parse each installed formula and dry-run `speckit-feature` after copying.

FEATURE LIFECYCLE
MUST Pour one persistent molecule per feature with `bd mol pour
  speckit-feature --var feature=<NNN-slug>`.
MUST Tag the root with the spec ID and `spec_dir` metadata.
MUST Run `bd swarm validate <root-id>` before parallel execution.
DEFAULT Read computed progress with `bd swarm status <root-id> --json`.
NOT Create a swarm marker unless a coordinator must discover the run after handoff.

TASK STATE
MUST Create implementation tasks as children of the formula's `implement` step
  with `--spec-id <NNN-slug>`; never author `specs/*/tasks.md`.
MUST Keep `implement` open until every child is closed; verify the child set
  before closing `implementation-complete`.
DEFAULT Read task state with `bd query "spec_id=<NNN-slug>" --json`, `bd ready`,
  or `bd children <implement-step-id> --json`.

GATES AND REMEDIATION
MUST Resolve human gates only after the named evidence is approved.
MUST Bond `mol-speckit-fix-findings` for runtime review, QA, or security findings.
MUST Bond `mol-speckit-iterate` when approved requirements or approach change.
MUST Preview bond direction with `--dry-run`; the blocked feature step resumes
  only after its persistent remediation molecule closes.
NOT Encode runtime findings with formula step conditions.

CLOSEOUT
MUST Close the final step, then the feature root, then perform one terminal
  `bd dolt push` only when the active authority policy permits it.
DEFAULT When sync authority is absent, report the exact pending command.
