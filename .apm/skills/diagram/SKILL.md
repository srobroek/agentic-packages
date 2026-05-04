---
name: diagram
description: Use when generating diagrams from text, code, or docs. Produces d2-based visuals.
---

# Diagram

Generate a D2 diagram: **$ARGUMENTS**

## Process

### Step 1: Understand the request

Determine: what to diagram (entities, architecture, flow, dependencies, deployment), source (conversation, file, codebase), and scope (everything, subset, or specific component).

### Step 2: Ask preferences

Ask about anything not already specified:
- **Theme**: run `d2 themes` to list options. Default: theme 0 (Neutral Default).
- **Layout**: `dagre` (default, good for most) or `elk` (better for >20 entities with crossing edges).
- **Colors**: recommended = NO custom colors (let theme handle it). If user wants custom, use light pastel fills with white entity fills and black text.
- **Output path**: suggest `docs/` or working directory.
- **Direction**: `right` for ER/architecture/data flows, `down` for flowcharts/sequences.

### Step 3: Generate D2

Apply conventions:
- `shape: class` for entities with properties; containers for logical grouping
- `style.stroke-dash: 3` for interfaces/abstract types; `style.stroke-dash: 5` for external/stubs
- Edge labels only when relationship is non-obvious
- Comments to separate sections; concise node labels
- Node shapes: rectangle (components), oval (start/end), diamond (decisions), cylinder (data stores), queue (streams), hexagon (external services), cloud (managed services)

If using theme colors (recommended): do NOT set fill/stroke/font-color anywhere.

### Step 4: Validate

Check D2 syntax (no unclosed braces, no duplicate IDs), verify all edges reference existing nodes, confirm labels are concise.

### Step 5: Render

```
d2 --theme <id> --pad 40 [--layout elk] <file>.d2 <file>.svg
```

If rendering fails, read the error, fix the D2, and retry.

### Step 6: Iterate

Tell the user where the SVG is. Suggest opening it. Ask for changes (layout, entities, labels, theme). On final version, ask if they want to commit the D2 + SVG files.
