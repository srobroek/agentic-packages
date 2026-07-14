# User Journeys — Advisory Steering

Applies only in repos that have a journeys directory (contains `FORMAT.md`
and `*/journey.md`; find it via `INDEX.md` or the journeys `README.md`).
That directory's FORMAT.md is normative for every journey artifact.

## The nudge (advisory, never auto-run)

Validation runs are expensive — they drive the real product. Therefore:

- After completing a feature, merging significant behavior changes, or
  fixing a user-visible bug: check the journeys `INDEX.md` for journeys
  whose `surfaces:` the change touches, and **suggest** the appropriate
  skill — `journey-write` for new/changed behavior with no journey,
  `journey-verify-changed` for touched journeys. Name the journey ids and
  why. Do not run them unprompted.
- If a change record you produced (PR body, changelog entry) contradicts a
  journey's expectations, say so — that PR is the intent evidence a future
  amendment will cite.

## Rules that bind every journey interaction

- Journey bodies are current truth; git is the archive. Never append run
  results or history into `journey.md`.
- Three change species — correction (silent body fix), behavior delta
  (body + Δ entry + version bump, intent evidence required), run result
  (runs/ + reporter only). Never mix them.
- Amendments are intent-gated: no citable evidence, no amendment.
- Ids (journey, step, precondition, criterion) are never renumbered or
  reused.
- Consolidation (delta-log flush, run pruning) is human-blessed only —
  propose via `journey-consolidate`, never do it as a side effect.
- Findings always embed the `journey-finding` block so journey↔finding
  linkage survives any tracker or label scheme.

## Skill routing

| Need | Skill |
|---|---|
| Set up / reconfigure the journeys directory | `journey-init` |
| Author, amend, or migrate journeys | `journey-write` |
| Validate journeys end to end | `journey-verify` |
| Validate only what a change touched | `journey-verify-changed` |
| Checkpoint: flush delta logs, prune runs | `journey-consolidate` |
| Fleet validation with bounded fix loop | `journey-campaign` |
