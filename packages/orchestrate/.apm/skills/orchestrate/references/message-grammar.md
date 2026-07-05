# Message grammar

Inter-agent messages (SendMessage) are terse and objective but **complete** — the
receiver is another model and must act without guessing. Frame: a **verb** and the
**node id** up front, then a labeled field block carrying every fact the receiver
needs. One verb per message; facts over prose. Every state-changing message is
mirrored to the ledger with the matching `--event`.

SendMessage envelope: `to` = recipient name (or `main` for the orchestrator from a
background subagent), `summary` = 5–10 words, `message` = the body below.

## Terseness is not just the envelope

The same terse, factual register governs an agent's **reasoning and output**, not
only its `SendMessage` bodies. Every agent in the run — coder, reviewer,
gatekeeper, scribe, advisor — thinks and reports in the same compressed style:
short, direct, facts over prose. This is a cost rule, not a stylistic one — long
reasoning and padded reports burn tokens and context across the whole fleet.

- **Reasoning:** think in the fewest steps the problem needs; no narration of
  obvious moves, no restating the brief, no throat-clearing. Get to the decision.
- **Output/reports** (ledger `--output`, `REPORTED`/`REVIEW` bodies, advisor
  `ADVICE`, end-of-run report): labeled fields and short lines, never paragraphs.
  State the fact, the location (`file:line`), and the action — nothing else.
- **No prose padding:** drop preamble, summaries of what you just did, hedging,
  and closing pleasantries. If a field is empty, omit it rather than explaining
  its absence.

## Verbs

| Verb | From → To | Carries |
|---|---|---|
| `ASSIGN` | orch → coder | node, title, scope, base, store, deps, commands, protocol |
| `BLOCKED` | coder → orch | node, the reasoning question + minimal code context |
| `ADVICE` | advisor → orch → coder | node, answer, rationale, refs (orch relays) |
| `REPORTED` | coder → orch | node, branch, worktree, commits, verify, risks, status |
| `REVIEW` | reviewer → orch | node, verdict(approve\|changes), numbered items, what's ok |
| `FIX` | orch → coder | node, the exact items to address, reviewer id |
| `CONFLICT` | gatekeeper → coder | node, with(node), files, required action |
| `APPROVE` | orch/reviewer | node (delta re-reviewed clean) |
| `MERGED` | gatekeeper → orch | node, sha, base, verify_after_merge |
| `DISMISS` | orch → coder | node (approved + merged; safe to exit) |
| `ASK` | any → orch | node, question, who is waiting |
| `RULE` | tiebreaker → orch | node, decision + rationale |

## Worked example — one node (`t3`) end to end

**Assign**
```
to: coder-t3   summary: "assign node t3 auth-token refactor"
ASSIGN t3
  title:    Refactor auth token validation into middleware
  scope:    src/auth/**, tests/auth/**
  base:     main @ 3f9a1c2
  store:    /home/…/.orchestration/run-7f3a/     # DAG + ledger here
  deps:     t1(done), t2(done)
  commands: state=graph.py …set-state t3 <s>; log=ledger.py …add --node t3 --actor coder-t3 …
  protocol: on block → BLOCKED to main (don't spawn). green → commit+push, log reported, REPORTED to main, stay alive.
```

**Blocked → orchestrator brokers an advisor** (the coder spawns nothing)
```
to: main        summary: "blocked on token refresh race"
BLOCKED t3
  need:    Concurrent refresh can double-issue tokens. (a) mutex around refresh vs
           (b) single-flight dedupe by jti — which is safe here?
  context: src/auth/refresh.rs:40-88; tests/auth/refresh_test.rs
```
The orchestrator spawns a `workflow-advisor`, relays the question, receives its
answer, then relays it back to the coder:
```
to: advisor-t3  summary: "advice: single-flight dedupe"     # advisor → main
ADVICE t3
  answer:  Use (b) single-flight keyed by jti.
  because: refresh runs in multiple worker procs; an in-proc mutex won't serialize them.
  refs:    guard with the existing jti store.
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

**Integrate (conflict pushback, then merge)**
```
to: coder-t3  summary: "t3 conflicts with t5 on routes"
CONFLICT t3  with: t5  files: src/api/routes.rs
  need: rebase on updated main, re-verify, push, re-report.
```
```
to: main   summary: "t3 merged"
MERGED t3  sha: 9c8b7a6  base: main  verify_after_merge: green
```

**Question to the human**
```
to: main   summary: "human decision needed on t3 scope"
ASK t3
  question: Refactor also removes deprecated /auth/legacy. Delete now, or keep behind a flag?
  waiting:  coder-t3 is idle pending your answer
```
The orchestrator surfaces `ASK` to the user, holds `coder-t3`, then forwards the
answer (`FIX t3 …`) or lets the user message `coder-t3` directly.
