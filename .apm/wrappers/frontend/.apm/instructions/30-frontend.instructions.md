---
description: Frontend and app-surface steering.
applyTo: "{apps/**,**/frontend/**,**/web/**,**/*.{tsx,jsx,vue,svelte,css,scss}}"
---

# Frontend

Route framework choice by use case: React + Vite for SPA/product UIs, Vue + Vite
for app-style UIs, Next.js for SSR/full-stack React, and Astro for
marketing/static/docs surfaces.

Use framework-specific UI. React may use shadcn/ui and Base UI. Vue may use
PrimeVue or Nuxt UI by project need. Use store-first app/UI state and TanStack
Query for server state.
