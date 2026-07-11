---
name: write-docs
description: Write or review READMEs, docs, PR descriptions, specs, ADRs, and release text. Use when writing, rewriting, reviewing, or de-slopping any documentation.
---

# Write Docs

TRIGGER
+ writing or updating README.md, docs/**, or any doc a consumer of the artifact reads
+ writing a PR description, commit message, or hand-written release notes
+ "review this README", "deslop this", "rewrite the docs"
+ writing specs, ADRs, constitutions, CONTRIBUTING, runbooks (internal genre)
- authoring skills, steering, or agent definitions → write-agentic
- code comments and docstrings → language conventions

## Genre → reference

| Surface | LOAD |
|---|---|
| README.md, docs/**, anything a user of the artifact reads | references/consumer-docs.md |
| PR bodies, commit messages, hand-written release notes | references/change-comms.md |
| specs/, ADRs, constitutions, CONTRIBUTING, contributor/internal docs | references/internal-docs.md |

## Workflow

1. Classify the doc with the genre table; LOAD that reference before writing.
2. Author or rewrite against the genre rules plus the shared rules below.
3. Run `scripts/slop-lint.sh --genre <consumer|change|internal> <file>` → fix
   every ERROR; fix or justify each WARN in one line.
4. Verify: every claim holds against code at HEAD · every consumer example has
   a runnable test under `examples/` · lint exits 0.

## Rules (all genres)

MUST State what the artifact does — never effort, intent, process, or journey.
MUST Delete any adjective you cannot back with a number, benchmark, or feature list.
MUST One idea per sentence; lists and tables over prose paragraphs.
NOT Status language: "under construction", "WIP", "coming soon", "currently", "for now", "planned", "being specified".
NOT Slop lexicon — scripts/slop-lint.py owns the banned list; prose never restates it.
NOT History narration in a doc body ("previously", "we changed X to Y") — deltas belong to the change-comms genre only.
