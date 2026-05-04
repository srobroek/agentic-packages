# Agent Optimization Rules — Complete Reference

Research-backed rules for optimizing markdown files consumed by AI agents. Sources: Anthropic official docs (prompt engineering guide, skills best practices, migration guide), academic papers (Tang et al. 2024, COLM 2024, arXiv 2025), AGENTS.md open standard (Linux Foundation, 60k+ projects).

---

## R1: Frontmatter

Every file must have YAML frontmatter with a `description` field.

**Why**: The description is the primary mechanism agents use to decide whether to load a file. From Anthropic's official docs: "The description field is the primary mechanism that determines whether an agent invokes a skill."

**Format**: Third person, present tense. Says WHAT the file contains AND WHEN to load it.

**Before**:
```markdown
---
---

# Commit Workflow
```

**After**:
```markdown
---
description: Commit strategy, push rules, and branch conventions. Always loaded.
---

# Commit Workflow
```

**For skill descriptions**: Be specific about triggers. From Anthropic: "Make the description a little bit pushy... mention when to use this skill whenever the user mentions X, Y, or Z."

---

## R2: Language

### No ALL CAPS directives

Reserve `MUST`/`NEVER`/`ALWAYS`/`CRITICAL` only for genuine safety issues (secrets exposure, data loss, destructive operations).

**Why**: Anthropic's migration guide for current models explicitly states: "Dial back any aggressive language. Where you might have said 'CRITICAL: You MUST use this tool when...', you can use more normal prompting." From the skill-creator: "If you find yourself writing ALWAYS or NEVER in all caps, that's a yellow flag."

**Before**: `- MUST run tests before committing.`
**After**: `- Run tests before committing — catches regressions before they reach the branch.`

### No model names

Remove all model family references: Claude, DeepSeek, GPT, Codex, Opus, Sonnet, Haiku.

**Why**: Cross-model steering must not bias toward one vendor's behavior. PromptBridge (2025) showed 27-39% degradation when prompts transfer between models without adaptation.

### No tool-specific paths

Replace vendor-specific paths with shared equivalents:
- `~/.claude/` → `~/.config/agentic-tools/` (for shared config)
- `CLAUDE.md` → `AGENTS.md` (CLAUDE.md is a symlink to AGENTS.md)
- `claude mcp add` → remove or use tool-agnostic equivalent

### Positive framing

Frame instructions as actions to take, not things to avoid.

**Before**: `- Do not skip tests before committing.`
**After**: `- Run tests before committing.`

**Why**: Anthropic: "Tell the model what to do instead of what not to do." Attention mechanisms highlight forbidden concepts, making negative instructions counterproductive.

### Explain why

For non-obvious rules, add a brief reason.

**Before**: `- Run pre-commit run --all-files before committing.`
**After**: `- Run pre-commit run --all-files before committing — enforces formatting and lint rules configured for the project.`

**Why**: Anthropic: "Try to explain to the model why things are important in lieu of heavy-handed musty MUSTs. Use theory of mind."

---

## R3: Structure

### Tables for mappings

Agent choices, tool selections, phase routing — use tables.

**Before** (prose):
```
For TypeScript use pnpm as the package manager and Biome for linting.
For Python use uv and Ruff.
```

**After** (table):
```
| Language | Package Manager | Linter |
|----------|----------------|--------|
| TypeScript | pnpm | Biome |
| Python | uv | Ruff |
```

**Why**: Tables reduce comprehension time by 42.9% vs prose (arXiv:2401.06837). Structured formats are strictly better for agent skimming.

### Bullets for rules

Rules and constraints as bullet lists. No paragraphs.

**Before**:
```
When working on this project you should always run tests before committing. You should also run the linter. It's also important to check that the types are correct by running the type checker.
```

**After**:
```
- Run tests before committing.
- Run the linter on changed files.
- Run the type checker before merging.
```

### No prose paragraphs

Convert all prose to scannable structures. If a concept needs explanation, use a bullet with a dash-separated reason.

### Heading depth

Maximum three levels: `# Title`, `## Section`, `### Subsection`. No deeper.

---

## R4: Consistent Template

Every file of the same type follows the same section structure.

### Steering files
```
---
description: [What and when]
---

# [Topic]

## [Section 1]
[Table or bullets]

## [Section 2]
[Table or bullets]
```

### Speckit per-step files
```
---
description: Step N — [what]. Load during [when].
---

# Step N: [Name]

## What It Does
- [bullet]

## Invoke
`/speckit.[skill]`

## Hand Off
- agent-name — what it does (mode)

## Consult
- steering/path/file.md — what to find there

## Rules
- [imperative rule with reason]
```

### Skill files (SKILL.md)
```
---
name: skill-name
description: [What and when. Third person.]
---

# [Skill Title]

## [Section]
[Content]
```

---

## R5: Cross-References

### Steering files
Reference by relative path from the steering root:
- `steering/speckit/testing.md` — not `../speckit/testing.md` or absolute paths

### Skills and agents
Reference in backticks:
- `` `quick-commit` `` for skills
- `` `code-reviewer` `` for agents
- `` `tdd-workflows:tdd-cycle` `` for namespaced skills

### Consistent naming
Use the canonical name throughout. Do not drift to synonyms.

---

## R6: File Size

### Target: under 50 lines

Files over 50 lines should be split or compressed.

### When to split

| If a file has... | Split into... |
|-----------------|---------------|
| Two distinct topics | One file per topic |
| A routing section + detailed content | Router file + detail file(s) |
| Multiple independent tables | Separate files per table |

### When to compress

| Technique | Example |
|-----------|---------|
| Merge similar rules | "Run tests, lint, and type-check before committing" instead of 3 separate bullets |
| Remove redundant explanations | Keep the "why" once, not per bullet |
| Tighten table rows | Remove filler words from table cells |

---

## R7: Progressive Disclosure

### Index files: routing only

An `index.md` file should be a routing table — what file covers what topic, when to load it. No actual rules or procedures.

**Before** (index with embedded rules):
```
# Speckit
## Phases
...
## Rules
- Always invoke via Skill tool...
- Never proceed with open questions...
## Subagents
...
## Extension Setup
...
```

**After** (index as pure routing):
```
# Speckit Steering
## Phase Routing
| Phase | Steps | Steering File |
|-------|-------|---------------|
| Specification | 1-3 | 01-specify.md |
...
## Cross-Cutting
| Concern | File |
|---------|------|
| Rules | trigger.md |
| Subagents | delegation.md |
```

### Three-tier loading

| Tier | Content | When loaded |
|------|---------|-------------|
| L0 — Index | Routing table | Always (session start) |
| L1 — Phase docs | Step-specific instructions | When step is active |
| L2 — References | Detailed procedures, examples | When consulted by L1 |

**Why**: Progressive disclosure delivers 60-80% token reduction and 80%+ instruction compliance improvement in empirical studies.

---

## Verification Checklist

After optimization, verify all files:

- [ ] All files have `description` frontmatter
- [ ] No ALL CAPS directives (`MUST`, `NEVER`, `ALWAYS`, `CRITICAL`) except for safety-critical rules
- [ ] No model family names (`Claude`, `DeepSeek`, `GPT`, `Codex`, `Opus`, `Sonnet`, `Haiku`)
- [ ] No vendor-specific paths where cross-model compatibility is needed
- [ ] Consistent heading structure per file type
- [ ] No prose paragraphs — bullets, tables, or imperative statements only
- [ ] Index files contain routing only, no embedded rules
- [ ] All cross-references use canonical names (relative paths, backtick names)
- [ ] Files under 50 lines (or justified splits)
- [ ] Content preserved — only structure and format changed
