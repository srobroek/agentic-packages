---
name: explore
description: Use for read-only codebase orientation, file discovery, and path tracing.
---

# Explore

Use this skill for read-only investigation of a codebase.

## Workflow

1. Parse the question to identify what the user needs to understand.
2. Search for relevant files, symbols, or directories.
3. Read only the files needed to answer the question.
4. Trace code paths when execution flow matters.
5. Return a concise explanation with absolute file path references.

## Rules

- The agent MUST NOT edit or write any files.
- Keep the read set focused -- avoid exhaustive file dumps.
- Prefer direct answers over listing every match.
- Use codebase-memory MCP for structural queries when available.
- Include file paths in every finding so the user can navigate directly.
