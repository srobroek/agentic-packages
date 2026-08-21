# Codex compatibility audit

Audited 2026-07-21 against Toolbox Codex 0.144.5.269 (upstream/npm 0.144.5),
Claude Code 2.1.211 documentation (local runtime 2.1.198), APM 0.26.0, and
Homebrew Git 2.54.0. Claude remains the behavioral baseline; Codex output uses
Codex-native contracts and APM transformations instead of invalid Claude fallbacks.

Primary references:

- <https://microsoft.github.io/apm/concepts/primitives-and-targets/>
- <https://microsoft.github.io/apm/reference/targets-matrix/>
- <https://github.com/microsoft/apm/issues/2108>
- <https://learn.chatgpt.com/docs/hooks>
- <https://learn.chatgpt.com/docs/build-plugins>
- <https://learn.chatgpt.com/docs/config-file/config-advanced#amazon-bedrock-provider>
- <https://code.claude.com/docs/en/hooks>

## Package surfaces

| Surface | Claude Code | Codex | Repository delivery |
| --- | --- | --- | --- |
| Skills | Native plugin/APM | Native plugin/APM | Both manifests reference `.apm/skills` |
| Hooks | Native plugin/APM | Native plugin/APM, supported events only | Shared or target-specific generated files |
| MCP | `.mcp.json` with `mcpServers` | direct map or `mcp_servers` | Separate `.mcp.json` and `.codex.mcp.json` |
| Agents | Native plugin `agents/*.md` | APM-generated `.codex/agents/*.toml` | Portable task agents remain in hybrid packages; raw/semantic profiles use one Codex-targeted package per agent |
| Steering | APM rules | APM-compiled `AGENTS.md` | Native plugins have no instructions component |
| Bundle dependencies | Claude manifest dependencies | No Codex manifest dependency field | APM composes the full dependency graph |

Every marketplace package has both required manifests. Native-only installation
is intentionally limited where Codex has no component field; the package matrix
below rates functionality when installed through APM, the project source of truth.

Hybrid packages can contain agents for both Claude and Codex. A verified APM
0.26.0 install transformed an agent bundled with a skill into
`.claude/agents/<name>.md` for Claude and `.codex/agents/<name>.toml` for Codex,
while deploying the skill to both runtimes. Agent extraction is therefore not
required for Codex compatibility. Package-level `target` still does not prevent
a caller from explicitly forcing a direct package install with the opposite
`--target`.

APM's Codex transformer serializes `name`, `description`, and
`developer_instructions`; it drops model metadata. Agent-bearing packages and
consumer lifecycle configuration handle the missing fields:

- Each agent-bearing package distributes `.apm/agent-models.yml`.
- `.apm/scripts/inject-agent-models.py` restores `model` and
  `model_reasoning_effort` after installation.
- Trusted `post-install` and `post-update` triggers run the injector.
- Setup, install, and update fail before the APM operation when lifecycle trust
  has not been granted.

APM lifecycle discovery reads admin policy, user configuration, and the
consuming project's root `apm.yml`; lifecycle blocks inside dependencies do not
run.

## Hook runtime differences

- Codex exposes 10 events; current Claude Code exposes 30.
- Codex executes only `type: "command"`. Claude also supports HTTP, MCP-tool, prompt, and agent handlers where allowed.
- Codex parses `async: true` but skips the handler. Claude runs asynchronous command hooks and can re-wake later.
- Codex has no Claude handler-level `if`; filtering must happen in matcher or script code.
- Codex ignores matchers on `UserPromptSubmit` and `Stop`.
- Codex Pre/PostToolUse intercept simple Bash, apply_patch, MCP calls, and local function tools. `spawn_agent` matches `Agent`; hosted tools such as WebSearch are not intercepted.
- Codex plugin hooks require trust review through `/hooks` after install or definition changes.

## Event parity

