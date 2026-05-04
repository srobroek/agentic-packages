---
name: interface-design
description: Design, audit, and normalize product interfaces with intent, DESIGN.md authority, and systematic UI consistency. Use when building or reviewing dashboards, admin panels, SaaS apps, tools, settings pages, forms, data interfaces, component systems, or when the user asks for UI craft, design-system, or interface consistency.
---

# Interface Design

Design product interfaces with craft, memory, visual inspection, and
consistency. This is for apps, dashboards, tools, admin panels, settings,
data-heavy screens, and interactive products. It is not for marketing pages
unless the user explicitly asks to apply product-interface discipline there.

This skill adapts the MIT-licensed `Dammyjay93/interface-design` Claude skill
for Codex and this agentic-tools setup. See [SOURCE.md](SOURCE.md).

## Authority Order

Before changing UI:

1. Read the repository root `DESIGN.md` or `DESIGN.MD`, if present.
2. Read the nearest subdirectory `DESIGN.md` or `DESIGN.MD`, if present.
3. Read `.interface-design/system.md`, if present.
4. Inspect the existing UI primitives and implemented screens.

`DESIGN.md` is authoritative. `.interface-design/system.md` is supporting
memory for recurring implementation patterns; it must not override
`DESIGN.md`.

## Intent Check

Before designing or editing a non-trivial UI surface, establish:

- Human: who is using this and what state are they in?
- Job: what must they accomplish on this screen?
- Feeling: what should the interface feel like in concrete terms?
- Defaults: which obvious/generic patterns would be tempting but wrong here?
- Signature: what structural, visual, or interaction pattern makes this product
  feel specific rather than templated?

If the answer is unclear and the choice is high-impact, ask. If the user has
already given enough direction, state the design choice briefly and proceed.

## Build Rules

- Use tokens from `DESIGN.md`; avoid random hex values and random spacing.
- Pick one depth strategy per surface and apply it consistently.
- Build text hierarchy with size, weight, color, and spacing; do not rely on
  size alone.
- Use structured tables, lists, forms, inspectors, tabs, drawers, and workflows
  before decorative cards.
- Give every interactive element default, hover, active, focus-visible,
  disabled, and loading-ready states where relevant.
- Use semantic HTML first. Links navigate; buttons act.
- Keep screen skeletons stable across related pages.
- Design empty, sparse, dense, loading, error, and overflow states.
- Use one icon set per app and remove icons that do not clarify meaning.

## Component Checkpoint

Before adding or changing a reusable component, record the decision in working
notes or the final summary:

```text
Intent: user, job, desired feel
Tokens: colors, spacing, radius, type scale from DESIGN.md
Depth: borders/shadows/surface shifts and why
States: hover, active, focus-visible, disabled, loading/error/empty as relevant
Responsive: narrow, normal, wide behavior
```

## Audit Workflow

When reviewing UI:

1. Load applicable `DESIGN.md` files and `.interface-design/system.md`.
2. Compare the implementation against the declared shell, tokens, density,
   components, states, and anti-patterns.
3. Identify generic/default choices and propose concrete replacements.
4. Use Playwright to inspect changed screens when a runnable UI exists:
   desktop and narrow screenshots, accessibility snapshots, core interaction
   checks, and canvas/graph nonblank checks where relevant.
5. Check Vercel-style interface gates: keyboard, focus, hit targets, URL state,
   native semantics, form behavior, loading, errors, and reduced motion.
6. Prioritize fixes that improve usability and consistency over decorative
   polish.

If Playwright is unavailable or blocked, say so and fall back to build checks,
source inspection, and a manual URL for user review.

## Design Memory

Offer to save `.interface-design/system.md` only when a reusable pattern has
been established or repeated. Save:

- Direction and feel.
- Token decisions not already captured in `DESIGN.md`.
- Depth strategy.
- Spacing base and scale.
- Component patterns with concrete measurements and usage rules.

Do not save one-off experiments, temporary mockups, or patterns that contradict
`DESIGN.md`.
