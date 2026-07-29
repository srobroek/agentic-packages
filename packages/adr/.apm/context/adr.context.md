# Architecture decision records

A decision is registered when it is made, not when the work finishes. The beads
`decision` bead is the live record; the MADR file under `docs/adr/` is what
discharges it. Reconstructing decisions at closeout loses the alternatives that were
considered and the reason the losing option lost, which is the part worth keeping.

WHEN A CHOICE EARNS A RECORD
MUST Record a choice that is hard to reverse, constrains later work, or crosses a
  package, contract, or agent boundary.
MUST Record the choice that was REJECTED and why, not only the one taken. An ADR
  without a rejected alternative is a description, not a decision.
NOT Record a choice a later commit can undo at no cost, a naming preference, or a
  step already fixed by an existing record.
DEFAULT In doubt, write the bead: promotion is cheap, recovery is not.

REGISTER AS YOU GO
MUST Create the `decision` bead BEFORE the choice affects a second bead, agent, or
  package. That bead carries `decision_key`, `decision_owner`, `design` (rationale,
  evidence, unknowns, bounds, alternatives), `acceptance`, and
  `decision_disposition`. See the beads carrier doctrine for the full schema.
MUST Link affected work with `relates-to` and evidence-supplying work with
  `validates`. Both are non-blocking; `blocks` is never correct for accepted policy.
MUST Write the ADR file when the disposition reaches `accepted`, cite its path on
  the bead, then READ THE CITATION BACK before closing. The carrier doctrine makes
  the bead authoritative and a file evidence only, so an uncited file is not a
  decision -- and a bead closed as `accepted` whose file was later superseded is a
  split the doctrine's `decision_key` machinery cannot see.
DEFAULT A decision that stays `proposed` keeps its bead open and needs no file yet.

THE FILE
| Property | Value |
|---|---|
| Format | MADR 4.0.0 |
| Path | `docs/adr/NNNN-kebab-title.md` |
| Numbering | sequential, never reused |
| Gate | `adrs doctor`, exit 1 under `--warnings-as-errors` |

MUST Create records with `adrs new --no-edit --format madr "<title>"`. Without
  `--no-edit` the command spawns `$EDITOR` and blocks; `EDITOR=true` does not help.
MUST Initialise with `adrs init docs/adr`. The tool defaults to `doc/adr`, and
  writing `.adr-dir` by hand does NOT create the directory -- `adrs new` then fails
  with "ADR directory not found", and a later bare `adrs init` silently rewrites
  `.adr-dir` back to `doc/adr`. Verified against 0.10.1.
NOT Edit an accepted record to change its decision. Write a new one and mark the old
  `superseded`, naming the successor. An ADR is a point-in-time record; the roadmap
  is the forward-looking document.
DEFAULT Absent `adrs`, format and path still apply and the gate is skipped.

WHAT BELONGS IN EACH SECTION
| Section | Holds | Fails when |
|---|---|---|
| Context and Problem Statement | The forces that made a choice necessary | It restates the decision |
| Decision Drivers | The criteria the options were judged against | The criteria appear only after the winner |
| Considered Options | Every option genuinely weighed | A straw option is listed to justify the winner |
| Decision Outcome | The choice, in one sentence, and the driver that settled it | It hedges |
| Consequences | What becomes harder, not only easier | Only benefits are listed |
| Confirmation | How compliance is verified | It names no observable check |

MUST State a consequence that is a cost. No gate checks this, so it is a review
  criterion: `adrs doctor` sees only that sections exist and are not placeholders.

RECORD AUTHORITY
| Record | Scope | Mutability |
|---|---|---|
| `decision` bead | Live, cross-boundary. AUTHORITATIVE per the carrier doctrine | Disposition changes until closed |
| ADR file | The durable evidence a bead cites, project-scoped | Append-only; supersede, never rewrite |
| Work-bead comment | Affects only that bead and its owned scope | Local, stays with the bead |
