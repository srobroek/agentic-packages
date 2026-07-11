# Project Docs

Docs-file conventions: see steering-project-structure (project-structure.docs-files.context.md).

Use Astro for marketing or content docs, VitePress for technical docs, and
Storybook for shared UI or design systems.

## Shipped Docs Describe Current Behavior

Shipped docs describe current behavior only. Never document unshipped features —
not in callouts, not in future tense. Land docs in the same PR as the implementation.

## Write For The Released Artifact

Write every doc, README, spec, and ADR for the released, steady-state artifact,
not the current moment or work in progress. Drop transient status language
("Draft", "currently", "for now", "at the moment", "planned", "WIP", "coming
soon", "we're doing X") and any "Status" section that goes stale. Name a section
for what it is — "API", not "Planned API".

A greenfield artifact has no history. State the current design as the design; do
not narrate change ("revised", "policy changed", "we dropped X", "previously Y,
now Z") or add dated "(revised 2026-…)" notes.

Justify a library, tool, or dependency choice only when the reason is
load-bearing for the reader — a real constraint or tradeoff. State that in one
line; otherwise just state the choice. Omit filler rationale ("popular",
"standard", "battle-tested", "aligns with <other project>").

Keep each artifact self-contained. Reference another repo, team, project, or
prior work only when this project depends on or uses it — no "matches how <other
repo> does it" without an actual code or dependency link.
