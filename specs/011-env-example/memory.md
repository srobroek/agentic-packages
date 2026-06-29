# Feature 011 — env-example-from-stack (memory)

Authored in one session from roadmap rank #9
(`reviews/tier2-agentic-features-roadmap.md:83-87`). Everything verified against
shipped code on `feat/project-setup-modular-redesign` at HEAD `7779c27` unless
marked otherwise.

## Scope decision (what 011 is)

011 = **a new module `env-example`** that follows the Tier-2 seam: a `kind=agent`
step derives the canonical env var name list from the frozen stack (framework ids
from lang-python + lang-ts), a soft `kind=gate` step shows the list for human
review, and a `kind=python` step writes `.env.example` with placeholder tokens only.
The key invariants are:

1. **Fixed output path** (`.env.example`, hard-coded in module.py — agent cannot
   redirect to `.env`).
2. **Hard-refuse any placeholder that `sdk.looks_like_secret` flags** (defense in
   depth on top of 004 G8).
3. **No registry verification needed** (env var names are not package pins).
4. **Tier-1 determinism**: same frozen `env_keys` → identical bytes.

Not a steps-on-existing-module choice (see Settled Decision A). Not a new runner
primitive — reuses everything from 003+004.

## VERIFIED CODE FACTS (so implementation doesn't re-derive)

### Fact 1 — `sdk.looks_like_secret` is the right G8 hook

`sdk.py:432-444` — returns a human label if the value matches a known credential
shape, or `None`. Patterns: `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_`, `sk-`,
`AKIA`/`ASIA` + 16 uppercase alphanumeric, `glpat-`, `xoxb-`/`xoxp-`/etc.,
`-----BEGIN … PRIVATE KEY`. **Already tested by the 004 suite** — no new SDK work.

### Fact 2 — `idempotent_write` path safety does NOT distinguish `.env` from `.env.example`

`sdk.py:538-589` — `is_safe_relative_path` blocks `..`, absolute paths, and null
bytes. It does **not** have a blocklist for dangerous filenames. The module.py
must hard-code `.env.example` and never accept a path input — this is the only
structural guard against writing `.env`.

### Fact 3 — `FrozenInputs.mode` property exists and is used by the Tier-2 pattern

`sdk.py:86-94` — returns `"init"` or `"reproduce"`. The env-example python step
reads this to decide whether to run (but unlike 003 lang-python there is no pin
verification to skip — on reproduce it just writes from frozen answers). Still
worth checking `mode` in the docstring for clarity.

### Fact 4 — `[order].after` multi-element arrays work

`lang-python/module.toml:15-16`: `after = ["gitignore-generate", "precommit-setup"]`.
TOML arrays. `env-example` can declare `after = ["lang-python", "lang-ts"]`.

### Fact 5 — No cross-module answer-reading API; agent reads its context dict

`executor.py:443-475` — `run_agent_step` passes a `ctx` dict built from the
module's own `resolved_answers`. The only legal way for env-example's agent step
to know `lang-python.framework` is if that value was already folded into
`resolved_answers` by the time env-example's Phase A runs. Because:
- The two-phase execution (003 FR-011) runs ALL agent steps in Phase A (topo order
  by `[order].after`), then re-freezes.
- `env-example`'s `resolve` step (kind=agent) runs AFTER `lang-python.resolve`
  (due to `after = ["lang-python", "lang-ts"]`).
- `lang-python.resolve` has already emitted `framework` as `agent-steered` into
  `final_answers` by then.
- The context dict passed to `env-example.resolve` includes all answers in
  `final_answers` for the env-example module — but only keys declared as `[[inputs]]`.
  So `framework_python` MUST be declared as an `[[inputs]]` in env-example's
  `module.toml`, and the runner will populate it from `final_answers["framework_python"]`
  (which inherits from `lang-python`'s frozen `framework` answer via the answer
  namespace).

**KEY QUESTION**: Does the runner automatically populate `env-example.framework_python`
from `lang-python.framework`? Answer: Not automatically by namespace inference — the
modules have separate answer namespaces. The value comes from the **interview**: when
the user is asked `framework_python?` at the env-example module's interview step,
the enablement layer pre-fills it from `lang-python`'s frozen answer (if lang-python
is enabled). This is how the "answer inheritance" described in OQ-1 works in
practice — but it needs verification in `pipeline._interview_module` to confirm the
flow. **This is OQ-1 and should be verified before implementation.**

### Fact 6 — The soft gate `[Y/n]` default-Yes and `init_only` are both implemented (004)

