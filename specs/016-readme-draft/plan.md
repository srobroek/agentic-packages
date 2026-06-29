# Implementation Plan: 016 README Draft Module

**Spec**: `specs/016-readme-draft/spec.md` · **Status**: Draft (2026-06-29)
**Baseline**: full suite 731 passed, 4 deselected (post 007).

Smallest of the 014 split. Single phase: a new default-disabled module reusing the
agent→gate→python seam. No runner changes. OQ-5 resolved (lean d: no `when`,
init_only + reconcile=false). Gate on the full suite.

## Phase 1 — readme-draft module + tests + closeout

1. `modules/readme-draft/module.toml`: `[meta]` (repository/author like siblings);
   `[module]` id="readme-draft", default_enabled=false, reconcile=false; steps:
   `draft`(agent, steering="steering/draft.md") → `readme-gate`(gate, hardness="hard",
   allow_flag="allow-readme", init_only=true, message="Project README draft
   (agent-authored):\n{decision}\nWrite README.md?") → `write`(python). NO `when`.
2. `modules/readme-draft/module.py` (stdlib, `# ///` dependencies=[]): STEP_HANDLERS=
   {"write": _do_write} + the standard `import sdk` bootstrap + __main__ dispatch
   (copy from env-example/stack-adr). `_do_write`: read `readme_body` via
   `load_frozen_inputs`; `sdk.idempotent_write("README.md", readme_body,
   reconcile=False, inspect=args.inspect)`; ModuleResult + emit_result. No wall-clock.
3. `modules/readme-draft/steering/draft.md`: instruct the agent to read ONLY the
   frozen plan answers (project_name, org, layout, language, framework, resolved
   stack, license) and emit a single `readme_body` agent-steered answer (full Markdown
   README). Prohibit filesystem reads + shell-variable-looking tokens ($VAR,
   PLUGIN_ROOT). Mirror tone of an existing steering doc (env-example/steering/resolve.md).
4. Tests `tests/test_module_readme_draft.py` (mirror test_module_env_example.py):
   SC-001 (frozen readme_body + no README → write creates byte-identical); SC-002
   (existing README → skip, preserved); SC-003 (idempotent: create then skip); SC-004
   (manifest: default_enabled false, step order, gate hard/allow-readme/init_only, no
   when); no wall-clock in module.py.
5. Full-suite gate; flip spec Status → Implemented; write memory.md AS-BUILT; commit
   (unsigned per session).

## Risk notes

- Lowest-risk spec in the batch (small, default-disabled, no runner change, fully
  leaned). The one subtlety (OQ-5) is already resolved in the spec: do NOT add a
  `readme_exists` `when` predicate.
- Re-run the full suite in the main thread (don't trust the subagent -k count).
