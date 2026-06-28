# Bloodhound Brief Template

Use this to construct the prompt for each `bloodhound` agent spawned in step 4 —
one per detected language. Fill every field. Pass **facts only**: the language,
the scope, the installed tools, and the language-doc path. Do not pass your own
hypotheses about what is wrong — bloodhound finds independently.

Spawn one bloodhound per language in parallel (single message, multiple Agent
calls). The agent is read-only.

---

```
You are scanning the **<LANGUAGE>** code in this repository for code smells.

## Scope
- Files / directories: <the resolved target file list for this language — explicit
  paths from step 0.5, NOT "the whole repo" when the run is scoped>
- Working directory: <repo root, OR the worktree path for a commit/PR/branch target>
- Exclude: <generated, vendored, test fixtures — if any>
- Scoped-run note: <if this is a diff/PR/module run, tell the agent to apply tool
  analysis-class rules — skip global-class tools (dead code/cycles) and say so>
- Base ref (if any): <for diff/PR/range — pass so baseline tools can compare>

## Installed tools (run these; skip + note any not listed here)
<tool: exact invocation, one per line, copied from references/tooling.md and the
language doc. e.g.:
  golangci-lint: golangci-lint run --out-format json ./...
  lizard:        lizard -C 10 -L 50 ./... >
Tools NOT in this list are NOT installed — record them as coverage gaps, do not
attempt to run them.

## Your reference
Read `references/languages/<LANGUAGE>.md` FIRST. It is your smell checklist,
idiom guide, and tool-invocation source. Do not improvise the catalog.

## Project conventions
- Config files governing this language: <e.g. .golangci.yml, pyproject.toml>
- Respect them; do not override project config.

## Return
Structured findings in the Bloodhound Findings format from your agent definition:
a coverage block (tools run / skipped / scope) and a findings table — every row
with file:line, smell, source, evidence, idiomatic alternative, and the
refactoring.guru smell name when one applies. Do not prioritize or fix; return
raw findings.
```

---

## Filling guidance

- **One language per agent.** If a repo has Go + TS + Dockerfile, that is three
  bloodhounds, each with its own scope and tool list.
- **Installed tools only — and tell bloodhound to verify, not trust the list.**
  Pull the live installed set from `install-tools.sh --probe` (step 2); list only
  what is actually present, with the exact invocation. But a hardcoded list goes
  stale: instruct bloodhound to confirm each tool with `command -v` (or `runnable`)
  at scan time and to **prefer ground truth over the Brief** — if a tool the Brief
  marked absent is actually present (e.g. a type-checker), run it rather than
  silently dropping that dimension; if one marked present is a `SHIM`/unrunnable,
  treat it as missing. This keeps a stale Brief from dropping a whole smell class.
- **Scope tightly.** Pass real paths, not "the whole repo", when the language
  lives in known directories — it keeps the scan focused and the findings
  locatable.
