---
x-lint:
  allow: [E3]
  reason: "design reference documenting the model-routing tier table; model names are the subject matter, not instructions to load a model"
---
# Bead-as-Brief -- orchestrate v2 architecture

Status: Accepted -- bead orc-3v0. Supersedes the ASSIGN-prompt contract in
spawn-brief.md and the gatekeeper merge path in lifecycle.md.

All task data for a node lives on the node bead. Spawn prompts carry only the
activation verb. Contracts bind to claims and are enforced by hooks. Ephemeral
coordination rides wisps; durable evidence stays on beads. The orchestrator
spawns and observes; it never relays content and never claims.

Cross-package doctrine (wisps, graph links, labels, gates) lands in the beads
package steering; this spec consumes it. Speckit adoption is tracked as
orc-pyq.

---

## Principles

1. **Bead-as-brief.** The bead carries the task; the prompt carries only
   `CLAIM <id>`. Nodes are crash-resumable, queue-handoffable, auditable
   without orchestrator relay.
2. **Claim ⟺ contract.** An actor holding a claim is bound by a completion
   and authority contract, enforced at SubagentStop. An actor without a claim
   has no bead contract. Both directions hold for every agent, known or not.
3. **Metadata = machine-checkable scalars; comments = narrative.** Every
   metadata key is referenced by at least one rule, spawn decision, or merge
   step. Anything else is a comment.
4. **Durable vs ephemeral.** Evidence with audit value lives on beads.
   Operational chatter lives on wisps and burns.
5. **Dependencies schedule; links explain.** `blocks`/parent edges shape what
   `bd ready` returns. Graph links carry provenance and conversation.
6. **The orchestrator routes that work happens, never what is said.** It
   spawns, wakes, creates shells and gates, observes lifecycle. Content flows
   bead-to-bead between actors.

---

## Metadata schema

```jsonc
{
  // Orchestrator (or planner node) at node creation
  "scope":           "<glob list — files this node owns exclusively>",
  "base_ref":        "<branch name>",
  "base_sha":        "<sha at planning time>",
  "execution_kind":  "git|artifact|comment|external",
  "artifacts_dir":   "<abs path>/.orchestration/run-<id>/artifacts/",
  "model":           "<model id>",               // optional; exact model required
  "complexity_tier": "low|medium|high|xhigh",    // preferred routing signal
  "tool_hints":      ["context7","serena"],      // optional
  "skill_hints":     ["write-docs"],             // optional; specialist loads or
                                                  // passes to children

  // Claiming agent after claim
  "branch":          "<working branch name>",     // git kind
  "worktree":        "<abs worktree path>",
  "execution_dispatch": "directed|generic",
  "execution_agent": "<agent type>",

  // Claiming agent at delivery
  "push":            "<sha>",                     // git kind
  "output_ref":      "<abs path under artifacts_dir, or comment/audit ref>",
                                                  // artifact|comment kinds

  // pr-shepherd after landing
  "merge_sha":       "<sha>",
  "pr":              "<number>",

  // Hook-managed counters (reset atomically at bounce)
  "stop_attempts":   0,
  "review_round":    0
}
```

Removed from the previous draft: `next_role`, `next_assignee` (the `agent:*`
label is the routing signal), `review_dimensions` (labels, below).

Rules:

- `model`/`complexity_tier` are read by the orchestrator **before spawning**,
  never by the agent after spawn -- an agent cannot reconfigure its own model.
- `output_ref` MUST NOT have `metadata.worktree` as a prefix and MUST resolve
  under `artifacts_dir` (artifact kind) or reference a bead comment/audit
  event (comment kind). Worktrees are disposable; the git object store and
  `artifacts_dir` survive them. No metadata key other than `worktree` may
  reference a path inside a worktree.
- `git` kind has no `output_ref`; the deliverable is `branch` + `push`.

## Labels

