# UI Component Context

Pages must be composable. Build a page as a thin assembly of named primitives
and components — never inline large JSX/template trees, repeated layout
fragments, or whole sub-features directly in a page module. When a region of
a page owns its own state, layout role, or visual concern, lift it into a
local component first; readability should rest on component names, not on
scrolling through hundreds of lines of markup. This applies to all
TypeScript/JavaScript frontends regardless of framework (React, Vue, Svelte,
Astro, Solid, Qwik).

Keep components local to an app until reused by at least two app surfaces.

Move shared primitives and design-system code to `libs/ui` only after real
reuse. Shared UI code should be more stable than app-local components: use typed
props, documented variants, reusable accessibility behavior, and browser
verification.

Do not turn one-off product layout into a design-system primitive before the
second real use case exists.
