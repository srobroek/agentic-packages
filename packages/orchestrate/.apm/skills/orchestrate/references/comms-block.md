ORCHESTRATION COMMS PROTOCOL — active run. Follow exactly.

Envelope (SendMessage): `to`=<name|main>, `summary`=5–10 words, `message`=ONE
VERB + node id + labeled fields. Omit empty fields — never write "none".

Verbs (12): ASSIGN BLOCKED ADVICE REPORTED REVIEW FIX CONFLICT APPROVE MERGED
DISMISS ASK NO_WORK. A tiebreaker's binding call arrives as ADVICE. `NO_WORK`
reports one generic activation that found no compatible bead and mirrors to
the run epic.
Mirror every verb to beads: `bd audit record --actor <you> --kind tool_call
--tool-name orc.<verb-lowercase> --issue-id <bead>` + `bd comment <bead>
"<VERB> <node> …fields…"`. Set BEADS_ACTOR to your actor name.

Proof: every claim carries a pointer — `file:line`, a command result, or a
bead/node id — or the marker `untested`. Cite prior facts by ref; never
restate or paste content.

Scratch: working notes go to a scratch file in your worktree; cite it as
`log:` in reports. Reason at the depth the task needs — terseness governs
what you WRITE (wire messages, bead comments, session text ≤1 line), not how
you think. Never trade correctness for brevity; never pad.

Delivery:
- Harness notification is an advisory immediate wake.
- A Beads message thread is the durable source for the active run.
- Use `scripts/thread-message.py` for send, reply, inbox, show, and acknowledge.
- Every message stores actor, assignee, run, and work-bead identity.
- A root replies to the work bead. A reply replies to one open message.
- Acknowledge closes only that message.
- Inbox/show/thread/ack remain available after work closes; send/reply require
  an open run and active work bead.
- Resolved decisions remain comments or decision beads.
- Send/reply retries create another message after a prior success. Reconcile
  the returned id or inbox before retrying.
- Acknowledge is idempotent.

Spawning: none. Blocked — design call or stuck-red debug (not a lookup)? Send
`BLOCKED <node> kind:<design|debug>` to `main`, then idle. Need product intent
not in your brief? Send `ASK <node>` to `main`. Everything else routes through
the orchestrator.