| Claude event | Codex | Functionality difference | Codex workaround |
| --- | --- | --- | --- |
| `SessionStart` | Yes | Same startup/resume/clear/compact matcher. Claude can persist environment changes; Codex injects developer context only. | None. |
| `Setup` | No | Claude has separate init and maintenance setup phases; Codex has no setup event. | Run setup in the launcher or CI; use a sentinel-guarded SessionStart only for per-session checks. |
| `InstructionsLoaded` | No | Claude reports eager and lazy instruction loads; Codex has no instruction-load observability event. | Keep policy in AGENTS.md and use SessionStart or an external watcher for coarse auditing. |
| `UserPromptSubmit` | Yes | Both can block or add context. Both ignore matcher for this event; Codex runs command handlers only. | None. |
| `UserPromptExpansion` | No | Claude intercepts slash-command, skill, and MCP-prompt expansion before expansion. | Parse explicit command text in UserPromptSubmit and put mandatory checks inside the skill workflow. |
| `MessageDisplay` | No | Claude can transform streamed display batches without changing transcript/model text. | Transform codex exec --json output in an external frontend; there is no in-process TUI equivalent. |
| `PreToolUse` | Yes | Claude supports allow/deny/ask/defer plus `if`. Codex covers local function tools as well as Bash, apply_patch, and MCP; `spawn_agent` matches `Agent`, while ask, defer, and `if` are unsupported. | Use `PreToolUse:Agent` for pre-spawn enforcement and sandbox, approvals, Git/CI policy, and script-side filtering for paths Codex does not intercept. |
| `PermissionRequest` | Yes | Both allow or deny an imminent approval. Codex rejects Claude input rewrites, permission updates, and interrupt controls. | None. |
| `PostToolUse` | Yes | Claude fires after success and identifies subagent calls. Codex also fires for nonzero Bash exits and covers local function tools. | Inspect tool_response in the handler, use SubagentStart/Stop for agent-scoped behavior, and retain external checks for hosted tools. |
| `PostToolUseFailure` | No | Claude has a dedicated failed-tool event with error metadata. Codex only folds nonzero Bash into PostToolUse. | Inspect PostToolUse for supported tools and use process/MCP logging elsewhere. |
| `PostToolBatch` | No | Claude can gate after a parallel tool batch before the next model call; Codex only has per-tool callbacks. | Accumulate PostToolUse records by turn_id and process at Stop; this cannot gate the immediate post-batch call. |
| `PermissionDenied` | No | Claude runs after an automatic permission denial and can request a model retry. | Move policy to PreToolUse or PermissionRequest and return a model-visible reason. |
| `Notification` | No | Claude exposes typed permission, idle, auth, elicitation, and background notifications. | Use Codex notify configuration, TUI notifications, or a codex exec --json wrapper. |
| `SubagentStart` | Yes | Both match agent type and inject initial context without blocking creation. Codex is command-handler only. | None. |
| `SubagentStop` | Yes | Both can continue a completed subagent. Claude additionally exposes background tasks and cron state. | None. |
| `TaskCreated` | No | Claude can reject task creation atomically; Codex has no task-creation event. | Validate task metadata in the orchestration skill before recording or spawning work. |
| `TaskCompleted` | No | Claude can veto task completion; Codex has no task-completion boundary. | Gate orchestration state with tests plus SubagentStop or Stop. |
| `Stop` | Yes | Both are turn-scoped and ignore matchers. Codex continues by creating a synthetic user prompt from the hook reason. | None. |
| `StopFailure` | No | Claude fires on API failure instead of Stop; Codex has no API-failure lifecycle event. | Inspect codex exec --json terminal/error events and process exit status externally. |
| `TeammateIdle` | No | Claude can keep an agent-team teammate working instead of idling. | Use SubagentStop as a quality gate and track idle/completion state in the orchestrator. |
| `ConfigChange` | No | Claude observes and can veto live config changes except managed policy. | Use requirements.toml/filesystem policy and external file monitoring. |
| `CwdChanged` | No | Claude reacts to directory changes and can update environment/watch paths. | Use direnv or a launcher; checking simple cd commands in PreToolUse is incomplete. |
| `FileChanged` | No | Claude watches configured files regardless of writer; Codex has no filesystem watcher event. | Use watchexec/entr; PostToolUse:apply_patch covers only intercepted Codex edits. |
| `WorktreeCreate` | No | Claude can replace default worktree creation and return the created path. | Use an explicit worktree wrapper/skill or Codex subagent worktree isolation. |
| `WorktreeRemove` | No | Claude receives the path during worktree cleanup. | Use a launcher finally/trap or an explicit cleanup workflow. |
| `PreCompact` | Yes | Both match manual/auto and can stop before compaction; output contracts differ. | None. |
| `PostCompact` | Yes | Both run after compaction. Claude supplies the generated summary; Codex supplies only the trigger. | None. |
| `SessionEnd` | No | Claude runs cleanup on actual session termination; Codex Stop is turn-scoped. | Wrap the process with cleanup and perform orphan cleanup on the next start. |
| `Elicitation` | No | Claude can accept, decline, cancel, or answer an MCP elicitation before the dialog. | Implement policy or automatic answers in the MCP server/proxy. |
| `ElicitationResult` | No | Claude can inspect, change, or decline the user response before it reaches MCP. | Validate or transform the response in the MCP server/proxy. |

## Package-specific adaptations

- `agent-builder`: APM transforms the bundled agents for both runtimes; both install without per-edit delegation reminders.
- `worktrunk-writer`: both runtimes consume parent-created Worktrunk leases; Codex unified shell paths remain outside complete hook interception.
- `speckit`: script-side filtering replaces Claude `if`; there is no Skill-tool reminder event.
- `orchestrate`: Codex spawn briefs embed protocol because skill-frontmatter hooks do not execute.
- `language-*`: Serena over MCP is the standard semantic and LSP-backed code interface for both Claude and Codex.
- `mcp-context7`: credential forwarding is runtime-managed with `env_vars` so no secret is persisted.

## Global APM and MCP state