| Label | Written by | Meaning |
|---|---|---|
| `agent:<role>` | orchestrator, or the finishing actor | What the orchestrator spawns next |
| `orc-node` | orchestrator | Bead is a run node |
| `needs-review:<dim>` | planner, or any T1 actor (add only) | Review lens required (`code`, `security`, `qa`, `data`, …) |
| `reviewed:<dim>` | the approving reviewer (swap) | Dimension approved this round |

- Any T1 actor may **add** `needs-review:*` (mid-run dimension escalation).
- Only the approving reviewer swaps `needs-review:<dim>` → `reviewed:<dim>`,
  in the same act as closing its review wisp.
- Only the orchestrator reverses the swap (scope-retrigger, below).
- Labels declare; the dep graph enforces. Nothing merges because a label
  says so.

## States

```
pending → working → reported → in_review → approved → merged | dismissed
                  ↘ failed (from any state)   waiting_human (gate)
                    changes_requested (reviewer verdict)
```

`BLOCKED` is a wisp, not a state. Blocked actors checkpoint and exit or keep
working; they never idle live waiting for another agent.

---

## Actor taxonomy

| Tier | Actors | Bead relationship | Contract |
|---|---|---|---|
| T0 | orchestrator (main session) | Never claims -- deny hook | Spawner + observer; all residual authority (create, close, dismiss, unclaim, deps, gates, shells, BRIEF) |
| T1 | domain-specialist, workflow-reviewer, workflow-advisor, workflow-researcher | One durable claim at a time | Full: checklist + authority + bounce |
| T2 | pr-shepherd, ledger-scribe | Many beads over time; lease wisps | Per-transaction authority; zero claims held at exit |
| T3 | builder, parallel-builder, pr-reviewer, external-repo-worker, speckit-implement-task, journey-scribe, journey-validator | Conditional | Contract binds iff a claim is held; silent otherwise |
| T4 | Explore, Plan, guards, scouts, everything else | Never | None -- no rules file, no hook |

Claim rules:

- **One durable-bead claim per actor at any moment** (node or merge bead).
  Wisp claims are additional and unbounded.
- **Zero claims of any kind held at exit** -- wisps included. A dead actor's
  claim (bead or wisp) enters dead-claim recovery.
- Claim-holders are spawned only by T0. Children never claim.
- The pr-shepherd's landing contract already conforms: claim one merge bead,
  probe or land, release. The merge slot serializes landings beneath it.

Fleet changes: `domain-specialist` added; `workflow-coder`,
`workflow-worker`, `workflow-pull-worker`, `integration-gatekeeper` deleted.
Pull activation folds into the surviving definitions; in-run integration
merges become PRs against the integration base, landed by the pr-shepherd.

---

## Rules engine

Each contract-holding agent package ships a declarative rules file next to
its agent definition. One shared evaluator script runs them all.

```yaml
agent: domain-specialist
kind: git                      # rules keyed by execution_kind where they differ
completion:
  - check: branch
    require: metadata.branch
  - check: push
    require: metadata.push
  - check: handoff
    require: label ~ "^agent:"
  - check: reported
    require: comment.verb in [REPORTED]
authority:
  deny_states: [closed, approved, merged, dismissed]
  deny_metadata: [merge_sha, pr]
escape:
  state: failed
  require: comment.verb in [FAILED, BLOCKED]   # unconditional exit
pause:
  - open escalation wisp linked to the claimed node  # valid exit while blocked
```

- Predicate vocabulary stays tiny: metadata-key-exists, label-matches,
  comment-verb-exists, state-in-set, wisp-open/closed. A check that needs
  conditionals or cross-bead lookups is a script, not a rule.
- The prose contract block in each agent definition is **generated from the
  rules file at compile time** (build-native-plugins). The rules file is the
  single source of truth; definitions carry a generated "Your bead contract"
  section.
- An agent package with no rules file gets no hook. T4 by omission.

### Enforcement hooks

