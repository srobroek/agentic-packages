---
name: codebase-index
description: Use when the codebase graph is missing or stale. Rebuild the codebase-memory index first.
---

# Codebase Index

Use this skill when codebase-memory-backed exploration depends on an up-to-date index that is missing or clearly stale.

## Workflow

1. Detect the current repo root.
2. Run the helper script to trigger a fast index refresh.
3. Report whether indexing was triggered, completed, or skipped.

## Steering

- Only re-index when the graph is genuinely stale or absent. Avoid redundant index runs.
- After indexing, verify the graph is queryable before proceeding with exploration.

## Scripts

- Index: `scripts/index.sh`