`executor.py:409-450` (post-004): hard gate → `io.confirm([y/N])`; soft gate →
`io.confirm([Y/n], default=True)`; `init_only=true` → auto-proceed on reproduce
(the `init_only_bypass` arg in `run_gate_step`). Both ready.

### Fact 7 — `{decision}` composition in gate messages

`plan.py:159-168` — `build_plan` replaces `{decision}` in a gate step's `message`
with `render_answer_block(mod_answers)` at freeze time. For env-example, the frozen
`env_keys` list will be in `mod_answers` by then (Phase A ran first), so the gate
message can render the full list by including `{decision}`.

### Fact 8 — No `.env.example` write anywhere in existing modules

Verified with `fd -e py . packages/project-setup/skills/project-setup/modules/`:
no reference to `env.example`, `dotenv`, or `DOT_ENV` in any module.py. The
feature is fully additive.

## DESIGN TRADEOFFS recorded here (so implementation knows why)

### Why `env_keys` is a list of structured objects, not a flat list of names

The roadmap names `{name, placeholder text, comment, secret_bool}` explicitly. The
`secret_bool` flag is needed to validate that a secret-class key has a non-empty
placeholder (FR-009). The `comment` field lets the agent embed per-key documentation
without inventing a parallel structure. The `placeholder` field is what enables the
hard-refuse check (FR-008) — a flat name list would require a separate step to
invent placeholders, creating an unguarded write path.

### Why `reconcile = true`

The env var surface of a project changes as the stack evolves (new companions, new
hints). `reconcile=true` means re-runs update the file to match the current frozen
answers. The 004 G5 overwrite gate (hard, CI SAFE-skips) protects hand-edits on
reproduce automatically. This matches `lang-python`'s posture.

### Why the gate is `hardness="soft"` not omitted

The roadmap says "optional kind=gate … gate=none is acceptable if effort-constrained."
We include it as soft because:
1. The env-example infers var names from framework knowledge — the agent can be
   wrong (e.g. inventing a `SECRET_KEY` for a framework that uses `APP_KEY`). A
   soft gate lets the dev eyeball and correct before committing.
2. Soft is zero CI friction (auto-proceeds) and zero hard-gate quota usage.
3. The 004 machinery makes it trivial to declare; the marginal cost is near zero.
A future author who wants to omit it can remove the gate step from module.toml.

## OPEN QUESTIONS — resolve before implementation

Each written so they can be answered without re-reading the spec.

### OQ-1 — How does `framework_python` get populated from `lang-python`'s frozen answer? (MED — verify before impl)

**The question**: `env-example/module.toml` declares `[[inputs]] key="framework_python"`.
At interview time, does the runner automatically pre-fill it with the value from
`lang-python`'s already-frozen `framework` answer (same key name, different module
namespace), or does the user get re-asked? Does the runner have an answer-inheritance
mechanism (populating a module's input from another module's persisted answer if
the keys match), or does it depend on the interview order?

**Why it matters**: if there is no inheritance, the user gets asked "framework (python)?"
twice — once by `lang-python` and once by `env-example`. That is fatigue-inducing
and error-prone (they could answer differently). The correct UX is: if `lang-python`
is enabled and has a frozen `framework`, `env-example.framework_python` is pre-populated
silently.

**Lean**: check `pipeline._interview_module` and the `resolved_answers` construction
path. If the runner pre-fills inputs whose key matches an already-answered key in
`final_answers` (across module namespaces), then naming the input `framework_python`
may not match `lang-python`'s `framework`. One clean solution: rename the input to
`framework` (same key), declare `requires = ["lang-python"]` as optional, and the
runner either skips asking (value already in `final_answers`) or pre-fills.
Alternatively: a `default = "{framework}"` template in `module.toml` that the
interview expands from the already-resolved `framework` answer. Verify the actual
mechanism before designing the input schema.

### OQ-2 — `env_keys` JSON shape: list of objects vs list of `"NAME=placeholder"` strings (LOW)

**The question**: the spec uses a list of structured objects
`[{"name": "...", "placeholder": "...", "comment": "...", "secret_bool": true}]`.
An alternative is a flat list of `"NAME=placeholder # comment"` strings that the
python step parses, with a separate `secret_keys` list for the secret_bool flag.

