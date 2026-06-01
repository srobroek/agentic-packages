# Frontend Context

Use this context for app surfaces, UI frameworks, browser-visible behavior,
state, server data, and frontend verification.

Read only the relevant detail:

- [Toolchain frontend defaults](toolchain-defaults.frontend.context.md)
- [UI components](frontend.ui-components.context.md)

Choose frameworks by surface:

- React + Vite for SPA and product UIs.
- Vue + Vite for app-style UIs when Vue is a better fit.
- Next.js for SSR or full-stack React.
- Astro for marketing, static content, and documentation.

Use framework-native UI libraries. React may use shadcn/ui and Base UI. Vue may
use PrimeVue or Nuxt UI by project need.

Prefer store-first app/UI state and TanStack Query for server state unless the
project already has a stronger convention.

Verify browser-visible changes with the project's browser test or Playwright
workflow when layout, interaction, rendering, or user-visible state changes.