| Hook | Attachment | Job |
|---|---|---|
| Per-agent SubagentStop | Claude: agent frontmatter `hooks:`; Codex: matcher on `agent_type` | Evaluate the rules file against the claimed bead; block exit on failure |
| Universal SubagentStart | Matcher-less, both runtimes | Inject one paragraph: claiming a bead binds the generic contract |
| Universal SubagentStop | Matcher-less, both runtimes | One `bd` query by derived actor name: no claim → silent allow; claim + no rules file → generic fallback checklist (report comment + valid terminal state + claim released or escalated) |
| Orchestrator claim-deny | PreToolUse on `bd … --claim`, gated on a run marker set by the orchestrate skill | T0 never claims; deny states the prohibition only |

Deny output is structured JSON, failure-specific, diagnosis-only -- which
check failed and what the bead shows. Remediation lives in the agent's own
contract, never in the deny message.

```json
{"decision":"block","reason":"{\"bead\":\"orc-ab3\",\"agent\":\"domain-specialist\",
 \"failed_checks\":[{\"check\":\"push\",\"detail\":\"metadata.push missing\"}],
 \"violations\":[]}"}
```

Verified hook semantics: both runtimes support SubagentStop block-and-continue
(exit 2 or `decision:"block"`; Codex requires JSON stdout and spills >~2500
tokens to a temp file). Codex provides `stop_hook_active` for re-entrancy;
Claude does not -- the Claude hook counts `stop_attempts` on the bead.

### Bounce-back

At `stop_attempts` = 3 the hook stops fighting:

