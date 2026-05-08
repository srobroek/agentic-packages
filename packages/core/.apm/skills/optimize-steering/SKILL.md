---
name: optimize-steering
description: Audit and optimize agent-facing markdown files (steering docs, skills, agent definitions) for token efficiency, structural compliance, and cross-model compatibility. Applies research-backed formatting conventions (R1-R7). Runs `steering-audit` first for drift/hook/lint detection. Use when asked to audit agent docs, optimize steering files, refactor SKILL.md, normalize agent instructions, reduce token waste, or fix agent compliance issues. To create a new skill from scratch, use `write-a-skill` instead.
---

# Optimize Steering

Audit and rewrite agent-facing markdown files for token efficiency and structural compliance.

## Workflow

1. **Run `steering-audit`** — lint, hooks, staleness, drift detection
2. **Measure** — discover agent-facing files, compute token estimates, map load patterns, detect redundancy (see `references/measurement.md`)
3. **Scope** — ask which files to optimize; note other candidates
4. **Apply R1-R7** — rewrite files applying the rules below (see `references/rules.md` for rationale)
5. **Verify** — check no ALL CAPS, no model names, consistent headings, no prose paragraphs, index files are routing-only, cross-references use canonical names
6. **Report** — changes per file: transformations applied, line count before/after, splits created

## Rules Summary

| Rule | What | Why |
|------|------|-----|
| R1 — Frontmatter | `description` in YAML frontmatter on every file | Primary mechanism for agent routing decisions |
| R2 — Language | Imperative tone, no ALL CAPS, no model names, no vendor paths | ALL CAPS causes overtriggering; cross-model files avoid vendor bias |
| R3 — Structure | Tables for mappings, bullets for rules, no prose | Tables reduce comprehension time vs prose |
| R4 — Template | Consistent section structure per file type | Format beats content — agents respond to structure |
| R5 — Cross-refs | Relative paths for files, backticks for skill/agent names | Unambiguous routing between files |
| R6 — File size | Under 50 lines; split oversized files | Progressive disclosure — load only what's needed |
| R7 — Progressive disclosure | Index files as routing tables, detail in referenced files | 60-80% token reduction, 80%+ instruction compliance |

## References

- `references/rules.md` — Rule rationale and application guidance
- `references/measurement.md` — Token estimation, load types, report format
