# Serena hooks

`hooks-serena` installs Serena's lifecycle hooks for Claude Code and Codex. It
does not register an MCP server, so the same hooks work with a direct Serena
connection or an MCP aggregator.

The package installs these commands:

| Client | Event | Matcher | Command |
| --- | --- | --- | --- |
| Claude Code | `PreToolUse` | `Read\|Grep\|Glob\|Bash` | `serena-hooks remind --client=claude-code` |
| Claude Code | `SessionStart` | all starts | `serena-hooks activate --client=claude-code` |
| Claude Code | `SessionEnd` | all ends | `serena-hooks cleanup --client=claude-code` |
| Codex | `PreToolUse` | `Bash` | `serena-hooks remind --client=codex` |
| Codex | `SessionStart` | `startup\|resume` | `serena-hooks activate --client=codex` |
| Codex | `Stop` | all stops | `serena-hooks cleanup --client=codex` |

Install Serena's CLI separately so `serena-hooks` is on the hook process
`PATH`.

The Claude `PreToolUse` matcher lists tools rather than being left empty. An empty
matcher runs on every tool call, and `serena-hooks remind` measured 74.4 ms median
against a 27.7 ms interpreter floor while producing no output on a `Read` payload.
The reminder only ever fires on read- and grep-shaped calls, so naming those tools
covers everything it can act on and stops it running on `Edit`, `Write`, `Agent`,
`Task`, `Skill`, and MCP tools.

## Claude Code auto-approval

This package does not install Serena's optional `auto-approve` hook. Serena's
documented matcher, `mcp__serena__*`, identifies a direct Serena registration.
An aggregator such as 1MCP changes the client-visible server namespace, and CLI
mode does not expose Serena calls as directly matchable MCP tool events. A
broad matcher could approve tools from another upstream server, so approval
remains under the client's permission policy.
