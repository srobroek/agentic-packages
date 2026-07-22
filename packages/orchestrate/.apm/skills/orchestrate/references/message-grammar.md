# Message grammar

Envelope, verb list, register, proof/ref rules, and the no-spawning rule: see
`references/comms-block.md` (canonical, auto-injected into every subagent).
This file adds the per-verb field table and a worked example.

## Verbs

| Verb | From → To | Carries |
|---|---|---|
| `ASSIGN` | orch → coder | node, title, scope, base, store, deps, commands, protocol |
| `BLOCKED` | coder → orch | node, `kind:design\|debug`, the question + minimal code context |
| `ADVICE` | advisor → orch → coder | node, answer, rationale, refs (orch relays) |
| `REPORTED` | coder → orch | node, verify, plus branch+commit(s)/PR for git evidence or `output_ref` for non-git evidence |
| `REVIEW` | reviewer → orch | node, verdict(approve\|changes), numbered items, what's ok |
| `FIX` | orch → coder | node, the exact items to address, reviewer id |
| `CONFLICT` | gatekeeper → coder | node, with(node), files, required action |
| `APPROVE` | orch → gatekeeper | node, branch, base; watcher wake-ups carry source, repo, PR, head, plus dispatch or lifecycle receipt fields |
| `MERGED` | gatekeeper → orch | node, sha, base, verify_after_merge |
| `DISMISS` | orch → coder | node (approved + merged; safe to exit) |
| `ASK` | any → orch | node, one exact nonempty question, impact, waiting actor, resume condition |
| `NO_WORK` | generic worker → orch | run epic, queue activation, `reason:no-compatible-work` |

Field vocabulary (any verb): `log:` pointer to your scratch file; `ref:`/`refs:`
a `file:line` or bead/node id backing a claim; `open:` a known-unfinished or
deferred item (distinct from `risks:` — hazards for the receiver); every factual
field is either a pointer or the marker `untested` (see `comms-block.md`).

## Durable replies-to threads

`scripts/thread-message.py` uses Beads 1.1.0 message wisps and native
`replies-to` dependencies. It does not require Gas Town, a daemon, or a poll
loop. Every success and failure is one JSON envelope on stdout.

Message metadata contains these fields:

| Field | Meaning |
|---|---|
| `actor` | sender identity and `BEADS_ACTOR` used for the create |
| `assignee` | recipient identity; matches the Beads assignee field |
| `run` | run epic id |
| `bead` | work bead id under the run epic |
| `protocol` | `replies-to` |

A root message has one `replies-to` edge to its work bead. A reply has one
`replies-to` edge to an open message in the same run and work bead. Replies may
branch. The helper rejects missing, deleted, non-message, wrong-run,
wrong-bead, self-referential, and cyclic parents.

```text
python3 scripts/thread-message.py send \
  --actor orchestrator --assignee coder-t3 --run orc-7f3a --bead orc-7f3a.3 \
  --subject "Review requested" --body "Read the node report."

python3 scripts/thread-message.py reply \
  --actor coder-t3 --assignee orchestrator --run orc-7f3a --bead orc-7f3a.3 \
  --parent orc-wisp-abc --subject "Report ready" --body "See output_ref."

python3 scripts/thread-message.py inbox \
  --actor coder-t3 --run orc-7f3a --bead orc-7f3a.3

python3 scripts/thread-message.py show --message orc-wisp-abc --thread

python3 scripts/thread-message.py acknowledge --actor coder-t3 --run orc-7f3a \
  --bead orc-7f3a.3 --message orc-wisp-abc
```

- Inbox discovery uses `bd list --include-infra --type message --assignee
  <actor> --status open`. Normal work lists exclude messages.
- Inbox output keeps validated messages under `messages` and malformed or
  legacy records under `invalid`. One invalid record does not hide valid
  messages.
- Acknowledgement validates the recipient and message type before closing the
  message. It never closes the linked work bead or a parent message.
- Inbox, show, thread rendering, and acknowledgement remain available after
  the work bead closes. Send and reply require an open run and an active work
  bead.

Harness notification remains the immediate wake path. Failure to notify does
not remove the Beads message. The recipient reads its inbox after resume.

Message wisps retain coordination for the active run and may be compacted
after acknowledgement. They do not store durable decisions. The authoritative
carrier table is in `references/beads-store.md`.

A message is material when its outcome changes a choice, default, scope,
route, ordering, acceptance evidence, disposition, human answer, or later
work. Before acting or closing from a material message:

1. Promote a bead-local outcome to an actor-attributed work-bead comment.
2. Promote a cross-bead, cross-agent, cross-package, shared-contract,
   ordering, or later-work outcome to a linked `decision` bead.
3. Read the promoted record and every non-blocking `relates-to`/`validates`
   link back from Beads.
4. Cite that durable record in the action or terminal report.

