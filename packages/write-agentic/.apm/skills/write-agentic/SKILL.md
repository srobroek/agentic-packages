---
name: write-agentic
description: Author or update skills, steering, or agent definitions using standard templates and lint validation. Triggers on create/write/rewrite/optimize a skill, steering, or agent.
---

# Write Agentic Assets

One workflow covers three asset kinds. Pick the template, author at source, and lint.

Agentic assets are technical documents. Write the current contract a capable reader needs to use, verify, or reproduce. Use direct, concise sentences.

Omit these kinds of content:

- process narration
- chronology
- superseded behavior
- future promises
- operational archaeology
- primers
- tangents
- repeated rationale
- over-explanation

Retain:

- prerequisites
- safety constraints
- non-obvious invariants
- current limits
- reproducible actions

Change or migration communications may compare states. Decision records may preserve rationale. Plans and specifications may state future intent. Historical reports and data may preserve dated facts.

## Kind -> template

| Writing a... | Template | Install shape |
|---|---|---|
| skill | references/template-skill.md | `packages/<pkg>/.apm/skills/<name>/SKILL.md` (+ `references/`, `scripts/`) |
| steering | references/template-steering.md | `packages/<pkg>/.apm/instructions/NN-<name>.instructions.md` pointer + `.apm/context/<name>.context.md` |
| agent | references/template-agent.md | `packages/<pkg>/.apm/agents/<name>.agent.md` (+ mirrored `agents/<name>.md`) |

## Workflow

1. MUST Edit the authoritative source (APM package repo). Never generated runtime copies: `.agents/skills`, `.claude/agents`, `.claude/rules`, compiled `AGENTS.md`/`CLAUDE.md`.
2. Gather only what the repo cannot answer:
   - purpose
   - trigger boundaries and non-triggers
   - install target
   - script and reference needs
   - external overlap
3. LOAD the matching template and follow it exactly.
4. Run `scripts/lint.sh <file>`. Fix every ERROR. Justify or fix WARNs.
5. Review what lint cannot judge:
   - triggers are phrases a user would type
   - every reference is one level deep

## Format rules (all kinds)

MUST Enums use CAPS (`PASS|PARTIAL|FAIL`). Decision tables use `situation -> choice`.
MUST Avoid hedge words on normative lines. Replace them with an observable condition.

MUST No model names in prose. Tier routing lives in steering-subagent-routing.
MUST State the rule, never argue for it. A steering line is read as an instruction.

Write a reason only in these cases:

- The reason is the rule.
- It gives the measured number that set a threshold.
- It names the failure the rule prevents.
- It states an edge case the agent cannot infer.

DEFAULT Environment facts may stay single sentences when a table would lose the trap.
NOT User-facing text (reports, PR bodies): never use keyword prefixes.
