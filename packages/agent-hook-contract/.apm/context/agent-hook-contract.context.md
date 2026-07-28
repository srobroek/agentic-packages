---
x-lint:
  allow: [W6]
  reason: "the hook contract keeps complete event, payload, decision, and limitation reference tables"
---

# Agent hook contract

How to write a hook that runs under both Claude Code and Codex CLI. This covers
the events each tool fires, the payload shape, the accepted decisions, and the
language and performance rules this repository applies to its own hooks.

The Codex behavior tracks the released contract at
<https://learn.chatgpt.com/docs/hooks>, refreshed 2026-07-22 for Codex CLI
0.144.5. Prefer that release documentation over schemas from Codex `main`, which
may carry unreleased fields.

## Language: Python by default

Write hooks in Python. Reach for shell only when the hook shells out for
everything it does and holds no logic of its own, such as a wrapper that
forwards to one command and returns its exit code.

The reason is not taste. A hook that parses a shell command with `grep` and
`sed` is writing a tokenizer in a language that has none, and every gap in that
tokenizer is a bypass. This repository's `rm -rf` guard collected one bypass
apiece for wrapper prefixes, env assignments, leading tabs, path traversal, and
trailing quotes, each found by fuzzing after the guard shipped. Python has a
lexer, a JSON parser, and a path normalizer in its standard library.

Python is also faster here, which is the part that surprises people. Measured on
an EDR-monitored macOS host, where every `exec` carries a scanning tax:

| Approach | Median per call |
| --- | --- |
| `bash` plus one `jq` parse and one `jq` emit | 50 ms |
| `bash` plus two `jq` parses and one `jq` emit | 134 ms |
| Python, same work, no subprocesses | 44 ms |

A Python interpreter starts about 9 ms slower than `bash`, and that gap is the
whole of bash's advantage. A single `jq` spawn costs more than the gap, so **any
hook that touches `jq` is both faster and safer in Python**. Since every hook
parses a JSON payload on stdin, that is every hook.

## Performance rules

A `PreToolUse:Bash` hook runs on every shell command the agent issues, and all
matching hooks launch concurrently. With two dozen registered, every wasted
millisecond is a tax on the whole session.

1. **Never `uv run` a per-tool-call hook.** It costs roughly three times a plain
   `python3` start, all of it spent before the hook does any work.
   `uv run --script` is fine for `SessionStart` and other once-per-session
   events, where dependency isolation is worth the startup.
2. **Standard library only on the hot path.** No third-party import. A git
   library is the trap: importing `pygit2` or `GitPython` costs more than the
   subprocesses either would replace, and a hook process is too short-lived to
   amortize an import.
3. **Find the repository root in-process.** Walking parents for a `.git` entry
   is exact and roughly three orders of magnitude cheaper than spawning
   `git rev-parse --show-toplevel`.
4. **Batch the git calls you genuinely need.** One `git rev-parse A B C` returns
   three answers for less than the cost of three separate calls. Prefer one
   `subprocess.run` over a loop.
5. **Bail before you parse.** Test the raw stdin bytes for a literal substring
   the hook requires (`commit`, `rm`, `worktree`) and exit 0 when it is absent.
   Keep the filter a strict superset of the real trigger so it cannot mask
   something the structured check would have caught.
6. **Keep slow scanners off the synchronous path.** A secret scanner or test run
   belongs in a git hook or a pre-commit stage, where it blocks a commit rather
   than every tool call.

## Reliability rules

1. **Fail open.** An unreadable payload, a missing tool, or an unexpected
   exception exits 0 and allows. A guard that crashes closed wedges the agent;
   one that crashes open loses a single check. Wrap the body and swallow.
2. **Never emit `permissionDecision: "ask"`.** It waits for a human, so it stalls
   an autonomous run, and Codex marks the hook run failed and continues the call
   anyway. Deny with actionable guidance, or allow with an advisory.
3. **Write denials to the model, not the user.** The agent re-issues the call, so
   a denial reason must say what to do differently: name the rule, name the
   offending token, give the corrected form.
4. **Accept a string `tool_input`.** Some callers send `tool_input` as a bare
   string rather than an object. In `jq`, `.tool_input.command // .tool_input`
   *throws* on a string and silently bypasses the guard; in Python, check
   `isinstance(ti, dict)` first.
5. **Self-filter inside the script.** Codex has no equivalent of Claude's `if`
   handler field, so a hook shared across both tools does its own matching.

## Supported events

Codex supports exactly these events. Anything else is Claude-only and belongs in
a `*-claude-hooks.json` variant.

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
Codex configuration key; `features.codex_hooks` is a deprecated alias.

Only synchronous `type: "command"` handlers run under Codex. It parses but skips
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

Read `cwd` rather than trusting the process working directory, and canonicalize
it: on macOS the payload may carry `/tmp/x` where git reports `/private/tmp/x`,
and the two share no prefix.

## Decisions and context

To deny a `PreToolUse` call, return:

```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Blocked by policy."}}
```

Codex also accepts `{"decision":"block","reason":"..."}`, or exit code 2 with the
reason on stderr. To permit a call and add model-visible context, use
`permissionDecision: "allow"` with `additionalContext`.

`PermissionRequest` uses an event-specific decision object:

```json
{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"allow"}}}
```

`behavior` may be `allow` or `deny`; omit a decision to keep the normal prompt.
For a denial, add `decision.message`.

`SessionStart`, `SubagentStart`, and `UserPromptSubmit` inject developer context
through `hookSpecificOutput.additionalContext`. `Stop` and `SubagentStop` use
`{"decision":"block","reason":"..."}` to continue work. `PostToolUse` can replace
model-visible feedback but cannot undo side effects.

Emit JSON for anything the model must see. Plain stdout is ignored on tool
events.

## Enforcement limits

`PreToolUse` and `PostToolUse` cover simple Bash calls, `apply_patch`, MCP tools,
and local function tools such as `spawn_agent`. They do not intercept hosted
tools such as WebSearch.

Treat a hook as a guardrail against the honest mistake. An agent that wants to
evade one can, and a hook that reaches for airtight coverage only gets slow and
brittle. Real enforcement belongs in sandbox permissions, approval policy,
managed requirements, and command rules.

Matching hooks launch concurrently, so one hook cannot prevent another from
starting, and two hooks guarding the same operation are defense in depth rather
than a sequence. `PostToolUse` runs for nonzero Bash exits, which is the Codex
workaround for Claude's `PostToolUseFailure`.

## Repository authoring rules

1. Route Claude-only events through a `*-claude-hooks.json` file. Never put them
   in a universal `.apm/hooks/hooks.json`.
2. Ship hook scripts under the package's `scripts/` directory, and commit a
   bare-path script mode 755. APM writes the source mode on first deploy and
   thereafter skips content-identical files, so a later mode fix never reaches
   an install that already has the wrong bit.
3. Cover every guard with a test suite: `tests/*.bats` for shell, `test_*.py` for
   pytest modules, `_test_*.py` for standalone harnesses. A guard's negative
   cases matter more than its positive ones, so prove that benign commands and
   quoted prose do not trip it.
4. When porting a guard to Python, keep the existing suite as the oracle. Prove
   behavior parity against it before porting the tests themselves.
5. Keep destructive enforcement in Codex sandbox and command rules as well as in
   hooks.
6. Run `.apm/scripts/audit-codex-config.py` after changing manifests, hooks, MCP
   config, or agent metadata.