- The durable global manifest contains 51 direct dependencies and targets `codex,claude`.
- The current lock resolves 63 dependency nodes. The automated Codex post-sync passes `--target codex`; Claude deployment is refreshed by the separate Claude-layer sync.
- The separate Claude sanitizer removes dead hook wiring and orphaned hook directories without changing non-hook settings.
- Codex agent model settings come from package-local `.apm/agent-models.yml` files and are restored by the post-deploy injector.
- Active global MCPs are Context7, Fetcher, MemPalace, Node REPL, 1Password, and OpenAI Developer Docs.
- Builder MCP is disabled at both AIM plugin contribution points. Asana is absent from durable and live Codex configuration.
- Context7 forwards `CONTEXT7_API_KEY` at runtime; no secret value is stored in `config.toml`.
- `apm-hooks.json` remains as APM ownership state; `hooks.json` is the sanitized Codex runtime config.

## Bedrock authentication

- Codex uses the built-in `amazon-bedrock` provider; durable config sets its AWS region only.
- Durable Codex config does not force an AWS profile; the former `claude-code` profile line remains commented.
- The Toolbox wrapper owns credential selection at launch. Codex does not store a `credential_process` command in `config.toml`.
- Toolbox accepts an explicit BYOA profile through `--aws-profile`; without one, its managed fallback profile invokes `codex credential-process`.
- A profile-unset Toolbox `codex exec` request completed successfully against the active Bedrock provider.

## Package-level differences

Packages omitted from this table have equivalent functionality through APM.
`Partial` means the package is usable but has the stated Codex gap.
`Claude-only` means no Codex lifecycle equivalent exists.
Native-plugin-only installation can expose fewer components because Codex
plugin manifests do not support every APM component type.

| Package | Status | Codex difference or workaround |
| --- | --- | --- |
| `adr-as-beads` | Partial | The write guard covers `apply_patch` and the file-write tools; a shell redirect into `docs/adr/` bypasses it. The pre-commit renderer rewrites the file from its bead regardless, so the loss is bounded to that one edit. |
| `agent-builder` | Partial | Agents work through APM; Claude-only edit reminder has no reliable Codex subagent identifier on PreToolUse. |
| `hooks-attribution-guard` | Partial | Simple Bash is covered; unified shell paths can bypass Codex hooks. Keep Git/CI enforcement. |
| `hooks-bash-safety` | Partial | Simple Bash is covered; unified shell paths can bypass Codex hooks. Keep sandbox and approval controls. |
| `hooks-chezmoi-guard` | Partial | Bash and apply_patch aliases are covered; other write/shell routes need source-first steering and filesystem policy. |
| `hooks-close-keywords` | Partial | Simple Bash advisory only; use the supplied commit-msg/pre-commit gate for tool-independent coverage. |
| `hooks-git-safety` | Partial | Simple Bash is covered; use Git protections and compiled steering for complete policy. |
| `hooks-package-investigate` | Partial | Simple package-manager commands are covered; invoke the investigation skill for unsupported shell routes. |
| `hooks-quality` | Partial | apply_patch and simple Bash are covered; use pre-commit/CI for other write and shell paths. |
| `hooks-worktrunk` | Partial | Both PreToolUse guards work; the WorktreeCreate/WorktreeRemove provider is Claude-only because Codex has no worktree lifecycle events. Use `wt` commands directly. |
| `language-go` | Full | Installs Go quality and steering plus Serena over MCP, the standard semantic and LSP-backed interface for both Claude and Codex. |
| `language-python` | Full | Installs Python quality and steering plus Serena over MCP, the standard semantic and LSP-backed interface for both Claude and Codex. |
| `language-rust` | Full | Installs Rust quality and steering plus Serena over MCP, the standard semantic and LSP-backed interface for both Claude and Codex. |
| `language-shell` | Full | Installs portable shell steering plus Serena over MCP, the standard semantic and LSP-backed interface for both Claude and Codex. |
| `language-terraform` | Full | Installs Terraform and HCL steering plus Serena over MCP, the standard semantic and LSP-backed interface for both Claude and Codex. |
| `language-typescript` | Full | Installs TypeScript quality and steering plus Serena over MCP, the standard semantic and LSP-backed interface for both Claude and Codex. |
| `orchestrate` | Partial | Skill works; native Codex role profiles receive task-specific spawn briefs because APM agents are Claude-only and Codex ignores skill-frontmatter hooks. |
| `release-please` | Partial | Skill works; Bash advisory inherits Codex simple-shell interception limits. |
| `worktrunk-writer` | Partial | Preparation, explicit lease validation, inventory, and apply_patch/simple Bash hooks work; unified shell paths still require sandbox policy and explicit validation. |

## Validation

`.apm/scripts/audit-codex-config.py` validates all Codex marketplace manifests,
component paths, MCP shapes, routed hook events, command-only/synchronous handler
constraints, explicit timeouts, and script paths.
CI runs it after native plugin and documentation regeneration.
