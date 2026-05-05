---
description: Shared UI and component steering.
applyTo: "{apps/**/components/**,apps/**/ui/**,libs/ui/**}"
---

# UI Components

Keep components local to an app until reused by at least two app surfaces. Move
shared primitives and design-system code to `libs/ui` only after real reuse.

`libs/ui` should be more stable than app-local components: prefer typed props,
documented variants, reusable accessibility behavior, and browser verification.
