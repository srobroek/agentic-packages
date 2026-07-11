# Write Docs

Condensed doc-writing rules. The write-docs skill owns the full genre
references and the slop-lint script; use it when available.

All genres:

MUST State what the artifact does — never effort, intent, process, or journey.
MUST Delete any adjective you cannot back with a number, benchmark, or feature list.
MUST One idea per sentence; lists and tables over prose paragraphs.
NOT Status language: "under construction", "WIP", "coming soon", "currently", "for now", "planned", "being specified".
NOT Slop lexicon: "seamlessly", "robust", "powerful", "comprehensive", "leverage", "blazingly fast", "battle-tested", emoji headings.

Consumer surfaces (README, docs/ — read by users of the artifact):

MUST Write for the released artifact: every sentence verifiable against code at HEAD; no target states or roadmap.
MUST Every example is copy-paste runnable and has a matching executable test under `examples/`.
NOT Internal references: specs/, ADRs, constitutions, tickets, extraction lineage ("extracted from X").
DEFAULT Mention another package only when this artifact imports or requires it at runtime.

Change surfaces (PR bodies, commit messages, release notes):

MUST Describe the delta: what changed · why · test plan; every claim maps to a diff hunk.
NOT "Lays the groundwork", "first step towards", roadmap sections.
NOT Hand-editing CHANGELOG.md in repos where release-please or changesets generate it.

Internal surfaces (specs, ADRs, constitutions, CONTRIBUTING, runbooks):

DEFAULT Internal references allowed — link, do not restate.
MUST Same prose discipline as consumer surfaces; structured status metadata allowed, status narration in body prose is not.
