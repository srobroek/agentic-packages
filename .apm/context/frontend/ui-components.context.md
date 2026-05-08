# UI Component Context

Keep components local to an app until reused by at least two app surfaces.

Move shared primitives and design-system code to `libs/ui` only after real
reuse. Shared UI code should be more stable than app-local components: use typed
props, documented variants, reusable accessibility behavior, and browser
verification.

Do not turn one-off product layout into a design-system primitive before the
second real use case exists.
