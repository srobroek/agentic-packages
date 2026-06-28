# Report Template

The step-7 output. Fill this in. Every surviving finding (post-adversarial) gets
a row in the plan with **impact, value, cost, severity, and
backwards-compatibility**. Order the plan by value-per-cost, highest first.

Keep it concrete: every finding cites `file:line` and a refactoring.guru mapping.
Drop sections that do not apply rather than padding them.

---

```markdown
# Sniff Refactoring Plan — <target>

**Target:** <whole repo / module `src/x` / diff / commit `abc123` / PR #42 / files>
**Scope mode:** <quick|full|plan-only>  ·  **Base ref:** <none | `main` | PR base>
**Languages:** <list>  ·  **Date:** <YYYY-MM-DD>

Framing (match the target): a **diff/PR/range** report is a *regression review*
("what did this change make worse, and what did it break?"); a **module** report
is a *mini-audit*; a **file** report is a *focused read*. Lead accordingly.

## Summary
- Findings: <n> (after adversarial filter; <m> dropped, <k> downgraded)
- By severity: critical <n> · high <n> · medium <n> · low <n>
- Headline: <one sentence — the single most valuable thing to do first>

## ⚠️ Breaking API changes vs. `<base>`  (ref targets only; omit if none)
Top-severity. Only when the target is a diff/PR/range/branch and a contract
(`.proto`, GraphQL SDL, OpenAPI) changed against the base ref.

| Contract | Change | Breaking? | Tool | Migration / mitigation |
|----------|--------|-----------|------|------------------------|
| api.proto:Field 4 | renumbered 4→5 | YES (wire) | buf breaking | reserve 4; never reuse |

## Tool coverage
| Dimension | Tool | Class | Ran? | Notes / install hint if skipped |
|-----------|------|-------|------|---------------------------------|
| complexity | lizard / golangci-lint | local | yes/SKIPPED | ... |
| dead code | knip / vulture | global | SKIPPED (scoped) | needs whole-project; run a full sniff |
| ... | ... | ... | ... | ... |

(Gaps are honest: a SKIPPED row means that dimension was not checked. In a scoped
run, global-class dimensions are expected to be SKIPPED — say so explicitly.)

Two coverage-honesty rules so a skipped tool isn't over-reported as a real gap:
- **Covered-by-meta-linter → not a gap.** If a primary meta-linter that ran
  already covers the dimension, a missing/`SHIM` point tool is **LOW or
  "covered"**, not a degraded gap. E.g. ruff `C901` / clippy `cognitive_complexity`
  subsume a missing `lizard`, so a `lizard SHIM` on a Python- or Rust-only target
  is not a complexity gap.
- **State the skip reason precisely.** "SKIPPED (scoped — global class)" vs.
  "SKIPPED (not installed)" need different remediation. If a global-class tool is
  *both* out-of-scope and not installed, report it once as **SKIPPED (scoped)** —
  the scope reason takes precedence. If the detected stack has no global-class
  tools at all (docs/config-only), mark global analyses **N/A**, not SKIPPED.

## Prioritized refactoring plan
Ordered by value ÷ cost. Severity = severity of the *current* smell, not the fix.

| # | Finding (file:line) | Smell → refactoring | Severity | Impact | Value | Cost | Back-compat | Apply tier |
|---|---------------------|---------------------|----------|--------|-------|------|-------------|------------|
| 1 | path:line | <smell> → <refactoring> (guru URL) | crit/high/med/low | what improves | high/med/low | S/M/L | safe / breaking: <surface> | mechanical / assisted / manual |

Legend:
- **Impact** — what gets better (readability, correctness risk, perf, change-cost).
- **Value** — benefit if done (high/med/low).
- **Cost** — effort/blast radius: S (one site, mechanical), M (a few files),
  L (cross-cutting, needs design).
- **Back-compat** — `safe`, or `breaking:` + the exact surface (public signature,
  wire/serialized format, config key, documented behavior).
- **Apply tier** — `mechanical` (sniff may apply on approval: rename, extract,
  inline, guard clause, dead-code removal), `assisted` (needs review),
  `manual` (design change; advisory only).

## Detail (per finding, top N)
### <#> <short title> — `file:line`
- **Smell:** <name> (`guru URL`) — <evidence: metric / quoted code / tool rule id>
- **Why it matters:** <impact in this codebase, concretely>
- **Recommended:** <refactoring> (`technique URL`) — <one-line mechanic>
- **Cost / blast radius:** <call sites, tests, surfaces touched>
- **Back-compat:** <safe | the surface that breaks and how to stage it>
- **Adversarial note:** <what refactor-challenger said — confirmed / scoped-down>

## Dropped & downgraded (transparency)
| Finding | Verdict | Reason (from refactor-challenger) |
|---------|---------|-----------------------------------|
| ... | DROP/DOWNGRADE | false positive / over-abstraction / non-idiomatic-but-fine / not worth cost |

## Adjacent (out of scope) — scoped runs only; omit if empty
Real issues a tool surfaced just outside the target (e.g. the function a changed
line calls). Listed, not mixed into the plan above — the user chose the scope.

| Finding (file:line) | Smell | Why flagged | In scope to fix? |
|---------------------|-------|-------------|------------------|
| ... | ... | adjacent to a target change | no — would need a wider sniff |

## Applied this run (only if step 7 apply ran)
| Finding | Change | Verification | Result |
|---------|--------|--------------|--------|
| ... | <refactor applied> | <command re-run> | pass/fail |
```

---

## Rules for filling it in

- The **Dropped & downgraded** section is not optional in full mode — it shows
  the pragmatism filter worked and explains what was deliberately not flagged.
- Never mark a finding `mechanical` if its back-compat cell is anything but
  `safe`. Public-surface changes are at least `assisted`.
- If nothing survives the adversarial pass, say the codebase is clean on the
  dimensions checked and list the coverage gaps — do not invent findings.
- The "Applied this run" table appears only when the user approved applying and
  the mode was not plan-only.