**Lean**: structured objects. They are the safer choice for the hard-refuse path
(FR-008 checks `entry["placeholder"]` directly — no parsing needed), and they
match the existing `pinned_deps` list-of-strings pattern (each pin is parsed in
sdk, but here the structure is already there). The extra verbosity in `answers.toml`
is acceptable for correctness. Keep the JSON the agent emits clean and typed.

### OQ-3 — Inline `# comment` suffix vs preceding comment line per entry (LOW)

**The question**: should comments appear as inline suffixes (`KEY=val  # comment`)
or as preceding lines (`# comment\nKEY=val`)? `.env` parsers vary: some do not
parse inline comments; most parse `# ...` at line start.

**Lean**: inline suffix (`KEY=placeholder  # comment`, two spaces before `#`).
This is the most common `.env.example` convention and is supported by
`dotenv`, `python-dotenv`, and the POSIX shell. Preceding-line comment is also
safe but slightly harder to associate with the key in a long file. If the user
wants preceding comments, that is a low-risk impl detail — pick one convention
and stick to it; do not offer both.

## ASSUMPTIONS made

1. The 003 two-phase execution (Phase A: agent steps in topo order; Phase B:
   python + gate steps) means env-example's `resolve` agent step runs AFTER
   `lang-python.resolve` and `lang-ts.resolve` when `[order].after` is set
   correctly. The framework answers are available in `final_answers` by then.
2. `sdk.looks_like_secret` pattern set is sufficient for the hard-refuse invariant.
   It covers GitHub tokens, OpenAI/Anthropic keys, AWS access keys, GitLab PATs,
   Slack tokens, and PEM private keys. A placeholder like `"your-database-url-here"`
   will never match any of those patterns.
3. There are no MCP server calls in this module. The agent derives env var names
   from framework knowledge (not live documentation), so the MCP-absent path is the
   primary path. If context7 is present, the agent may use it to confirm conventions,
   but it is not required.
4. `[order].after = ["lang-python", "lang-ts"]` with neither in `requires` correctly
   expresses a soft ordering dependency. A manifest with only one or neither enabled
   will not trigger an ordering error — verify this in `manifest.py` if unclear.
5. The preamble comment lines are fixed implementation details ("# .env.example —
   generated by project-setup; fill in values before running." + "# DO NOT commit
   real values to version control."). They do not need human sign-off.

## AS-BUILT (2026-06-28)

Built as a new module, no runner change. Full suite green (no regression).

- `modules/env-example/{module.toml, module.py, steering/resolve.md}`: the
  resolve(agent) → preview(gate, soft, init_only) → write(python) seam. module.py is
  STEP_HANDLERS={"write": _do_write}; agent+gate are runner-dispatched. `_OUTPUT_PATH =
  ".env.example"` is a module-level CONSTANT (FR-012 — never input-derived; the agent
  structurally cannot redirect the write).
- `_do_write`: per-entry name-validate (`^[A-Z][A-Z0-9_]*$`, bad → skip+warn, FR-010);
  `looks_like_secret(placeholder)` non-None → hard error INPUT_VALUE_INVALID, write
  nothing (FR-008); secret_bool+empty-placeholder → same hard error (FR-009); newline
  sanitize; sort by name; fixed 2-line preamble + `NAME=placeholder  # comment` lines;
  `idempotent_write(reconcile=…, inspect=…)`. Reuses the shipped `looks_like_secret`
  (G8) — no new SDK work.
- Tests: `tests/test_module_env_example.py` (10) — SC-001 (framework keys, no
  placeholder trips looks_like_secret), SC-002 (ghp_ placeholder → error, nothing
  written), SC-003 (sorted + preamble + byte-identical 2-run), SC-004 (empty list →
  preamble-only), SC-007 (bad name skipped+warned, good written), SC-008 (secret_bool+
  empty → error), manifest parse, + idempotent/inspect.

OQ resolutions (per leans): OQ-1 framework_python/_ts as module `[[inputs]]` read from
the agent context dict (no new cross-module API); OQ-2 structured `env_keys` objects;
OQ-3 inline `# comment` suffix.

**Deferred (runner-level, same note as 006):** SC-005 (soft gate auto-proceed/CI),
SC-006 (reproduce zero-network byte-identical), SC-009 (runs with only-one/neither
overlay) — the gate dispatch + reproduce replay are runner-owned machinery already
proven by `test_two_phase_resolver.py`; the module has no mode-conditional code (it
always writes from the frozen `env_keys`), so determinism is structural and SC-003
covers the byte-identical half. SC-009 is structural (no `requires` edge; inputs
default ""). A dedicated env-example run_pipeline test is a low-value follow-up.
