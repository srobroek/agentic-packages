# Beads GitHub Mirror

Rules for repositories where beads mirror out to GitHub issues.

MUST Mirror with `bd github push <ids>`, never by hand-creating the issue —
  the push records the `External:` back-link on the bead, so a hand-made issue
  leaves the two unlinked. `--dry-run` first.
DEFAULT Supply credentials per invocation
  (`GITHUB_TOKEN="$(gh auth token)" GITHUB_REPOSITORY=<owner/repo> bd github
  push ...`) rather than `bd config set github.token`, which persists a PAT to
  disk in the repo's beads config.
MUST Expect mirrored issues to carry bd's OWN label scheme (`priority::medium`,
  `type::task`, `status::in_progress`), derived from bd's structured fields. A
  repo with its own vocabulary (`priority-p2`, `spec:NNN`, component labels)
  will not match, so mirrored issues drop out of every existing triage query
  while looking correctly filed.
NOT Hand-correcting those labels on GitHub — `bd github push` REPLACES the whole
  label set from bd on every sync, so any manual fix is silently undone the next
  time that bead is pushed (verified 2026-07-20: labels applied via `gh api`
  were wiped by the next push, twice). `bd update` has no `--label` flag, so the
  scheme cannot be corrected from the bd side either.
DEFAULT Treat the mismatch as an upstream gap rather than per-issue toil: it
  needs configurable label mapping in bd itself. Until then, either accept the
  `::` scheme as the mirror's vocabulary and build triage queries that tolerate
  both, or keep mirrored issues out of label-driven workflows.
