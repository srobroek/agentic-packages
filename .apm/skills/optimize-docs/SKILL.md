---
name: optimize-docs
description: Use to audit docs for agent-context cost, redundancy, and routing opportunities.
---

# Documentation Token Optimizer

Analyze a project's documentation for LLM token efficiency. Read-only -- never modify files. Produce a structured report with concrete recommendations.

## Process

### 1. Discover

Find all documentation files: steering files (AGENTS.md, CLAUDE.md), rules, skills, procedures, contracts, config JSON files. Use parallel search across the project.

### 2. Measure

For each file compute:
- **Lines**: raw line count
- **Est. tokens**: `word_count * 1.3`
- **Load type**: eager (read every session), lazy (read on demand), or agent (read when skill invoked)

### 3. Detect redundancy

Search for content duplicated across 2+ files: identical paragraphs, same rules in different words, code templates repeated across skill files, protocol descriptions duplicated per-agent. Use key phrase searches from eager files to check for echoes elsewhere.

### 4. Map load patterns

| Load Type | When Read | Token Impact |
|-----------|-----------|-------------|
| Eager | Every session start | Highest -- minimize aggressively |
| Agent | When skill invoked | Medium -- one skill per phase |
| Lazy | When rule/procedure referenced | Lowest -- load only when needed |

### 5. Identify routing opportunities

Content in eager/agent files that could be a one-line reference to a lazy file: repeated design rules, code templates that could be procedure files, protocol descriptions that could be centralized.

### 6. Report

Output a markdown report to stdout (do NOT write files) with: summary (total files, lines, tokens, eager tokens, redundancy rate), file inventory table, redundancy map, prioritized recommendations (sorted by token savings), and estimated savings per scenario.

## Execution

Launch 3 parallel subagents:
1. Discover and measure all doc files (steering, rules, procedures, contracts)
2. Discover and measure all skill files
3. Scan for redundancy patterns

Synthesize results into the report. Present directly -- only write a file if the user explicitly requests it.
