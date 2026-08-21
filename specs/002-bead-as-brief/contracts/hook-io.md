# Contract: Hook I/O

## SubagentStop (per-agent and universal)

**Input (stdin JSON)** -- fields used; all optional-tolerant (fail open):

| Field | Claude | Codex | Use |
|---|---|---|---|
| `agent_type` | ✓ | ✓ | rules-file selection / universal dispatch |
| `agent_id` | ✓ | ✓ | actor-name derivation |
| `stop_hook_active` | ✗ | ✓ | Codex re-entrancy guard |
| `transcript_path` | ✓ | ✓ (`agent_transcript_path`) | unused (bead is the record) |

**Activation-resource resolution**: the orchestrator stamps the hook-visible
id as `metadata.runtime_context`. The hook queries infrastructure and durable
resources with `bd list --include-infra --all --json`, selects the most recent
resource for that context, and validates it after claim release or wisp
closure. `metadata.runtime_handle` is parent routing state and is not used for
hook identity. A legacy resource without runtime context falls back to actor
lookup. Any active claim at stop is a `claim_release` violation.

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
BOUNCE comment (accumulated evidence), reopen a prematurely closed activation
resource, `--assignee ""`, non-terminal open state, and
`stop_attempts`/`review_round` reset.

**Failure policy**: malformed input, missing rules file for an unknown agent,
bd unreachable → exit 0 (fail open, constitution III). Never `ask`.

## SubagentStart (universal)

Injects one short paragraph (additionalContext): claiming a bead in this
workspace binds the generic bead contract; `state=failed` + FAILED comment is
the always-valid exit. No matcher; both runtimes; never blocks.

## UserPromptSubmit run activation

Reads the raw `prompt` value and matches only a leading `/orchestrate` or
`$orchestrate` invocation. Before the lead can issue a tool call, it atomically
creates `.orchestration/.active-run` with `run_id=pending` and the runtime
session id. The lead binds `pending` to the created run epic through the
installed hook entry before dispatch. A restart preserves an existing run id.
Ordinary prompts leave no marker. A marker write failure blocks the prompt.

## PreToolUse activation guard

For claim-holder Agent spawns, accepts only the checkout-backed WAIT grammar
from the activation protocol. A directed resource must resolve through
`bd show`, remain non-terminal and unclaimed, and match its stamped checkout
and lease. For SendMessage activation, accepts only
`CLAIM <resource-id>` sent to `metadata.runtime_handle` after
`metadata.runtime_context` is present, or a canonical checkout-backed queue
claim. Task-bearing, combined, missing-resource, missing-handshake,
wrong-handle, and pending-marker activations are denied. Denials use the PreToolUse
`hookSpecificOutput.permissionDecision=deny` envelope accepted by both
runtimes.

## PreToolUse claim-deny (orchestrator)

Fires only when the run marker is set by UserPromptSubmit or
`ORCHESTRATE_RUN`. Matches `bd` commands carrying `--claim`. T0 claims are
denied. A worker claim passes only when the command prefix carries equal,
non-lead `BEADS_ACTOR` and `BD_ACTOR` identities; every claim segment in a
multi-command input must satisfy that envelope. Without a run marker, allow
silently. Codex enforcement remains advisory-strength because tool
interception is partial. Denials use the same PreToolUse hook-specific
envelope as the activation guard.

## Attachment matrix

| Hook | Claude | Codex |
|---|---|---|
| Run activation | UserPromptSubmit, matcher ignored | same |
| Per-agent SubagentStop | agent frontmatter `hooks:` | config entry, matcher `agent_type` |
| Universal SubagentStart/Stop | settings hooks, no matcher | config entry, no matcher |
| Activation guard | PreToolUse:Agent/SendMessage | same |
| Claim-deny | PreToolUse:Bash, run-marker-gated | same, advisory-strength |