1. Force-allow the exit.
2. Stamp a structured BOUNCE comment: accumulated failed checks from all
   attempts (durable -- the orchestrator's investigation evidence).
3. Unassign the bead; non-terminal state.
4. Reset `stop_attempts` and `review_round` in the same act -- a bounced bead
   is always clean while unassigned.

The orchestrator reads BOUNCE and decides: respawn with fixes, escalate tier,
or raise a human gate. `review_round` = 3 is the same pattern: the verdict
lands, but the orchestrator arbitrates instead of spawning round 4.

Codex PreToolUse does not intercept every shell path; hook enforcement there
is defense-in-depth. The SubagentStop checklist is the backstop on both
runtimes.

---

## Wisps

Wisp types are TTL classes for compaction of **closed** wisps
(beads source, `internal/types/types.go`): `heartbeat`/`ping` 6h ·
`patrol`/`gc_report` 24h · `recovery`/`error`/`escalation` 7d. GC never
deletes open wisps, but `bd mol wisp gc` flags open wisps untouched for 24h
as abandoned -- freshness is a liveness signal.

| Wisp | bd type | Created by | Burned |
|---|---|---|---|
| `[wisp:review] <node>: <dim>` | escalation | orchestrator (shell) | after merge bead closes |
| `[wisp:escalation] <node>: <question>` | escalation | blocked/asking actor | node close |
| `[wisp:worklog] <node>` | gc_report | claiming actor | node close |
| `[wisp:ledger] <event>` | gc_report | any actor | scribe drain |
| `[wisp:patrol] sheepdog <repo>` | patrol | starting shepherd | shepherd generation end |
| CI probe chatter | ping/heartbeat | shepherd | TTL |
| Dead-claim recovery | recovery | recovering actor | TTL |

### Worktree reclamation (wipe-on-merge)

When a git-kind node's worktree is created, the creator stamps a
`[wisp:recovery] wipe-worktree <abs-path>` wisp and adds
`bd dep add <wipe-wisp> <merge-bead>` so the wisp is **blocked by the merge
bead**. When the merge bead closes (merged OR dismissed), the wisp unblocks;
the next patrol/wake (pr-shepherd or orchestrator) runs
`worktree-sweep.sh`, which uses `wt list` + `wt remove`, and closes the wisp.
Raw `git worktree` lifecycle commands and harness-created worktrees are
prohibited. This makes worktree cleanup
crash-safe: an abandoned run leaves its wipe wisps behind for the next patrol
to reclaim, so no worktree is silently orphaned. Verified on bd 1.1.0 (wisp
`blocks`-dep on a durable bead unblocks on close).

### Worktree resource scaling (heavy build trees -- Rust, etc.)

Per-worktree build output does not scale: N parallel Rust worktrees each grow
a multi-GB `target/`, and the run can fill the disk (bead
`astro-plan-ki35`). Four mechanisms apply together:

1. **Repository-scoped build target.** The global Worktrunk `pre-start` hook
   materializes an ignored, marker-owned `.cargo/config.toml` in each Rust
   checkout. Worktrunk renders `{{ primary_worktree_path }}` and the pre-start
   command persists `<primary_worktree_path>/target` as the absolute
   `build.target-dir`, so the primary checkout and every linked worktree
   converge without mixing unrelated repositories. The hook refuses to
   overwrite an existing Cargo config; that repository must configure the
   target in its project hook or tracked config. A hook-only
   `CARGO_TARGET_DIR` export is insufficient because later build shells do not
   inherit it.
   Project hooks own analogous tool-specific output settings when the tool has
   no safe global static configuration.
2. **Compiler cache.** `RUSTC_WRAPPER=sccache` (local or remote) dedupes
   compilation units across worktrees and runs; complements the shared target.
3. **Warm worktree-local state by copy-on-write.** A repository may allowlist
   safe ignored dependency/build trees in `.worktreeinclude`; global
   `post-start` runs `wt step copy-ignored --require-include`. Python virtual
   environments and mutable runtime state stay worktree-local.
4. **Disk backpressure (the governor).** The orchestrator treats disk as a
   bounded resource: before spawning the Nth heavy-build worktree it checks
   free space against the repository target plus a per-worktree estimate
   (metadata `build_footprint`) and caps concurrency to `free / footprint`.
   A run must never wedge the machine by over-spawning; log what was deferred.

Rules:

- Wisps carry questions, decisions, logs, chatter -- never work assignments.
  Work for another actor is a `discovered-from` bead.
- Nothing the rules engine checks may live on a wisp, except wisp-open/closed
  itself.
- Content worth more than 7 days is not wisp content: `bd promote` it or
  write it durable.
- Burn order: never burn a wisp that a dep edge still points at. Review wisps
  burn only after their merge bead closes.
- The sheepdog is the shepherd's per-repo singleton lease: a starting
  shepherd claims it or exits; the shepherd touches it every patrol cycle;
  a 24h-stale sheepdog is the dead-shepherd signal.
- CHECKPOINT comments go to the node's worklog wisp, not the node. A
  re-claimed actor reads node + worklog thread. Durable-worthy log content is
  flushed into the node's closing comment before report.

## Graph links

| Link | Use |
|---|---|
| `replies-to` | Conversation threads on wisps (`bd show <id> --thread`). CLI dep-type support unverified -- implementation confirms; fallback `relates-to` |
| `relates-to` | Node ↔ wisp tether; node ↔ domain bead; cross-node hints |
| `discovered-from` | Follow-up work found mid-node; fix beads from the shepherd |
| `caused-by` | Bounce investigations, recovery beads → the node that failed |
| `supersedes` | Re-planned nodes (old node auto-closes with forward pointer) |
| `duplicates` | Orchestrator dedup (auto-close semantics) |

Discovery is link-first: no metadata keys pointing at wisps. When a wisp
burns, its links die with it.

---

## Review flow

1. Planner stamps `needs-review:<dim>` labels at node creation. Default:
   `needs-review:code`. Any T1 actor may add dimensions mid-run.
2. At `reported`, the orchestrator -- atomically, before spawning any
   reviewer -- creates one review-wisp shell per `needs-review:*` label,
   links each `replies-to` the node, and adds
   `bd dep add <merge-bead> <review-wisp>`. Shell creation is T0's because
   the full blocker set must exist before the first reviewer can close;
   reviewer-created wisps race (approve-before-other-dimension-exists).
3. Each reviewer is spawned `CLAIM <review-wisp-id>`, fresh per node. It
   follows links to the node and PR, fills the wisp with FIX material and
   working notes, writes a verdict line on the node
   (`REVIEW dim=security round=2 verdict=changes`), and submits a GitHub
   review -- always: `--request-changes` with the FIX list as body, or
   `--approve`. The PR carries review continuity outside beads.
4. On approve: close the wisp + swap the label, one act. On changes: the wisp
   stays open carrying the FIX material.
5. **Aggregation is the dep graph.** The merge bead is ready exactly when the
   last review wisp closes. The reviewer whose close unblocks it runs
   `gh pr ready` (idempotent; races are benign). No actor counts dimensions.
6. **Fix rounds are barriered and batched.** The builder wakes only when every
   dimension's round verdict is in; one fix series addresses the union of all
   open wisps' items. Re-review covers only still-open dimensions.
7. **Scope-retrigger.** A fix diff intersecting an approved dimension's
   trigger scope: orchestrator swaps `reviewed:<dim>` back to
   `needs-review:<dim>` and recreates the shell. Repos with
   dismiss-stale-approvals branch protection retrigger all dimensions
   (bead state mirrors PR state).
8. Reviewers resume only within a node's fix rounds (round 2 must know what
   round 1 demanded). Never across nodes -- verdicts want cold eyes.

