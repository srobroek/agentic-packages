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
| **Workflow-reviewer** | `workflow-reviewer` (bundled) → `code-reviewer`/`pr-reviewer` | **mid tier** medium, read-only | kept alive per node (re-reviews deltas) | → top tier for complex or security-critical diffs |
| **Workflow-advisor** | `workflow-advisor` (bundled) → `adversarial-challenger` | **top tier** high, read-only | ephemeral, **spawned by the orchestrator** | already top tier |
| **Integration Gatekeeper** | `integration-gatekeeper` (bundled) | **mid tier** medium | **persistent** | → top tier only if merge reasoning is genuinely gnarly |
| **Ledger Scribe** | `ledger-scribe` (bundled) | **cheap tier** low, read-only | **persistent** | — |
| **Tiebreaker** | `general-purpose` (fresh) | **top tier** high, read-only | ephemeral, gated | → xhigh only if genuinely complex |

All custom roles ship **bundled** with this package (coder, reviewer, advisor,
gatekeeper, scribe); the remaining routes are built-in agents (`Explore`,
`general-purpose`) present everywhere. The package does not assume
`code-reviewer`/`adversarial-challenger` exist; those are optional upgrades
when the catalog has them.

"Persistent" means the role is always available for the run, not that it is one
never-restarted process — recycle the Gatekeeper/Scribe to shed context (see
`references/lifecycle.md`). The orchestrator never executes work directly; see
SKILL.md Core rules.

## Capabilities & access — what each role may do

| Role | Writes | Spawns | Runs in | Notes |
|---|---|---|---|---|
| Orchestrator | no code | **everything; sole dismisser** | lead session | coordination + deterministic scripts only |
| Workflow-coder | its `scope` only | **nothing** | own git worktree | commits + pushes its branch; on block → `BLOCKED kind:design\|debug` to `main` |
| Workflow-reviewer | nothing (read-only) | nothing | reads branch/worktree | logs `review` verdict as audit record + bead comment |
| Workflow-advisor | nothing (read-only) | nothing | reads code | one `ADVICE`, then exits |
| Integration Gatekeeper | integration branch / merges (remote) | nothing | remote-side (`gh`, merge-tree probes) — no worktree | merge + push authority only; never mutates local trees |
| Ledger Scribe | nothing (read-only) | nothing | reads beads db + artifacts | never in the write path |
| Researcher | nothing (read-only) | nothing | reads sources/code | returns a terse findings digest |
| Tiebreaker | nothing (read-only) | nothing | reads the dispute | binding `ADVICE`, logged |

**Only the orchestrator spawns or dismisses agents; no worker nests** — even
where the platform would allow it (flat tree — SKILL.md core rule 5).

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
