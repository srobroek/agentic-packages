---
name: sniff
description: Audit a codebase for code smells, tech debt, and non-idiomatic code, map each finding to refactoring.guru smells/patterns/techniques, adversarially stress-test the recommendations, and produce a prioritized refactoring plan with impact, value, cost, severity, and backwards-compatibility. Drives the project's own linters and analyzers when installed and offers to install them when not. Use when the user asks to sniff the codebase, audit code quality or tech debt, find code smells, plan a refactor, check idiomatic style, or harden a cleanup pass. Advisory by default; applies low-risk refactors only on explicit approval.
---

# Sniff

Audit code for smells and non-idiomatic patterns, then produce a prioritized,
adversarially-vetted refactoring plan. Advisory by default — code is edited
**only** on explicit user approval (see step 7).

## ⛔ STOP — two questions before you touch the code

Do NOT detect the stack, run a tool, or dispatch a `bloodhound` until BOTH are
answered. These are blocking gates, not preferences — skipping them is the most
common failure of this skill. If you have already started scanning without
asking, stop and ask now.

1. **Which target?** If the user did not explicitly name one, ask — and wait:
   > "What should I sniff — your uncommitted changes, a specific dir/file, a
   > commit/PR, or the whole repo?"
   Do **not** assume whole repo. A whole-repo sweep is the most expensive option
   and almost never what a bare "sniff" means.
2. **Which tool depth?** After resolving the target, run
   `<skill-dir>/scripts/install-tools.sh --probe` (the skill dir = the directory
   holding this `SKILL.md`; see `$SNIFF_SKILL_DIR` below), show the coverage, and
   ask the user to pick **lean / full / custom** — and wait. Do **not** silently
   proceed on whatever tools happen to be installed, even if coverage looks fine.

Only exception: a **non-interactive** run (CI / you are yourself a sub-agent with
no user to ask). Then skip the prompts, use the named target or whole-repo,
proceed with installed tools, and record gaps. Interactive `/sniff` is NOT this
case — ask.

This SKILL is a router. Load the referenced file for each step; do not inline
its content here.

**Skill dir vs. target dir.** Tools run with cwd = the *target* repo (or a
worktree), but this skill's shipped assets (`scripts/`, `references/semgrep-rules/`)
live in the *skill* dir. Note the skill dir once at the start — the directory
containing this `SKILL.md` — and call it `$SNIFF_SKILL_DIR`. Reference every
shipped asset by an absolute path under it (e.g.
`"$SNIFF_SKILL_DIR/references/semgrep-rules/hardcoded-values.yml"`), never by a
skill-relative path that won't resolve from the target.

## Workflow

Run these in order. The full procedure, with stop/report points, is in
`references/workflow.md` — LOAD it before starting.

1. **Resolve target & detect stack.** Determine the target (whole repo, a
   module/dir, named files, a diff, a commit/range/branch, or a PR). **If the
   user did not name a target, STOP and ask which one — do not default to whole
   repo.** Once you have a target, LOAD `references/targeting.md`: resolve it to
   an explicit file list + base ref, decide in-place vs. worktree checkout, and
   confirm scope. Then detect every language/format present **in the target** and
   map each to its doc in `references/languages/index.md`.