Reviewer PR authority: `gh pr review`, `gh pr ready`. Nothing else -- no push,
no merge, no edit.

## Landing (pr-shepherd only)

There are no direct merges and no in-run merge agent. Node branches PR into
the run's integration base; the integration branch PRs into main; the
shepherd's landing contract already handles stacked bases (`pr-base` vs
`landing-base`). One landing path, one merge slot per repo, uniform draft
flow.

- **Any agent** that opens a PR first creates the merge bead (open,
  unassigned, `agent:integrator`) and adds `bd dep add <work> <merge-bead>`;
  the PR body carries `Merge-Bead:`. This is the one bead-creation carve-out
  for T1/T3 actors, plus the accompanying dep edge.
- PRs are created **draft**. The shepherd ignores drafts (existing rule) -- so
  draft = invisible to landing until a reviewer promotes it via `gh pr ready`.
- The shepherd manages PR state and audit only: undrafted-and-unblocked →
  probe → slot → merge → stamp `merge_sha`/`pr` → close as merged. It never
  pushes commits, edits content, or resolves conflicts. Every content problem
  bounces: fix bead (`discovered-from` the merge bead), merge bead parked
  behind it, claim released.
- Fix beads are plain beads by convention. The orchestrator **routes** them
  to a warm specialist or fresh spawn; it never claims them itself.
- One shepherd per repo, named `pr-shepherd-<repo>`, singleton via sheepdog.

## Gates

| Gate | Use | Ticker |
|---|---|---|
| `human` | ASK from any actor: escalation wisp carries the question; orchestrator sets `waiting_human` + `bd gate create --type=human --blocks <node>` | human/orchestrator resolves |
| `timer` | Scribe drain cycle; re-armed by the scribe after each drain | `bd gate check` |
| `gh:run` | Shepherd parks merge-blocked-on-CI behind the run id | shepherd patrol: `bd gate check --type=gh` |
| `gh:pr` | Work beads awaiting an external PR. NEVER blocking a merge bead (deadlock) | shepherd patrol |

Gates resolve only when `bd gate check` runs: the shepherd ticks gh gates
every patrol; the orchestrator runs `bd gate check` at every wake.

---

## Communication patterns

| Exchange | Mechanism |
|---|---|
| T0 → actor task | Bead (BRIEF comment + metadata), spawn = `CLAIM <id>` |
| Actor → T0 outcome | Bead state + REPORTED/BOUNCE/FAILED comment |
| Coder ↔ advisor | Escalation wisp; advisor claims the wisp, answers on it; one-line summary lands on the node |
| Specialist ↔ specialist | Escalation wisp linked to both nodes/domain beads. Content peer-to-peer; T0 is the doorbell only. The answering side weaves the reply into its next natural boundary (stop, claim, checkpoint) -- never a live interrupt |
| Specialist → researcher (bounded question) | Escalation wisp; researcher claims and answers on it |
| Anyone → researcher (artifact-producing) | `discovered-from` bead; T0 triages and spawns; output is durable (`output_ref`) |
| Anyone → ledger | `[wisp:ledger]` wisp, fire-and-forget; scribe drains in batch on its timer gate; final drain at run end by T0 |
| Reviewer → builder fixes | Review wisp (material) + node verdict line + GitHub review |
| Anyone → human | ASK: escalation wisp + human gate |