A material message not promoted has no policy effect. Acknowledgement,
compaction, or a lost harness wake never erases the promoted source of truth.
An artifact or `output_ref` is evidence only until a comment or decision bead
cites it. A human answer received in a thread is promoted before the stored
`waiting_human` resume instruction runs. Late messages for closed work follow
the late-evidence and follow-up rules in `references/lifecycle.md`.

`send` and `reply` are create operations. Each successful retry creates a new
message. A caller records the returned message id, then checks `inbox` or
`show` before retrying an ambiguous failure. `acknowledge` is idempotent and
reports `already_closed:true` for a duplicate acknowledgement.

## Evidence and empty activations

`REPORTED` accepts exactly one of these evidence shapes:

- Git commit: `branch`, `commit` or `commits`, and `verify`.
- Git pull request: `branch`, `pr`, and `verify`.
- Non-git: `output_ref` and `verify`.

A generic activation that loses a claim race or finds no compatible work does
not claim another bead. Its epic, queue, and reason fields are nonempty:

```text
NO_WORK queue:generic
epic: orc-7f3a
queue: agent:generic
reason: no-compatible-work
```

## Worked example — one node (`t3`) end to end

**Assign**
```
to: coder-t3   summary: "assign node t3 auth-token refactor"
ASSIGN t3
  title:    Refactor auth token validation into middleware
  bead:     orc-7f3a.3
  scope:    src/auth/**, tests/auth/**
  base:     main @ 3f9a1c2
  epic:     orc-7f3a
  artifacts: /home/…/.orchestration/run-7f3a/artifacts/
  deps:     t1(done), t2(done)
  commands: claim=bd update orc-7f3a.3 --claim + stamp branch/worktree/base_sha metadata;
            state=bd set-state orc-7f3a.3 state=<s>; log=bd audit record + bd comment
  protocol: on block → BLOCKED to main (don't spawn). green → commit+push, state=reported, REPORTED to main, stay alive.
```

**Blocked → orchestrator brokers an advisor** (the coder spawns nothing)
```
to: main        summary: "blocked on token refresh race"
BLOCKED t3
  kind:    design
  need:    Concurrent refresh can double-issue tokens. (a) mutex around refresh vs
           (b) single-flight dedupe by jti — which is safe here?
  context: src/auth/refresh.rs:40-88; tests/auth/refresh_test.rs
```
```
to: coder-t3    summary: "advice on t3: single-flight dedupe"   # main → coder
ADVICE t3
  answer:  Use (b) single-flight keyed by jti.
  because: multi-proc refresh; in-proc mutex won't serialize.
  refs:    existing jti store.
```

**Report (then stays alive)**
```
to: main        summary: "t3 reported, green, awaiting review"
REPORTED t3
  branch:   coder/t3-auth-middleware
  worktree: /home/…/.claude/worktrees/t3
  commits:  a1b2c3d refactor→middleware; d4e5f6a single-flight refresh
  changed:  src/auth/middleware.rs, src/auth/refresh.rs, tests/auth/*
  verify:   green (cargo test -p auth = 41 passed; clippy+fmt clean)
  risks:    validate_token signature changed — callers in src/api/** updated in scope
  log:      /home/…/worktrees/t3/.scratch.md
  status:   alive, awaiting REVIEW
```

**Review → fix → approve**
```
to: main   summary: "t3 review: 2 changes"
REVIEW t3  verdict: changes  items: 2
  1. src/auth/middleware.rs:52 — error swallows underlying cause; propagate it
  2. tests/auth/refresh_test.rs — add the concurrent double-refresh regression test
  ok: structure, naming, single-flight approach sound
```
```
to: coder-t3   summary: "apply 2 review fixes on t3"
FIX t3
  items: 1) propagate error at middleware.rs:52  2) add double-refresh regression test
  reviewer: reviewer-t3 (kept alive; re-reviews delta)
```
```
to: main   summary: "t3 approved"
REVIEW t3  verdict: approve  note: both items resolved; delta re-reviewed
```

**Handoff to the gatekeeper**
```
to: gatekeeper  summary: "t3 approved, ready to integrate"
APPROVE t3
branch: coder/t3-auth-middleware
base: main @ 3f9a1c2
```

A watcher-backed PR uses the same verb after deterministic dispatch resolution:

```
APPROVE t3
branch: coder/t3-auth-middleware
base: main @ 3f9a1c2
source: release-queue-watch
repo: owner/repo
pr: 42
head: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
dispatch: owner/repo#42@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

A lifecycle wake-up uses the same verb but cannot enter the merge path:

```text
APPROVE t3
branch: coder/t3-auth-middleware
base: main @ 3f9a1c2
source: release-queue-watch-lifecycle
repo: owner/repo
pr: 42
head: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
transition: failed
lifecycle: owner/repo#42#failed#opaque
```
```
to: main   summary: "t3 merged"
MERGED t3  sha: 9c8b7a6  base: main  verify_after_merge: green
```