2. **Probe & offer tools — mandatory blocking checkpoint (interactive runs).**
   Run `scripts/install-tools.sh --probe`, then **always** show the coverage
   (installed / missing / gaps) and **ask the user to choose** depth — lean /
   full / custom — using the overlap-and-gap guidance in `references/tooling.md`.
   **Stop and wait for their answer before Step 3, even if installed tools look
   adequate.** Install only approved bundles; never auto-install. (Non-interactive
   runs skip the menu: use what's present, record gaps.) See
   `references/installer.md`.
3. **Tool-driven detection.** For each detected language, run the installed
   tools per `references/tooling.md` (exact invocation + machine-readable
   output flag), respecting project config. Skip + warn + record an install
   hint for any absent tool. Collect findings; do not guess where a tool could
   have answered.
4. **Detection reading.** For smells tools cannot see (naming, design, idiom,
   abstraction level), read the code guided by the relevant
   `references/languages/<lang>.md`. LOAD only the docs for languages actually
   present. On a multi-language or large codebase, fan out the `bloodhound`
   agent — **one per detected language, in parallel** — building each Brief from
   `references/scout-brief.md`. bloodhound runs that language's tools, reads its
   code, and returns structured findings only. On a small single-language repo,
   read inline instead.
5. **Map to refactoring.guru.** For each finding, attach the smell name, the
   recommended refactoring pattern(s) and technique(s), and the canonical URL
   from `references/refactoring-catalog.md`. Fetch the full technique page only
   when the finding needs step-by-step detail (hybrid index+fetch).
6. **Adversarial pass.** Stress-test the recommendation set with the
   `refactor-challenger` agent so pragmatism holds (no parameter object for a
   one-arg function, no premature abstraction). Build its Brief from
   `references/adversarial-brief.md`. Drop or downgrade findings it refutes.
7. **Report & (optional) apply.** Emit the prioritized plan using
   `references/report-template.md`. If — and only if — the user explicitly
   approves applying a finding, apply **low-risk/mechanical** refactors only,
   then re-run the relevant checks from step 3 to verify. Anything risky or
   behavior-changing stays advisory.

## Targets

Sniff audits the whole repo or a bounded slice. **No default target — if the
user didn't specify one, ask before doing anything** (a whole-repo sweep is
expensive and rarely what's wanted on a bare "sniff"). See
`references/targeting.md`.

- **whole repo** · **module/dir** · **file(s)** — operate in place.
- **working-tree diff** — `git diff` of uncommitted changes, in place.
- **commit / range / branch / PR** — check the ref out into a throwaway git
  worktree so tools read the code at that ref; diff against the base.

Two rules make scoped runs correct: scope each tool by its **analysis class**
(local/relational/global/baseline — see `references/tooling.md`), and for ref
targets **headline breaking-change** findings vs. the base. Global analyses
(dead code, cycles, unused deps) are **skipped + noted** in scoped runs.

## Scope modes

- **quick** — error handling, obvious smells, hardcoded values, naming; skip the
  full tool sweep and adversarial pass.
- **full** (default) — all steps above.
- **plan-only** — steps 1–6; never apply, even on approval.

**Debug mode** (orthogonal — combine with any scope mode): OFF by default. Turn
ON **only when the user explicitly asks to debug the sniff RUN itself** — e.g.
"debug the sniff", "run sniff in verbose/debug mode", "show me how sniff is
working", "why did sniff drop/keep this file". A bare "debug" or the user
debugging *their own code* does **not** trigger it — the request must be about
sniff's own behavior. When ON, narrate each step's reasoning with terse `[debug]`
lines (exact commands + exit codes, what reduction dropped and why, keep/drop
verdicts with reasons, spawn decisions). It changes what's *shown*, never what's
*decided*. See `references/workflow.md` → "Debug mode" for the per-step contract.

## Hard rules

- Detection uses real tools; there is no built-in low-precision grep fallback for
  *smell* detection. If no tool is installed for a dimension, skip it and tell the
  user what to install. **Exception:** a deterministic exact-match pass is allowed
  — checksums (`shasum`/`cksum`) or `diff -q`/`git diff --no-index` — to find
  byte-identical or near-identical **duplicated files** across a repo/monorepo.
  Per-file linters are structurally blind to cross-file duplication, jscpd is
  rarely installed, and dual-emitted files / parallel crates are often the
  single highest-value finding. This is exact comparison, not heuristic grep.
  The checksum pass is a **floor, not a ceiling**: when parallel/mirrored files
  exist (per-binding crates, `*_pb` siblings, mirrored language bindings), also
  *read* a sample of the parallel set for **conceptual** duplication — a shared
  helper copied inside otherwise-divergent files is common and checksums miss it.
- Never edit code in steps 1–6. Apply only in step 7, only on explicit approval,
  always followed by a verification re-run.
- Load language docs and the refactoring catalog lazily — only what the detected
  stack needs.
- Rust note: the standard toolchain (clippy pedantic/nursery + rustc) already
  covers most dimensions; do not over-tool it. See `references/languages/rust.md`.

## References

| File | When to load |
|------|--------------|
| `references/workflow.md` | Always, before step 1 |
| `references/targeting.md` | Step 1: any non-whole-repo target (diff/PR/module/file) |
| `references/tooling.md` | Steps 2–3: tool catalog, invocation, overlap/gaps, analysis class |
| `references/installer.md` | Step 2: install-flow contract and bundles |
| `references/languages/index.md` | Step 1: route stack → language docs |
| `references/languages/<lang>.md` | Step 4: per-language smells/idioms/tools |
| `references/scout-brief.md` | Step 4: build the `bloodhound` Brief |
| `references/refactoring-catalog.md` | Step 5: smell → pattern → technique + URLs |
| `references/adversarial-brief.md` | Step 6: build the `refactor-challenger` Brief |
| `references/report-template.md` | Step 7: prioritized plan format |

## Agents

| Agent | Role | Spawned |
|-------|------|---------|
| `bloodhound` | Read-only per-language smell detector | Step 4, one per language, parallel |
| `refactor-challenger` | Read-only adversarial pragmatism critic | Step 6, once over the finding set |