No agent ever blocks live on another agent. Waiting = checkpoint + exit
(or bounded poll on runtimes without resume).

## Wake mechanics

Capability probe at run start: `SendMessage` exists only with
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.

| Capability | Wake path |
|---|---|
| Claude + flag | Suspend-and-resume: actor exits; T0 `SendMessage`s the stored agent id; full context restored |
| Claude without flag, Codex | Bounded poll (60s interval, 15 to 30 min timeout) then checkpoint-exit; respawn reads node + worklog thread |

- Any wake may silently become a respawn: handles die on compaction and
  overnight gaps. T0 tries SendMessage; on a dead handle it respawns at the
  bead under the same actor name. The bead is the contract; SendMessage is an
  optimization.
- Resume freshness: prefer respawn over resume after ~2 rounds on the same
  node or after the agent has auto-compacted (a compacted resume replays a
  summary of a summary). `review_round` is the signal.
- T0 tracks `node → (actor name, agent id)` in run memory only. Lost state =
  respawn path; no bead fields for agent ids.

The protocol layer is runtime-neutral; the warm tier (persistent specialists,
FIX-round resume) is Claude-with-flag only. Codex runs degrade to
fresh-per-node actors reading node + worklog. Codex subagent APIs are
officially undocumented; revisit when they stabilize.

---

## Domain specialists

One agent definition, parameterized at spawn -- never per-trade definitions.

- **Identity:** a domain bead (child of the run epic) carrying the domain
  BRIEF; nodes link `relates-to` it. Actor name `<role>-<domain>` (or
  `<role>-<epic>-<domain>` when epics collide), stable across resumes.
- **Serial single-claim:** claim node → work → report → release → next domain
  node. Claim released at `reported`; fix rounds re-claim, and a FIX wake
  queues behind the current claim -- the specialist finishes its working phase
  first. Never a second durable claim; children must be collected before
  the node reports.
- **Delegation-first:** the specialist's window is for domain knowledge;
  implementation bulk goes to children. Self-code small deltas and FIX rounds;
  delegate bulk edits, test-fix loops, and wide reading.
- **Children:** prompt-briefed and one-shot. They edit only inside the
  specialist's prepared Worktrunk checkout after the specialist binds each
  returned child ID to its path/actor/lease. They never claim, touch
  Beads/PRs/pushes, or manage worktrees. None survives its node.
- **Parallelism:** more simultaneous nodes in one domain than a serial
  specialist can pipeline → T0 spawns `<role>-<domain>-2`. Never
  sub-specialists: only T0 creates claim-holders; a domain that seems to need
  sub-specialists is the signal to split the domain. Every claim-holder
  receives a distinct Worktrunk checkout.
- **Effort variants:** Agent spawn calls carry `model` but not effort. The
  package compiles `domain-specialist-{low,medium,xhigh}` from one source
  (effort frontmatter is the only difference; one shared rules file). The base
  `domain-specialist` is the `high` tier; `-xhigh` also pins `effort: high`,
  because above `high` measured effort ladders show no capability gain and a
  tool-use regression. Codex variants set `model_reasoning_effort`. T0's tier
  table maps `complexity_tier` → (variant, model).

### Standard profiles

| Profile | Domain bead brief | skill_hints | Typical tier |
|---|---|---|---|
| Code | subsystem scope, conventions, integration points | per stack | medium--high |
| Docs | doc tree, audience, genre rules | `write-docs` | low--medium |
| Security (review lens) | -- dimension label, not a specialist | `speckit-security-review-branch` on the reviewer | high |
| Research | question space, sources, output format | `web-fetch`, `deep-research` | medium |
| Infra/CI | pipeline scope, environments | stack-specific | medium--high |
| QA (review lens) | -- dimension label | journey/QA skills on the reviewer | medium |

