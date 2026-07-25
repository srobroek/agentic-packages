# Contract: Hook I/O

## SubagentStop (per-agent and universal)

**Input (stdin JSON)** -- fields used; all optional-tolerant (fail open):

| Field | Claude | Codex | Use |
|---|---|---|---|
| `agent_type` | ✓ | ✓ | rules-file selection / universal dispatch |
| `agent_id` | ✓ | ✓ | actor-name derivation |
| `stop_hook_active` | ✗ | ✓ | Codex re-entrancy guard |
| `transcript_path` | ✓ | ✓ (`agent_transcript_path`) | unused (bead is the record) |

**Claim resolution**: actor name embeds the claim identity
(`<role>-<node-bead>` / `<role>-<domain>`); the hook queries
`bd list --assignee <derived-actor> --json`. No claim → exit 0 silently
(universal net) / exit 0 (per-agent -- nothing to validate).

**Output (stdout JSON)** -- Codex requires JSON; Claude accepts it:

Allow: `{}` (exit 0).

Block (exit 0 + decision, or exit 2 with reason on stderr for Claude):

```json
{
  "decision": "block",
  "reason": "{\"bead\":\"<id>\",\"agent\":\"<type>\",\"attempt\":2,
             \"failed_checks\":[{\"check\":\"push\",\"detail\":\"metadata.push missing\"}],
             \"violations\":[{\"check\":\"state_authority\",\"detail\":\"state=closed set; deny_states\"}]}"
}
```

Rules: diagnosis only -- no remediation text (contract lives in the agent
definition); failure-specific (only failed checks appear); `attempt` counts
toward bounce.

**Bounce (attempt ≥ 3)**: exit 0 allow + side effects in the same invocation:
BOUNCE comment (accumulated evidence), `--assignee ""`, non-terminal state,
`stop_attempts`/`review_round` reset. Bead is clean-while-unassigned.

**Failure policy**: malformed input, missing rules file for an unknown agent,
bd unreachable → exit 0 (fail open, constitution III). Never `ask`.

## SubagentStart (universal)

Injects one short paragraph (additionalContext): claiming a bead in this
workspace binds the generic bead contract; `state=failed` + FAILED comment is
the always-valid exit. No matcher; both runtimes; never blocks.

## PreToolUse claim-deny (orchestrator)

Fires only when the session run-marker is set (orchestrate skill sets it at
run start; env var + marker file probe). Matches `bd` commands carrying
`--claim` / claim-equivalent forms. Decision: deny with self-correction text
("orchestrators route; dispatch to a worker"). Without run-marker: allow
silently. Codex: advisory-strength (partial interception) -- accepted.

## Attachment matrix

| Hook | Claude | Codex |
|---|---|---|
| Per-agent SubagentStop | agent frontmatter `hooks:` | config entry, matcher `agent_type` |
| Universal SubagentStart/Stop | settings hooks, no matcher | config entry, no matcher |
| Claim-deny | PreToolUse:Bash, run-marker-gated | same, advisory-strength |
