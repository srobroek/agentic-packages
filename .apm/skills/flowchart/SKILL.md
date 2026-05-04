---
name: flowchart
description: Use when generating color-coded flowcharts or dependency diagrams with d2.
---

# Flowchart

Generate a D2 flowchart diagram: **$ARGUMENTS**

## Color Palette

Each category gets a fill (light), stroke (medium), and font-color (dark) from the same hue:

| Category | Fill | Stroke | Font |
|----------|------|--------|------|
| Research/analysis | `#f0e6ff` | `#7c3aed` | `#3b0764` |
| Infrastructure/platform | `#e0f2fe` | `#0284c7` | `#0c4a6e` |
| Code/implementation | `#dcfce7` | `#16a34a` | `#14532d` |
| Data/models/schemas | `#fef9c3` | `#ca8a04` | `#713f12` |
| Integrations/APIs | `#ffe4e6` | `#e11d48` | `#881337` |
| UI/frontend | `#ffedd5` | `#ea580c` | `#7c2d12` |
| Services/middleware | `#e0e7ff` | `#4f46e5` | `#312e81` |
| Operations/deployment | `#f1f5f9` | `#475569` | `#1e293b` |
| Testing/QA | `#ccfbf1` | `#0d9488` | `#134e4a` |
| Users/stakeholders | `#fce7f3` | `#db2777` | `#831843` |

## D2 Conventions

- `direction: down` for top-to-bottom (default); `direction: right` for process flows
- Use `\n` in labels for multi-line text (ID + short description)
- Flat nodes (no containers) -- categories conveyed by color only
- Edge labels only when relationship is non-obvious
- Keep node labels short (2-4 words max)
- Limit to 3-5 categories per diagram for readability
- Node shapes: rectangle (default), oval (start/end), diamond (decisions), cylinder (data stores), queue (streams), hexagon (external services)

## Rendering

1. Write `.d2` file to appropriate location (`docs/architecture/` for project diagrams)
2. Render: `d2 --theme 200 --pad 40 --layout elk <input>.d2 <output>.svg`
3. Suggest opening the SVG to view

## Category Assignment

Map concepts to colors by semantic meaning (what things ARE, not where they live). When in doubt, use blue (infrastructure). Respect user-specified categories over defaults.
