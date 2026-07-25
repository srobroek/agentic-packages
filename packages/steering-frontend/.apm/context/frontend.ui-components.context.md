# UI Component Context

Keep components local to an app; move shared primitives and design-system code
to `libs/ui` only after two app surfaces actually reuse them. Shared UI code
should be more stable than app-local components: use typed props, documented
variants, reusable accessibility behavior, and browser verification.
