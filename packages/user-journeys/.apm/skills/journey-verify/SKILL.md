---
name: journey-verify
description: >-
  Validate user journeys against the running product: drive each step, triage mismatches with intent gating, amend journeys, record runs, report findings.
---

# journey-verify

Validate journeys against reality. `FORMAT.md` in the journeys directory is
normative for every artifact this skill writes. Read `README.md` (config)
and the target `journey.md` files first.

For a single journey, run inline. For several, spawn one `journey-validator`
agent per journey (respect profile `exclusive: true` — serialize journeys
sharing an exclusive profile).

## 1 — Resolve the driving strategy

From the journey's `interfaces:` pick a profile from README.md. The profile
gives kind, launch/reset guidance, and doc pointers; you resolve the
concrete driver from that plus project knowledge (browser automation for
web, app-driving MCP for desktop, direct invocation for CLI/API). Bindings
are improvised per run, never stored per step.

State plainly in the run file which interface was actually driven. If you
can only reach a lower-fidelity surface than the user's (e.g. API instead
of UI), say so and classify UI-specific expectations `blocked`, not `pass`.

## 2 — Preflight

Establish preconditions (P-ids) using profile reset/fixture guidance. A
precondition you cannot establish makes dependent steps `blocked` — never
fake state unless the profile explicitly documents stand-ins.
Record the git commit under validation.

## 3 — Execute steps

In order, for each step: perform **Do**, observe, judge every **Expect**
and **Expect (negative)**. Capture evidence proportionate to the claim —
screenshots/snapshots where the driver supports them, command output,
response bodies. A step with any failed expectation is `fail`; steps
unreachable after a failure are `blocked`. Continue past failures when
later steps are independently reachable.

## 4 — Triage every mismatch

Exactly one triage per mismatch (taxonomy in FORMAT.md). For each candidate
mismatch, search for **intent evidence** before concluding: merged
PRs/commits since the journey's last amendment, changelog, and the repo's
intent-evidence sources listed in README.md.

- Evidence found → `intended-change`.
- Doc wrong about long-standing reality (predates recent changes) →
  `correction`.
- No evidence → `suspected-regression`.
- Doc and reality disagree and neither is clearly right → `product-question`.
- Harness/fixture/driver at fault → `environment` (run file only).

## 5 — Amend (intent-gated)

- `correction`: fix the journey body. No Δ entry, no version bump.
- `intended-change`: update the body, bump `version`, add a Δ entry citing
  the evidence, `by: journey-validator (intent-gated)`.
- `suspected-regression` / `product-question`: journey unchanged.

## 6 — Record and report

1. Write `runs/<UTC>.md` per the run-file spec: frontmatter with per-step
   results, body sections for every non-pass step with evidence and triage.
2. File `suspected-regression` and `product-question` findings through the
   configured reporter (github-issues via `gh`, or TRACKER.md). Every
   finding embeds the `journey-finding` block from FORMAT.md and the human
   sections (Summary / Repro / Expected vs Observed / Evidence / Triage
   rationale) with severity P1–P3.
3. Update run frontmatter `findings:` with assigned ids. Reindex
   (`journeys.py index`).
4. Commit journeys-dir changes (amendments, run file, index) as
   `journey(J<id>): validate v<version> — <result>`.

## 7 — Close the loop

Report to the caller: per-journey result, amendments made (with evidence),
findings filed. Then offer next actions — do not auto-run them when invoked
directly: consolidation (`journey-consolidate`) if green and the delta log
has entries; the fix loop per README.md `fix_loop` for regressions
(`journey-campaign` owns the autonomous loop).
