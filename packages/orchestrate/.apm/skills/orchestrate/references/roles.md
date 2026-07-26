# Roles, models, escalation

Route each role to the **cheapest capable model**; escalate up only on hard
cases. Discover the concrete agents available with `scripts/discover-agents.py`
(the catalog shows each agent's real `model`); the mapping below is the default
starting point, refined by what the catalog actually offers.

| Role | Agent (default → alternatives) | Model / effort | Persistence | Escalation |
|---|---|---|---|---|
| **Orchestrator** | you (lead session) | your session model | whole run | delegate deep planning / disputes |
| **Researcher** | `researcher` (bundled) -> `Explore`, `speckit-research` | **cheap tier** low/med, read-only | per claimed node or wisp | -> mid tier when one synthesis is contradictory |
| **Docs-guard** | `docs-guard` (`agent-quality-guards`) | **cheap tier** medium, read-only | ephemeral | → reviewer when policy or meaning is disputed |
| **Data-metrics-summarizer** | `data-metrics-summarizer` (`agent-quality-guards`) | **cheap tier** medium, read-only | ephemeral | → researcher when interpretation is required |
| **Lint-guard** | `lint-guard` (`agent-quality-guards`) | **cheap tier** high, read-only | ephemeral | → reviewer when rule intent is disputed |
| **Maintenance-metrics-reader** | `maintenance-metrics-reader` (`agent-quality-guards`) | **cheap tier** low, read-only | ephemeral | → researcher when a root cause is ambiguous |
| **Reviewer-mechanics** | `reviewer-mechanics` (`agent-quality-guards`) | **cheap tier** low, read-only | ephemeral | → reviewer on deeper correctness questions |
| **Domain-specialist** | `domain-specialist` (bundled) | **mid tier** medium | per node, kept alive across fix rounds | do **not** upgrade the domain-specialist -- on a reasoning block it raises `BLOCKED` |
| **Reviewer** | `reviewer` (bundled) → `code-reviewer`/`pr-reviewer` | **mid tier** medium, read-only | kept alive per node (re-reviews deltas) | → top tier for complex or security-critical diffs |
| **Advisor** | `advisor` (bundled) → `adversarial-challenger` | **top tier** high, read-only | ephemeral, **spawned by the orchestrator** | already top tier |
| **Shepherd** | `shepherd` (bundled) | **mid tier** high | persistent for one run | -> top tier only for an evidence dispute it cannot resolve |
| **Scribe** | `scribe` (bundled) | **cheap tier** low, read-only | one claimed query wisp | escalate to mid if issue interpretation is ambiguous |
| **Tiebreaker** | `general-purpose` (fresh) | **top tier** high, read-only | ephemeral, gated | → xhigh only if genuinely complex |

Claim-holder roles bundled here are domain-specialist, researcher, reviewer,
advisor, shepherd, and scribe. A node with `execution_kind=artifact` must go to a
writable role -- in practice `domain-specialist` -- because the writer hook denies
the artifact write from a read-only role, and the node cannot recover by itself.
Route a read-only role only when the node's deliverable is its reported result. The in-run shepherd uses landing safeguards
from the `pr-shepherd` dependency; the dependency's standalone agent remains
the repository-global queue drainer. Quality-guard roles come from
`agent-quality-guards`; remaining routes are built-ins. The package does not assume
`code-reviewer`/`adversarial-challenger` exist; those are optional upgrades
when the catalog has them.

"Persistent" means the role is always available for the run, not that it is one
never-restarted process -- recycle the Shepherd to shed context (see
`references/lifecycle.md`). The orchestrator never executes work directly; see
SKILL.md Core rules.

## Capabilities & access -- what each role may do

| Role | Writes | Spawns | Runs in | Notes |
|---|---|---|---|---|
| Orchestrator | no code | **claim-holders; sole dismisser** | lead session | writes BRIEFs, prepares leases, creates wisp shells, and sends content-free wakes |
| Docs-guard | nothing (read-only) | nothing | own Worktrunk checkout when using tools | flags low-signal doc issues before merge review |
| Data-metrics-summarizer | nothing (read-only) | nothing | artifact-only, or own Worktrunk checkout when reading the repo | compacts logs/telemetry into bounded, prompt-driven summaries |
| Lint-guard | nothing (read-only) | nothing | own Worktrunk checkout when using tools | triages lint artifacts and classifies likely false positives |
| Maintenance-metrics-reader | nothing (read-only) | nothing | own Worktrunk checkout when reading repo metadata or trees | emits `MAINTENANCE SNAPSHOT <scope> status=PASS\|WARN\|FAIL` with top signals and evidence |
| Reviewer-mechanics | nothing (read-only) | nothing | own Worktrunk checkout | emits `MECH-REVIEW <scope> verdict=PASS\|CHANGES` with deterministic `file:line` findings |
| Domain-specialist | its `scope` only | bound throwaway children | bound Worktrunk checkout | children share its path but never claim, commit, push, or manage worktrees; on block → `BLOCKED kind:design\|debug` |
| Reviewer | nothing (read-only) | nothing | separate Worktrunk checkout created from writer branch | logs `review` verdict as audit record + bead comment |
| Advisor | nothing (read-only) | nothing | separate Worktrunk checkout | claims one escalation wisp and answers it directly |
| Shepherd | PR state and merge records (remote) | nothing | dedicated integration Worktrunk checkout per repository | never edits or pushes content; bounces through fix beads |
| Scribe | report artifacts only | nothing | separate Worktrunk checkout | claims one query wisp; never mutates work beads |
| Researcher | artifact output only | nothing | separate Worktrunk checkout | claims a node or escalation wisp and reports there |
| Tiebreaker | nothing (read-only) | nothing | separate Worktrunk checkout | binding `ADVICE`, logged |

## Specialist dispatch

| Input | Route | Boundary |
|---|---|---|
| Documentation-only node or documentation lint report | `docs-guard` | syntax, links, structure, and reported documentation findings only |
| Existing lint report with many or stale findings | `lint-guard` | validate and normalize the report; never replace the project linter |
| Large scoped log, metric, CSV, JSON, or JSONL artifact | `data-metrics-summarizer` | compact the supplied evidence; never diagnose or recommend |
| Repository hygiene scan (stale branches, worktrees, locks) | `maintenance-metrics-reader` | report signals with evidence; never delete or repair |
| Scoped diff smoke-check before review handoff | `reviewer-mechanics` | mechanical findings only; never judge design or merge strategy |

These specialists preprocess bounded evidence. A semantic correctness decision
still belongs to `reviewer`, a researcher, or an advisor.

**Only the orchestrator spawns or dismisses claim-holders.** A
domain-specialist may nest bounded throwaway implementation children in its
own checkout. It binds every child runtime to the same Worktrunk
actor and lease, and collects the child before reporting. No other worker
nests.

## Researcher fan-out / fan-in

The orchestrator owns research decomposition and never reads raw sources
itself. Every gatherer or synthesizer gets a complete research bead and is
activated only by its claim verb.

- **Narrow question:** one Researcher (`Explore`, cheap tier), returns a terse digest.
- **Broad research -- fan-out then fan-in:**
  1. **Fan-out:** create one scoped research node per source or sub-question.
     Each gatherer claims its node and writes cited artifact evidence.
  2. **Fan-in:** create a synthesis node depending on every gatherer. The
     synthesizer reads their cited artifacts, dedupes conflicts, and reports
     one synthesis.
  3. The orchestrator keeps only the synthesis; gatherers and synthesizer are
     dismissed. Escalate the synthesizer a tier only if the material is
     genuinely contradictory or high-stakes.

Gatherers are read-only and spawn nothing; the fan-out width is the orchestrator's
call (bound it to the sources that matter -- log what was skipped).

## Escalation ladder

1. `BLOCKED kind:design` -> create or reuse an escalation wisp; an advisor
   claims and answers it directly.
2. `BLOCKED kind:debug` -> route the same wisp to a read-only debugger; its
   ADVICE stays on the wisp and is promoted to the node.
3. A complex or security-sensitive review -> create the review wisp with the
   higher tier before activation.
4. A specialist/reviewer deadlock or landing dispute -> a fresh read-only
   tiebreaker claims an escalation wisp; its promoted ADVICE is binding.
5. Missing product intent -> ASK wisp plus human gate.

Never silently upgrade a whole role to the top tier to paper over a one-off hard case;
escalate the specific instance.
