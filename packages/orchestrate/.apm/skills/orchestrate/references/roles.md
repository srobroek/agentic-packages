# Roles, models, escalation

Route each role to the **cheapest capable model**; escalate up only on hard
cases. Discover the concrete agents available with `scripts/discover-agents.py`
(the catalog shows each agent's real `model`); the mapping below is the default
starting point, refined by what the catalog actually offers.

| Role | Agent (default → alternatives) | Model / effort | Persistence | Escalation |
|---|---|---|---|---|
| **Orchestrator** | you (lead session) | your session model | whole run | delegate deep planning / disputes |
| **Researcher** | `Explore` → `general-purpose`, `speckit-research` | **cheap tier** low/med | ephemeral (reuse for follow-ups) | → mid tier when a single task is synthesis-heavy (see fan-out/fan-in below) |
| **Workflow-coder** | `workflow-coder` (bundled) | **mid tier** medium | per node, kept alive across fix rounds | do **not** upgrade the coder — on a reasoning block it raises `BLOCKED` |
| **Generic pull worker** | `workflow-pull-worker` | cheapest compatible tier | one claimed node per activation | route a hard reasoning block through an advisor; do not upgrade the worker |
| **Specialist** | catalogued agent matching the routing envelope | cheapest compatible tier | per node | fall back to generic pull only when no specialist is selected |
| **Workflow-reviewer** | `workflow-reviewer` (bundled) → `code-reviewer`/`pr-reviewer` | **mid tier** medium, read-only | kept alive per node (re-reviews deltas) | → top tier for complex or security-critical diffs |
| **Evidence reviewer** | catalogued read-only specialist → `general-purpose` | cheapest compatible tier | kept alive per non-git node | → top tier for high-stakes external-state verification |
| **Workflow-advisor** | `workflow-advisor` (bundled) → `adversarial-challenger` | **top tier** high, read-only | ephemeral, **spawned by the orchestrator** | already top tier |
| **Integration Gatekeeper** | `integration-gatekeeper` (bundled) | **mid tier** medium | **persistent** | → top tier only if merge reasoning is genuinely gnarly |
| **Ledger Scribe** | `ledger-scribe` (bundled) | **cheap tier** low, read-only | **persistent** | — |
| **Tiebreaker** | `general-purpose` (fresh) | **top tier** high, read-only | ephemeral, gated | → xhigh only if genuinely complex |

The baseline bundle supplies coder, reviewer, advisor, gatekeeper, and scribe.
Every other route must appear in `scripts/discover-agents.py` output before use.
The package does not assume `code-reviewer`, `adversarial-challenger`, a
specialist, or a pull worker exists; absent routes fall through the precedence
below without weakening compatibility.

"Persistent" means the role is always available for the run, not that it is one
never-restarted process — recycle the Gatekeeper/Scribe to shed context (see
`references/lifecycle.md`). The orchestrator never executes work directly; see
SKILL.md Core rules.

## Dispatch precedence and compatibility

Dispatch is deterministic:

1. **Exact actor assignment.** A non-empty bead `assignee` pins that actor.
   Nobody else may claim it. Explicit selection wins routing preference, not
   the compatibility gate.
2. **Specialised capability.** For an unassigned bead, select the narrowest
   compatible specialist from the discovered catalog. Set the selected actor
   as assignee before waking or spawning it.
3. **Generic pull.** When no specialist is selected, leave the bead unassigned
   and admit it to one compatible `agent:<queue>`. A generic worker atomically
   claims the first ready bead in that queue.

An agent is compatible only when all of these hold:

- its declared task kinds include the bead's `execution_kind`;
- its declared capabilities cover every `execution_capabilities` entry and
  mirrored `cap:*` label;
- its write and network permissions cover the task without exceeding the
  brief;
- it can produce the declared `execution_evidence` within the owned scope.

Unknown capability is incompatible. For multiple specialists, choose the one
with the fewest surplus capabilities, then the cheapest capable tier, then
stable agent name order. If an exact actor is incompatible, hold the bead and
raise `ASK` only when the coordinator cannot correct the route from existing
evidence.

A generic queue is a capability contract, not a suggestion. The coordinator
adds `agent:<queue>` only after proving the bead requirements are a subset of
that queue's declared task kinds and capabilities. The pull worker uses
`bd ready --claim` with that exact queue filter and accepts the returned bead;
listing then choosing is prohibited.

If no compatible route exists, keep the bead unclaimed and record an ambiguity
owner plus revisit trigger. Never turn non-code work into broad coding or grant
wider access to make a route fit.

## Capabilities & access — what each role may do

| Role | Writes | Spawns | Runs in | Notes |
|---|---|---|---|---|
| Orchestrator | no code | **everything; sole dismisser** | lead session | coordination + deterministic scripts only |
| Workflow-coder | its `scope` only | **nothing** | own git worktree | commits + pushes its branch; on block → `BLOCKED kind:design\|debug` to `main` |
| Generic pull worker | claimed node scope only | nothing | worktree for git; artifact/resource scope otherwise | one atomic queue claim per activation; no second node before terminal state |
| Specialist | only the scope and access in its brief | nothing | isolation selected by evidence mode | exact assigned bead; reports the declared evidence |
| Workflow-reviewer | nothing (read-only) | nothing | reads branch/worktree | logs `review` verdict as audit record + bead comment |
| Evidence reviewer | nothing (read-only) | nothing | reads artifact, bead comments, or external state | different actor from worker; validates acceptance criteria and evidence |
| Workflow-advisor | nothing (read-only) | nothing | reads code | one `ADVICE`, then exits |
| Integration Gatekeeper | integration branch / merges (remote) | nothing | remote-side (`gh`, merge-tree probes) — no worktree | merge + push authority only; never mutates local trees |
| Ledger Scribe | nothing (read-only) | nothing | reads beads db + artifacts | never in the write path |
| Researcher | nothing (read-only) | nothing | reads sources/code | returns a terse findings digest |
| Tiebreaker | nothing (read-only) | nothing | reads the dispute | binding `ADVICE`, logged |

**Only the orchestrator spawns or dismisses agents; no worker nests** — even
where the platform would allow it (flat tree — SKILL.md core rule 5).

Tracked-file work may use a workflow-coder, specialised worker, or generic pull
worker. It always runs in an isolated worktree and uses an independent
workflow-reviewer plus the integration gatekeeper, regardless of whether its
task kind is code, docs, or configuration. Artifact, comment, and external-state
work has the same `REPORTED → in_review → approved` sequence, but an Evidence
reviewer validates it and the orchestrator closes the approved bead without
inventing a commit or merge.

## Researcher fan-out / fan-in

The orchestrator owns research decomposition and never reads raw sources itself.

- **Narrow question:** one Researcher (`Explore`, cheap tier), returns a terse digest.
- **Broad research — fan-out then fan-in:**
  1. **Fan-out:** the orchestrator spawns several cheap **cheap-tier gatherers** in
     parallel, each scoped to one source, slice, or sub-question. Each returns a
     terse findings digest (facts + `refs`, not prose) — nothing raw.
  2. **Fan-in:** the orchestrator hands all digests to **one mid-tier synthesizer**
     that dedupes, resolves conflicts, and returns a single synthesis with
     citations.
  3. The orchestrator keeps only the synthesis; gatherers and synthesizer are
     dismissed. Escalate the synthesizer a tier only if the material is
     genuinely contradictory or high-stakes.

Gatherers are read-only and spawn nothing; the fan-out width is the orchestrator's
call (bound it to the sources that matter — log what was skipped).

## Escalation ladder

1. `BLOCKED kind:design` → `workflow-advisor` (top tier, one-shot).
2. `BLOCKED kind:debug` (red verify, stuck diagnosing) → the catalog's
   `debugger` agent if present, else `general-purpose` read-only; it
   investigates independently and returns findings as `ADVICE` via the
   orchestrator.
3. Diff too complex/security-sensitive for a mid-tier reviewer → orchestrator
   re-spawns the reviewer on the top tier (or adds `adversarial-challenger`).
4. Coder⇄reviewer deadlock after bounded fix rounds, or gatekeeper⇄coder conflict
   a rebase can't settle → orchestrator spawns a fresh **Tiebreaker** (top tier,
   clean context, read-only); its `ADVICE` is logged and binding.
5. A decision needs product intent not in the brief → bubble `ASK` to the human.

Never silently upgrade a whole role to the top tier to paper over a one-off hard case;
escalate the specific instance.
