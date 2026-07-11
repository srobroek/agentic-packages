# Change Communication (PR bodies, commit messages, release notes)

The one genre that describes a delta, not a steady state. Past tense about the
change belongs here — and only here.

## PR body

MUST Shape: what changed · why · test plan (close keywords and merge rules: see steering-git-workflow).
MUST Every claim under "what changed" maps to a hunk in the diff.
NOT "Lays the groundwork", "first step towards", "part of a broader effort", roadmap sections.
NOT File-by-file diff restatement — state behavior changes, not file lists.

## Commit messages

MUST Conventional commit; imperative subject naming the behavior change.
NOT Vague subjects: "improve", "enhance", "update", "polish" without the concrete change.

## Changelog

MUST Repos with release-please or changesets: never hand-edit CHANGELOG.md — quality comes from commit subjects and PR titles.
DEFAULT Hand-maintained changelogs: one line per user-visible change; internal refactors only when they change behavior a consumer can observe.
