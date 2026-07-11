# Consumer Docs (README, docs/)

Audience: a user of the released artifact with zero access to internal process.

## Released-artifact test

MUST Every sentence is verifiable against the code at HEAD of the branch being merged.
MUST A sentence that stops making sense once git history, specs, and this conversation vanish gets deleted.
MUST Feature flags: document behavior that is on by default, or document the flag as opt-in configuration — never the roadmap.
NOT Target states, milestones, completion percentages, "phase 2", section names like "Planned API".

## Structure (README skeleton — omit empty sections, never pad)

1. Name + one-line purpose (what it does, for whom)
2. Install
3. Usage — minimal working invocation first
4. Examples — one per major capability
5. Configuration — table: name · type · default · effect
6. License

## Examples

MUST Copy-paste runnable exactly as written against a fresh install.
MUST Each example has a matching executable test under `examples/` in the repo; run it before shipping the doc.
DEFAULT Environment blocks execution (credentials, external service) → state that in the PR body; never silently skip.
NOT Pseudo-code presented as a runnable example.

## Internal references

NOT Links to or mentions of specs/, ADRs, constitutions, .specify/, internal tickets, or agent instructions.
NOT Extraction lineage: "extracted from X", "mirrors Y", "aligned with Z".
DEFAULT Mention another package only when this artifact imports or requires it at runtime — one line naming the dependency and what it provides.

## Rationale

DEFAULT State the choice; add a one-line reason only when the reader needs the constraint to use the artifact.
NOT Filler rationale: "popular", "battle-tested", "industry standard", "modern".
