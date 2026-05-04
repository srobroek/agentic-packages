---
name: optimize-steering
description: Optimize markdown steering files, skills, and agent definitions for cross-model agent consumption. Applies research-backed formatting conventions. Use when asked to optimize, refactor, or normalize agent instructions, steering docs, SKILL.md files, or agent definitions for better agent compliance.
---

# Optimize Steering

Refactors markdown files consumed by AI agents — steering docs, skills (`SKILL.md`), and agent definitions — applying research-backed conventions that improve instruction following across models.

## When to Use

- User asks to optimize, normalize, or refactor agent steering files
- User wants skills or agents rewritten for better compliance
- User mentions "apply agent optimization rules" or similar
- After adding new steering files that need formatting

## Workflow

### 1. Identify scope

Ask the user which files to optimize:
- A single file
- A directory of files
- All steering files in a project

### 2. Read each file

Read every file before writing. Understand the factual content — only change structure and format, not meaning.

### 3. Apply the seven rules

Read `references/rules.md` for the complete ruleset with before/after examples. The rules in summary:

| Rule | What | Why |
|------|------|-----|
| R1 — Frontmatter | Add `description` to YAML frontmatter on every file | Primary mechanism for agent routing and trigger decisions |
| R2 — Language | Normal imperative tone, no ALL CAPS, no model names, no tool-specific paths | ALL CAPS causes overtriggering on current models; cross-model files must avoid vendor-specific references |
| R3 — Structure | Tables for mappings, bullets for rules, no prose paragraphs | Tables reduce comprehension time by 42.9% vs prose |
| R4 — Template | Consistent section template per file type | Format beats content — agents respond to structure more than specific wording |
| R5 — Cross-references | Relative paths for files, backticks for skill/agent names | Unambiguous routing between files |
| R6 — File size | Under 50 lines; split oversized files | Progressive disclosure — load only what's needed |
| R7 — Progressive disclosure | Index files as routing tables only, detail in referenced files | 60-80% token reduction, 80%+ instruction compliance improvement |

### 4. Verify

After writing, verify:
- All files have `description` frontmatter
- No ALL CAPS directives (grep for `MUST|NEVER|ALWAYS|CRITICAL`)
- No model names (grep for model families relevant to the context)
- No vendor-specific paths or tool references in cross-model files
- Consistent heading structure
- No prose paragraphs — everything is bullets, tables, or imperative statements

### 5. Report

Summarize changes per file: what structural transformations were applied, line count before/after, any splits created.

## File-Type Specific Guidance

### Steering files (`steering/**/*.md`)
- Frontmatter with `description` explaining when to load
- `# Title` matching the file topic
- Tables for routing/mapping content
- Bullet lists for rules, each starting with an imperative verb

### Skills (`SKILL.md`)
- Keep existing frontmatter fields; ensure `description` says what the skill does AND when to trigger
- Description in third person: "Processes Excel files and generates reports" (not "I can help you...")
- Body: imperative form throughout. Explain *why* for non-obvious rules
- Keep bundled resources (`references/`, `scripts/`, `assets/`) unchanged

### Agent definitions (`agents/*.md`)
- Keep existing frontmatter fields
- Remove model name from `model:` field if it's vendor-specific and cross-model use is desired
- Body: role description in third person, capabilities as bullet lists

## References

- `references/rules.md` — Complete research-backed ruleset with before/after examples, research citations, and language-specific guidance
