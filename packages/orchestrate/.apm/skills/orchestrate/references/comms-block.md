ORCHESTRATION COMMS PROTOCOL - active run. Follow exactly.

Activation: a claim-holder receives only `CLAIM {bead-or-wisp-id}` or
`CLAIM queue:{filter}`. Read the BRIEF, metadata, comments, and linked wisps
before acting. Never treat prompt-carried task details as authority.

Envelope (harness wake): `to`={actor}, `summary`=5-10 words,
`message`=ONE verb plus a resource id. The wake is only a doorbell. Task,
question, review, and decision content stays on Beads.

Verbs (11): BLOCKED ADVICE REPORTED REVIEW FIX CONFLICT APPROVE MERGED DISMISS
ASK NO_WORK. A tiebreaker's binding result is ADVICE. Mirror each material
verb to the affected bead or wisp with the acting identity. Set `BEADS_ACTOR`
and `BD_ACTOR` to `metadata.actor` on every mutating Beads process.

Proof: every factual claim carries a `file:line`, command result, bead/wisp id,
or `untested`. Cite prior facts by reference; never paste them into a relay.

Scratch: working notes go to the node's worklog wisp or an artifact path.
Terseness governs wire messages and comments, not reasoning depth.

Delivery:
- Harness notification is an advisory immediate wake.
- The Beads wisp/thread is the P2P source for active-run communication.
- Material local outcomes are promoted to the work-bead comment.
- Cross-bead policy becomes a linked decision bead before action.
- Acknowledge or burn a wisp only after required promotion and dependency use.
- A retry after ambiguous send reconciles the returned id or inbox first.

Spawning:
- A domain specialist may spawn bounded, contract-free implementation
  children in its bound checkout. Children never claim, commit, push, manage
  worktrees, or spawn another writer.
- Every other actor spawns nothing. A child never spawns.

Blocked:
- Design/debug uncertainty creates an escalation wisp linked to the node.
  The orchestrator wakes an advisor; the advisor and specialist exchange
  content on that wisp without orchestrator relay.
- Product intent creates an ASK escalation wisp and human gate.
- No actor waits live on a peer. Checkpoint and exit, or use the bounded poll
  allowed by the runtime contract.
