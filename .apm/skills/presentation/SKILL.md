---
name: presentation
description: Use when creating slide decks. Produces Marp slides and exports them for review.
---

# Presentation

Create a Marp presentation: **$ARGUMENTS**

## Process

### Step 1: Understand the request

Determine: topic, audience (technical/business/mixed), slide count (default 8-12), source (conversation, file, or codebase).

### Step 2: Ask preferences

Ask about anything not already specified:
- **Mode**: Light (white content slides) or Dark (navy content slides). Title/section/closing slides always use gradient background.
- **Output directory**: default `./presentations/`
- **Export formats**: HTML only, PDF only, or both (default: both)
- **Theme**: use the project's custom theme from the skill's assets directory, or a user-provided theme

### Step 3: Set up output directory

Create the output directory and copy theme assets (CSS, logos, backgrounds) into it.

### Step 4: Generate slides

Write `slides.md` using Marp markdown syntax with the theme. For dark mode, add `class: dark` to frontmatter.

**Slide classes**: `title` (opening), `section` (divider), default (content), `closing` (final). Apply via `<!-- _class: name -->` directives.

**Content density**: title = 1 heading + subtitle + speaker; content = 1 heading + 5-8 bullets OR 1 code block OR 1 table. Do not overload -- split if content overflows.

### Step 5: Export

```
marp slides.md --theme <theme>.css -o slides.html --allow-local-files
marp slides.md --theme <theme>.css -o slides.pdf --allow-local-files
```

If PDF export fails (e.g., browser locked), export HTML only and suggest manual PDF via browser print.

### Step 6: Iterate

Tell the user where files are. Suggest opening the HTML to preview. Ask for changes (content, layout, add/remove slides, switch mode). Iterate until satisfied.
