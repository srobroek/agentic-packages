# Hooks Migration Analysis

Scope: the root `.apm/hooks/agentic-tools-{claude,codex}-hooks.json` (repo-internal
dev config) reference ~50 `./scripts/*.sh`. This audit classifies each by whether
it can ship inside a marketplace package and, if so, which one.

## Shipping mechanism (reference)

The working pattern is `packages/speckit-dag-hooks`:
- hook JSON in `<pkg>/.apm/hooks/<name>-{claude,codex}-hooks.json`
- scripts in `<pkg>/scripts/`
- referenced via `${PLUGIN_ROOT}/scripts/<x>.sh` (APM copies + path-rewrites
  `${PLUGIN_ROOT}` / `./` refs in a hook COMMAND; sibling files are NOT auto-copied,
  so every referenced script must live under the package and be addressed via
  `${PLUGIN_ROOT}`)
- package `type: instructions`

## Migratable into an existing owning package

| Hook script | Owning package | Event | Notes |
|---|---|---|---|
| `speckit-context7-reminder` | speckit | PreToolUse:Skill | |
| `speckit-deferred-issues` | speckit | UserPromptSubmit | |
| `speckit-issue-close-guard` | speckit | PreToolUse:Bash | |
| `speckit-issue-label-guard` | speckit | PreToolUse:Bash | |
| `speckit-pr-issue-refs` | speckit | PreToolUse:Bash | |
| `speckit-stop-gate` | speckit | Stop | |
| `speckit-task-commit-check` | speckit | PostToolUse:Bash | |
| `speckit-task-issue-sync` | speckit | (inactive) | |
| `codebase-index` | code-intelligence | SessionStart | needs codebase-memory MCP |
| `code-discovery-steer` | code-intelligence | PreToolUse | advisory toward codebase-memory/repomix |
| `reindex-after-commit` | code-intelligence | PostToolUse:Bash | |
| `repomix-refresh-snapshot` | code-intelligence | PostToolUse:Bash | needs repomix |
| `subagent-context-inject` | code-intelligence | SubagentStart | injects MCP guidance |
| `validate-d2` | diagrams | PostToolUse (`*.d2`) | |
| `pkg-version-warn` | mcp-package-version | PreToolUse:Bash | |
| `package-file-warn` | mcp-package-version | PreToolUse:Edit/Write | |

## Migratable only as a NEW dedicated opt-in hook package

These are cross-cutting policy hooks with no single existing functional owner.

| Candidate package | Hook scripts |
|---|---|
| `hooks-git-workflow` | git-guard, no-ff-guard, squash-merge-guard, attribution-guard, branch-check, uncommitted-warn, pre-commit-test-gate, quality-before-commit, gh-rate-guard, post-merge-cleanup |
| `hooks-worktree` | worktree-create, worktree-cleanup, worktree-enforce, worktree-orphan-cleanup, session-end-prune |
| `hooks-agent-discipline` | concurrent-limit, coder-delegation-reminder, agent-metrics, enforce-tool-prefs, approve-compound-bash, bash-guard, test-state-tracker, quality-edit-advisory |

## NOT migratable (personal-env coupled -- stay repo-internal)

Coupled to this maintainer's chezmoi/dotfile setup, notification stack, or this
repo's own dev loop. Shipping them would leak environment assumptions.

- `chezmoi-sync`, `allow-chezmoi-apply`, `chezmoi-guard` -- chezmoi dotfile sync
- `agentic-source-guard` -- guards edits to this repo's own `.apm/` source layout
- `safe-commands` -- references absolute `/Users/sjors` paths
- `notify` -- personal desktop notification
- `apm-outdated-check` -- this repo's dependency-freshness check
- `failure-logger`, `debug-stuck-detector`, `stuck-reset` -- this repo's dev loop
- `dependent-api-check`, `worktree-enforce` (overlaps hooks-worktree; keep repo-internal until generalized)

## Recommendation

1. Move the 16 domain-coupled hooks into their owning packages (speckit,
   code-intelligence, diagrams, mcp-package-version) -- unambiguous, no new
   package surface.
2. Create the 3 `hooks-*` packages only if cross-cutting policy enforcement is
   wanted as opt-in marketplace entries. Otherwise leave them repo-internal.
3. Leave personal-env hooks in `.apm/hooks/` untouched; they are not shipped.
