# Hooks and MCP packages

## Hook packages

Opt-in lifecycle hooks. Most hooks ship inside their owning package (code-intelligence, agent-coder, unstuck, the MCP packages, speckit); the two below are standalone cross-cutting policy packages.

A package ships hooks as `.apm/hooks/<pkg>-{claude,codex}-hooks.json` plus a `scripts/` directory, with commands referencing `${PLUGIN_ROOT}/scripts/<name>.sh`. On install, APM deploys the scripts under `.claude/hooks/<pkg>/` and `.codex/hooks/<pkg>/`, rewrites `${PLUGIN_ROOT}`, and merges the config into `settings.json` / `hooks.json`. Codex supports `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `Stop`, `SessionStart`, `SubagentStart`, `SubagentStop`, `PreCompact`, and `PostCompact`; Claude-only events (e.g. `WorktreeCreate`, `UserPromptExpansion`) ship in the claude variant only. Both runtimes honor hard blocking: `PreToolUse` via `hookSpecificOutput.permissionDecision: "deny"` (the tool never executes) and prompt events via `{"decision": "block", "reason": ...}`; on Codex, `Edit`/`Write` matchers alias onto `apply_patch`. Two gotchas: neither runtime reads an `"args"` field on hook entries (pass arguments inside the `command` string — APM also only rewrites `${PLUGIN_ROOT}` there), and plain stdout with exit 0 on PreToolUse/PostToolUse is never shown to the model (use `additionalContext`).

<!-- BEGIN:hooks -->
| Hook Package | Description |
| --- | --- |
| `hooks-attribution-guard` | Blocks git commits that carry AI authorship attribution (Co-Authored-By Claude/Anthropic, "Generated with/by AI", "AI-assisted/AI-generated", Claude Code trailers), enforcing that the human is the sole author of record. Scoped to attribution trailers/phrases so prose mentioning AI is not blocked. Cross-tool (Claude + Codex). |
| `hooks-bash-safety` | Bash safety guards tuned for autonomous agents: hard-block only unrecoverable ops (rm -rf / or $HOME, mkfs, dd to a device, sandbox-bypass), ask on curl\|sh pipes, warn on sudo + destructive verbs. rm -rf allows project-local/temp cleanup silently and asks only on absolute/parent/variable targets. Matching is anchored to command position to avoid quoted-string false positives. Cross-tool (Claude + Codex). |
| `hooks-branch-check` | Branch awareness hook: on prompt submit, warn when work starts on a protected branch (main/master/develop) and surface relevant feature branches/worktrees. Advisory context only, never blocks. Cross-tool (Claude + Codex). |
| `hooks-chezmoi-guard` | PreToolUse guard that denies direct edits and shell writes to files chezmoi ACTUALLY manages (exact membership in `chezmoi managed`, 60s cache), steering changes to the chezmoi source. Read-only references and unmanaged paths pass. Cross-tool (Claude + Codex). |
| `hooks-close-keywords` | Fixes the GitHub "comma-list close" quirk, where a closing keyword binds to only the FIRST issue in a list (Closes #1, #2, #3 closes just #1). A shared normalizer distributes the keyword across every issue in a contiguous list (-> Closes #1, closes #2, closes #3) for close/closes/closed, fix/fixes/fixed, resolve/resolves/resolved. Two delivery layers: a pre-commit commit-msg hook that rewrites the message in place (tool-agnostic), and a PreToolUse guard on `gh pr create`/`gh pr edit` that blocks with the corrected --body to re-issue. Cross-tool (Claude + Codex). |
| `hooks-git-safety` | Git safety guards: hard-block `git reset --hard` only when the tracked tree is dirty (work would be lost) and `git push --force`, and soft-guard other destructive git operations — confirm (ask) on checkout --/restore/clean -f/branch/stash/tag deletion/worktree remove. Cross-tool (Claude + Codex). |
| `hooks-git-workflow` | Opt-in git workflow hooks: BLOCK a git push when unit tests are stale or failing (the hook does not run tests — it reads the edit/test state the tracker records and tells the agent to run them; warns-and-allows when no test command is detectable, bypass with SKIP_TEST_GATE=1), track edit-vs-test state from real test runners only, and warn about uncommitted work at session end. Cross-tool (Claude + Codex). |
| `hooks-no-ff` | Opinionated git policy hook: require --no-ff on git merge so feature-branch history is preserved. Blocks fast-forward merges. Cross-tool (Claude + Codex). |
| `hooks-package-file-guard` | Non-blocking PreToolUse hook (Edit/Write/MultiEdit) that warns against editing a dependency manifest directly (go.mod, package.json, Cargo.toml, pyproject.toml, Gemfile, composer.json), steering toward the package manager's add command. Advisory only, never blocks. Cross-tool (Claude + Codex). |
| `hooks-package-investigate` | Non-blocking PreToolUse Bash hook that nudges the agent to investigate a dependency's trustworthiness, maintenance, quality, popularity, and alternatives BEFORE adding/installing it (lighter review for update/upgrade/remove). Cross-tool (Claude + Codex). |
| `hooks-pkg-version-warn` | Advisory PreToolUse:Bash hook that nudges you to install the latest compatible version when running a package install command (pnpm add, npm install, uv add, pip install, go get, gem install, composer require, etc.). Advisory only via additionalContext, never blocks. Self-gates on the leading command token so a substring such as `echo "pip install ..."` does not trip it. Cross-tool (Claude + Codex). |
| `hooks-portability-ci` | CI gate that runs shipped hook scripts through the real portability failure modes the audits found: bash 3.2 parse errors (;;& fallthrough, mapfile), GNU-only sed/grep constructs (\b word boundaries, lazy quantifiers), and string-form tool_input payloads that crash jq. Reports a summary and exits non-zero on any failure. Invoked on demand or wired into CI. |
| `hooks-precommit-gate` | Ensures the pre-commit framework actually runs. PreToolUse on git commit/push: when the repo HAS a .pre-commit-config.yaml but the matching git hook is not installed (.git/hooks/pre-commit / pre-push missing), it blocks with "run pre-commit install"; it also blocks --no-verify, which would skip the framework. Silent in repos with no pre-commit config, so it adds zero friction elsewhere. Pairs with secrets-scan (whose enforcement lives in the pre-push hook). Cross-tool (Claude + Codex). |
| `hooks-quality` | Opt-in code-quality hooks: advisory linting/formatting feedback after edits and a quality check before commits. Cross-tool (Claude + Codex). |
| `hooks-squash-merge` | Opinionated git policy hook: require an explicit merge strategy on gh pr merge (--squash for feature PRs, --merge for release PRs). Blocks strategy-less PR merges. Cross-tool (Claude + Codex). |
| `hooks-subagent-worktree` | Enforce an explicit worktree-isolation decision on every subagent spawn. A PreToolUse:Agent guard denies an undeclared spawn and instructs the parent to re-issue with `isolation:"worktree"` (the child writes to THIS repo) or with an `[iso:skip]` sentinel appended to the description (read-only, a different repo, or must edit the parent tree directly). The sentinel is stripped from the description before the spawn proceeds. Claude-only (the Agent spawn tool is Claude-specific); the Codex variant is a no-op. |
| `hooks-tool-prefs` | Opinionated advisory hook: suggest preferred tools over deprecated ones (rg over grep, fd over find, pnpm over npm, uv over pip, mise over nvm/pyenv, just over make). Advisory only, never blocks. Cross-tool (Claude + Codex). |
| `hooks-worktree` | Worktree lifecycle hooks: create worktrees outside the repo tree (in /tmp) to prevent nesting, and clean up the worktree directory and branch on removal. Claude WorktreeCreate/WorktreeRemove events. |
<!-- END:hooks -->

## MCP server packages

Pre-wired Model Context Protocol servers. Installing one adds the server's tools to your runtime's MCP config -- no manual server setup.

<!-- BEGIN:mcp -->
| MCP Package | Description |
| --- | --- |
| `mcp-codebase-memory` | MCP server package for the Codebase Memory MCP, providing graph-aware project orientation (symbol search, call paths, code snippets). |
| `mcp-context7` | MCP server package for Context7, providing current library and framework documentation lookups. |
| `mcp-package-version` | MCP server for package version discovery |
| `mcp-playwright` | MCP server package for Playwright, providing browser automation and in-browser UI verification. |
| `mcp-repomix` | MCP server package for Repomix, providing bulk repository snapshots for analysis and review. |
| `mcp-serena` | MCP server package for Serena semantic code tools. The launcher selects the Codex or Claude Code context from the parent harness and can be overridden with SERENA_MCP_CONTEXT. |
| `mcp-speckit-memory` | MCP server package for the Spec Kit Memory Hub (memory-md) extension: durable, repository-native project memory (decisions, bugs, lessons) with a SQLite cache exposed as MCP tools. The launcher resolves the project-local memory-md extension and builds its server in-place on first use, since the upstream binary is not published to npm. |
| `mcp-tauri` | MCP server package for Tauri, enabling AI assistants to build, test, and debug Tauri v2 apps — UI automation, IPC monitoring, log streaming, mobile device listing, and plugin setup. |
<!-- END:mcp -->

---

See also: [bundles](bundles.md) · [skills](skills.md) · [agents](agents.md) · [steering](steering.md) · [SpecKit](speckit.md)
