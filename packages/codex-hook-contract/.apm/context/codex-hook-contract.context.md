---
x-lint:
  allow: [W6]
  reason: "the hook contract keeps complete event, payload, decision, and limitation reference tables"
---

# Codex CLI hook contract

This reference tracks the released Codex hook behavior documented at
<https://learn.chatgpt.com/docs/hooks>. It was refreshed on 2026-07-22 for
Codex CLI 0.144.5. Prefer that release documentation over schemas from Codex
`main`, which may contain unreleased fields.

## Supported events

Codex supports exactly these events:

| Event | Matcher input |
| --- | --- |
| `SessionStart` | `startup`, `resume`, `clear`, or `compact` |
| `SubagentStart` | subagent type |
| `PreToolUse` | local tool name, including `Bash`, `apply_patch` (`Edit`/`Write` aliases), MCP tools, and `Agent` for `spawn_agent` |
| `PermissionRequest` | same tool names as `PreToolUse` |
| `PostToolUse` | same tool names as `PreToolUse` |
| `PreCompact` | `manual` or `auto` |
| `PostCompact` | `manual` or `auto` |
| `UserPromptSubmit` | matcher ignored |
| `SubagentStop` | subagent type |
| `Stop` | matcher ignored |

Hooks are enabled by default. `[features] hooks = true|false` is the canonical
configuration key; `features.codex_hooks` is a deprecated alias.

Only synchronous `type: "command"` handlers run. Codex parses but skips
`prompt`, `agent`, and asynchronous command handlers. Non-managed hooks,
including plugin hooks, are skipped until the user reviews and trusts their
current hash through `/hooks`.

## Inputs

Every command hook receives one JSON object on stdin. Common fields include
`session_id`, `transcript_path`, `cwd`, `hook_event_name`, and `model`.
Turn-scoped events also include `turn_id`.

Tool events use:

```json
{
  "tool_name": "Bash",
  "tool_use_id": "...",
  "tool_input": {"command": "git status"}
}
```

`Bash` and `apply_patch` use `tool_input.command`; MCP and local function tools
place their arguments directly in `tool_input`. `spawn_agent` matches `Agent`.
`PostToolUse` adds `tool_response`.
Compatibility parsers may tolerate a legacy string `tool_input`, but new code
must implement the documented object shape first.

## Decisions and context

To deny `PreToolUse`, return:

```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Blocked by policy."}}
```

Codex also accepts `{"decision":"block","reason":"..."}` or exit code 2 with
the reason on stderr. To permit a tool and add model context, use
`permissionDecision: "allow"` with `additionalContext`.

Do not return `permissionDecision: "ask"`. Codex marks that hook run failed and
continues the tool call. A policy that needs user review should either deny with
actionable guidance or leave the decision to the normal approval flow.

`PermissionRequest` uses an event-specific decision object:

```json
{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"allow"}}}
```

`behavior` may be `allow` or `deny`; omit a decision to keep the normal prompt.
For a denial, add `decision.message`.

`SessionStart`, `SubagentStart`, and `UserPromptSubmit` can inject developer
context through `hookSpecificOutput.additionalContext`. `Stop` and
`SubagentStop` use `{"decision":"block","reason":"..."}` to continue work.
`PostToolUse` can replace model-visible feedback but cannot undo side effects.

## Enforcement limits

`PreToolUse` and `PostToolUse` cover simple Bash calls, `apply_patch`, MCP
tools, and local function tools such as `spawn_agent`. They do not intercept
hosted tools such as WebSearch. Hooks are guardrails, not a complete security boundary.
Use sandbox permissions, approval policy, managed requirements, and command
rules for enforcement.

Matching hooks launch concurrently. One hook cannot prevent another matching
hook from starting. `PostToolUse` runs for nonzero Bash exits, which is the
Codex workaround for Claude's `PostToolUseFailure`.

## Repository authoring rules

1. Route Claude-only events through a `*-claude-hooks.json` file. Never put
   them in a universal `.apm/hooks/hooks.json`.
2. Self-filter commands inside scripts. Codex does not define Claude's `if`
   handler field.
3. Use only synchronous command handlers in Codex variants.
4. Emit JSON for model-visible context; plain stdout is ignored by tool events.
5. Never use `permissionDecision: "ask"`.
6. Keep destructive enforcement in Codex sandbox/rules as well as hooks.
7. Run `.apm/scripts/audit-codex-config.py` after changing manifests, hooks,
   MCP config, or agent metadata.
