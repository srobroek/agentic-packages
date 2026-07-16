# Hooks and MCP packages

## Hook packages

Opt-in lifecycle hooks. Most hooks ship inside their owning package (code-intelligence, agent-coder, the MCP packages, speckit); the two below are standalone cross-cutting policy packages.

A package ships universal `.apm/hooks/hooks.json` only when behavior is genuinely identical, otherwise it ships `.apm/hooks/<pkg>-{claude,codex}-hooks.json`, plus a `scripts/` directory. APM deploys target-specific config and rewrites `${PLUGIN_ROOT}`. Codex supports `SessionStart`, `SubagentStart`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`, `UserPromptSubmit`, `SubagentStop`, and `Stop`; all other events stay in Claude variants. Codex runs only synchronous command handlers, requires trust review for plugin hooks, does not support `permissionDecision: "ask"`, and does not intercept every unified shell or non-MCP tool path. See [Codex compatibility](codex-compatibility.md) and the [hook contract package](../packages/codex-hook-contract/.apm/instructions/codex-hook-contract.instructions.md).

<!-- BEGIN:hooks -->
| Hook Package | Description |
| --- | --- |
| `hooks-attribution-guard` | Advises against AI authorship attribution in git commits (Co-Authored-By Claude/Anthropic, "Generated with/by AI", "AI-assisted/AI-generated", Claude Code trailers). Emits a non-blocking advisory (allow + additionalContext, exit 0) so the human stays the sole author of record. Scoped to attribution trailers/phrases so prose mentioning AI is not flagged. Cross-tool (Claude + Codex). |
| `hooks-bash-safety` | Bash safety guards tuned for autonomous agents: hard-block only unrecoverable ops (rm -rf / or $HOME root, mkfs, dd to a real block device, sandbox-bypass flag). dd to pseudo-devices (/dev/null, /dev/zero, /dev/random, /dev/urandom, /dev/stdout, /dev/stdin) is allowed. curl\|sh pipes emit a non-blocking warn (allow + advisory). sudo paired with destructive/disruptive verbs also warns. rm -rf defers to rm-rf-guard: project-local and temp-dir cleanups are silent; unexpanded $var targets are denied; ~/subpath, repo root/.git, and outside-tree paths warn (non-blocking). Quoted bypass forms (rm -rf "/etc") and flags-after-target (rm /path -rf) are denied. Matching is anchored to command position to avoid quoted-string false positives. No "ask" is ever emitted. Cross-tool (Claude + Codex). |
| `hooks-chezmoi-guard` | PreToolUse advisory (non-blocking) for files chezmoi ACTUALLY manages (exact membership in `chezmoi managed`, 60s cache). Emits permissionDecision:"allow" + additionalContext steering changes to the chezmoi source — the operation proceeds. Read-only references and unmanaged paths are silent. Cross-tool (Claude + Codex). |
| `hooks-close-keywords` | Fixes the GitHub "comma-list close" quirk, where a closing keyword binds to only the FIRST issue in a list (Closes #1, #2, #3 closes just #1). A shared normalizer distributes the keyword across every issue in a contiguous list (-> Closes #1, closes #2, closes #3) for close/closes/closed, fix/fixes/fixed, resolve/resolves/resolved. Two delivery layers: a pre-commit commit-msg hook that rewrites the message in place (tool-agnostic), and a PreToolUse guard on `gh pr create`/`gh pr edit` that emits a non-blocking advisory (allow + additionalContext carrying the corrected body) when a malformed comma-list close is detected. Cross-tool (Claude + Codex). |
| `hooks-git-safety` | Git safety guards tuned for autonomous agents. DENY only when a destructive op targets another working tree through an unexpanded shell variable or ~ (the guard cannot verify the target — agent re-issues with a literal path). All other destructive ops are non-blocking: reset --hard / checkout -- / restore / clean -f emit a warn (allow + advisory) only when uncommitted work would actually be lost; push --force/--force-with-lease always warns. branch -D, tag -d, stash drop/clear, worktree remove --force are passed silently (all reflog-recoverable). No "ask" is ever emitted. Cross-tool (Claude + Codex). |
| `hooks-git-workflow` | Opt-in git workflow hook: warn about uncommitted AND unpushed work at session end (continuous commit/push cadence). Cross-tool (Claude + Codex). |
| `hooks-package-investigate` | Non-blocking PreToolUse Bash hook that nudges the agent to investigate a dependency's trustworthiness, maintenance, quality, popularity, and alternatives BEFORE adding/installing it (lighter review for update/upgrade/remove). Cross-tool (Claude + Codex). |
| `hooks-portability-ci` | CI gate that runs shipped hook scripts through the real portability failure modes the audits found: bash 3.2 parse errors (;;& fallthrough, mapfile), GNU-only sed/grep constructs (\b word boundaries, lazy quantifiers), and string-form tool_input payloads that crash jq. Reports a summary and exits non-zero on any failure. Invoked on demand or wired into CI. |
| `hooks-precommit-gate` | PreToolUse advisory (non-blocking) for git commit/push when a repo opts into the pre-commit framework. When the repo has .pre-commit-config.yaml but the matching git hook is not installed, or --no-verify would skip the framework, emits a single permissionDecision:"allow" + additionalContext advisory — the operation proceeds. Silent in repos with no pre-commit config, so it adds zero friction elsewhere. Pairs with secrets-scan (enforcement lives in the pre-push hook). Cross-tool (Claude + Codex). |
| `hooks-quality` | Opt-in code-quality hooks: advisory linting/formatting feedback after edits and a quality check before commits. The before-commit gate is a FALLBACK — it defers when the pre-commit framework is installed (which already runs the same formatters), so it only fires in repos that have not adopted pre-commit. Cross-tool (Claude + Codex). |
| `hooks-subagent-worktree` | Non-blocking worktree-isolation advisory on every subagent spawn. A PreToolUse:Agent hook injects a short reminder — if the subagent WRITES files and runs in parallel with other writers, pass `isolation:"worktree"` (Claude branches it from your current HEAD); a read-only, different-repo, or lone-writer subagent needs none — and if it does run isolated, to COMMIT before finishing so the worktree branch retains the work. It NEVER denies a spawn (superseding the 1.x deny-gate, which guessed wrong and blocked legitimate work) and stays silent once isolation is already declared. Claude-only (the Agent spawn tool is Claude-specific); the Codex variant is a no-op. |
| `hooks-worktree` | Worktree lifecycle hooks: create worktrees outside the repo tree (in /tmp) to prevent nesting, and clean up the worktree directory and branch on removal. Claude-only WorktreeCreate/WorktreeRemove events; Codex requires explicit worktree wrapper commands because it has no equivalent lifecycle events. |
<!-- END:hooks -->

## MCP server packages

Pre-wired Model Context Protocol servers. Installing one adds the server's tools to your runtime's MCP config -- no manual server setup.

<!-- BEGIN:mcp -->
| MCP Package | Description |
| --- | --- |
| `mcp-codebase-memory` | MCP server package for the Codebase Memory MCP, providing graph-aware project orientation (symbol search, call paths, code snippets). |
| `mcp-context7` | MCP server package for Context7, providing current library and framework documentation lookups. |
| `mcp-mempalace` | MCP server package for MemPalace, a local-first cross-session memory layer for coding agents. Files verbatim conversation/decision history into a vector + temporal-graph store (ChromaDB, local embeddings, zero LLM calls) and recalls it via semantic + temporal search. Ships the mempalace-mcp stdio server, a SessionStart wake-up hook that injects relevant prior context, a mining script that ingests Claude Code / Codex session transcripts (run after significant work or relevant findings, per the package's steering), and steering that scopes MemPalace (cross-session memory) against codebase-memory (current code structure). Complements code intelligence; it is not code navigation. |
| `mcp-package-version` | MCP server for package version discovery |
| `mcp-playwright` | MCP server package for Playwright, providing browser automation and in-browser UI verification. |
| `mcp-repomix` | MCP server package for Repomix, providing bulk repository snapshots for analysis and review. |
| `mcp-serena` | MCP server package for Serena semantic code tools. The launcher selects the Codex or Claude Code context from the parent harness and can be overridden with SERENA_MCP_CONTEXT. |
| `mcp-tauri` | MCP server package for Tauri, enabling AI assistants to build, test, and debug Tauri v2 apps — UI automation, IPC monitoring, log streaming, mobile device listing, and plugin setup. |
<!-- END:mcp -->

---

See also: [bundles](bundles.md) · [skills](skills.md) · [agents](agents.md) · [steering](steering.md) · [external repos](external-repos.md) · [SpecKit](speckit.md)
