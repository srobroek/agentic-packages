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
| `REPORTED` | coder → orch | node, branch, worktree, commits, verify, risks, log, status |
| `REVIEW` | reviewer → orch | node, verdict(approve\|changes), numbered items, what's ok |
| `FIX` | orch → coder | node, the exact items to address, reviewer id |
| `CONFLICT` | gatekeeper → coder | node, with(node), files, required action |
| `APPROVE` | orch → gatekeeper | node, branch, base — integrate this approved node (the handoff trigger) |
| `MERGED` | gatekeeper → orch | node, sha, base, verify_after_merge |
| `DISMISS` | orch → coder | node (approved + merged; safe to exit) |
| `ASK` | any → orch | node, question, who is waiting |

Field vocabulary (any verb): `log:` pointer to your scratch file; `ref:`/`refs:`
a `file:line` or bead/node id backing a claim; `open:` a known-unfinished or
deferred item (distinct from `risks:` — hazards for the receiver); every factual
field is either a pointer or the marker `untested` (see `comms-block.md`).

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
APPROVE t3  branch: coder/t3-auth-middleware  base: main @ 3f9a1c2
```
```
to: main   summary: "t3 merged"
MERGED t3  sha: 9c8b7a6  base: main  verify_after_merge: green
```