Template for a new profile: domain bead description (scope, conventions,
standing constraints) + `skill_hints` + default `complexity_tier` + review
dimensions its nodes default to. A profile earns a new agent *definition*
only when it needs a different contract -- different rules-file shape or tool
surface (that test is why `workflow-researcher` exists and `doc-writer` does
not).

## Planning and model tiers

Planning is a node, not an orchestrator duty. A `plan` node at high tier
claims the spec, produces the node DAG + domain beads + scopes + label
stamps as its deliverable (execution_kind=artifact; carve-out: the planner
may create node beads under the epic), receives a plan review dimension, and
exits. Mid-run re-planning is a new planner node; the router never redesigns
the DAG.

| Role | Model / effort |
|---|---|
| Orchestrator (routing) | sonnet, effort low |
| Planner node | opus/fable-class, effort high |
| Domain specialist | per tier table from `complexity_tier` |
| Implementation children | haiku high / sonnet low |
| Reviewers | per dimension (security high, code medium) |
| Shepherd, scribe | sonnet low |

## Spawn topology

- Depth 1: claim-holders, spawned only by T0.
- Depth 2: implementation children (write-capable spawning ends here).
- Depth 3: read-only scouts. Nothing spawns at depth 3.
- Enforcement is brief-level (no per-depth hook signal exists); the
  claim⟺contract net catches the case that matters.

## Naming

| Thing | Convention | Example |
|---|---|---|
| Domain specialist | `<role>-<domain>[-n]` | `builder-frontend`, `builder-api-2` |
| Node-scoped actor | `<role>-<node-bead>` | `reviewer-code-orc-ab3` |
| Advisor | `advisor-<wisp-id>` | `advisor-orc-w12` |
| Shepherd | `pr-shepherd-<repo>` | `pr-shepherd-agentic-packages` |
| Children | `<parent>.<k>` | `builder-frontend.3` |
| Wisps | `[wisp:<type>] <subject>` | `[wisp:review] orc-ab3: security` |

Name the domain, not the task (the name must hold on resume #8). Node-scoped
names embed the bead id so the universal Stop hook derives the claim from the
assignee. T0 has no name -- it is the session; its per-run identity is the
epic bead.

---

## Acceptance criteria

- [ ] Spawn prompts for every role are `CLAIM <bead-or-wisp-id>` (or
      `CLAIM queue:<q>`); no ASSIGN field survives in any prompt template.
- [ ] Rules files exist for all T1/T2/T3 contract-holders; the evaluator
      passes a conformance suite covering every predicate; agent definitions
      carry compile-generated contract blocks that match their rules file.
- [ ] Per-agent SubagentStop blocks an incomplete builder exit on both runtimes
      and force-allows with BOUNCE + unassign + counter reset at attempt 3.
- [ ] Universal Start/Stop net: an unlisted agent that claims a bead gets the
      generic contract; one that claims nothing is untouched.
- [ ] Orchestrator claim-deny fires only in sessions with the run marker.
- [ ] Review flow end-to-end: labels → shells → dep-blocked merge bead →
      last-close unblocks → `gh pr ready` -- with zero dimension-counting by
      any actor.
- [ ] Draft-PR flow: shepherd never sees a draft; reviewer undraft is the
      only promotion path.
- [ ] Escalation wisp round-trip (builder→advisor) with content never passing
      through T0; wisp burns at node close; no dangling dep edges.
- [ ] Ledger wisps drain in batch on a timer gate; the epic run record is the
      only durable output.
- [ ] Wake: SendMessage resume with the flag; dead-handle respawn recovers
      the same node from bead + worklog with no information loss.
- [ ] `workflow-coder`, `workflow-worker`, `workflow-pull-worker`,
      `integration-gatekeeper` removed; `domain-specialist` variants compiled;
      pr-shepherd amendments (orchestrator-routes-fix-beads, read-only
      content, sheepdog) landed.
- [ ] Wisp/link/label/gate doctrine published in beads package steering;
      speckit adoption (orc-pyq) references it.
