---
name: write-agentic
description: Author or update skills, steering, or agent definitions using the standard templates and lint validation. Triggers on create/write/rewrite/optimize a skill, steering, or agent.
---

# Write Agentic Assets

One workflow for three asset kinds. Pick the template, author at source, lint.

LEGEND: ! hard rule · ~ default (override with reason) · ? confirm with user · → then · − anti-trigger

## Kind → template

| Writing a… | Template | Install shape |
|---|---|---|
| skill | references/template-skill.md | `packages/<pkg>/.apm/skills/<name>/SKILL.md` (+ `references/`, `scripts/`) |
| steering | references/template-steering.md | `packages/<pkg>/.apm/instructions/NN-<name>.instructions.md` pointer + `.apm/context/<name>.context.md` |
| agent | references/template-agent.md | `packages/<pkg>/.apm/agents/<name>.agent.md` (+ mirrored `agents/<name>.md`) |

## Workflow

1. ! Edit the authoritative source (APM package repo). Never generated runtime
   copies: `.agents/skills`, `.claude/agents`, `.claude/rules`, compiled
   `AGENTS.md`/`CLAUDE.md`.
2. Gather only what the repo cannot answer: purpose, trigger boundaries and
   non-triggers, install target, script/reference needs, external overlap.
3. LOAD the matching template and follow it exactly.
4. Run `scripts/lint.sh <file>` → fix every ERROR; justify or fix WARNs.
5. Review: triggers concrete · description ≤25 words · no hedges (lint catches
   the lexicon) · every rule carries `!`/`~`/`?` · output contract has verdict
   line + word cap (agents) · references one level deep.

## Format rules (all kinds)

- ! Sigil legend line once per file; every normative rule starts with a sigil.
- ! Enums in CAPS (`PASS|PARTIAL|FAIL`); decision tables as `situation → choice`.
- ! No hedge words for rules (lint list); replace with an observable condition.
- ! No model names in prose — tier routing lives in steering-subagent-routing.
- ~ Gotchas/env-facts may stay single sentences when a table would lose the trap.
- − User-facing text (reports, PR bodies) stays prose — never sigils.
