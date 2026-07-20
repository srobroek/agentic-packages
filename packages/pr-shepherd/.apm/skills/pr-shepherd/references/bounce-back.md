# Bounce-back protocol

When a probe finds a problem the shepherd cannot fix (CI failure, merge
conflict, changes requested), park the merge bead behind a fix bead and move
on. The coder closing the fix bead re-readies the merge bead automatically —
no messaging.

## 0. Dedupe + correlation first

Search open fix beads before filing:
`bd list --label agent:coder --status open --json`, compare metadata dedupe
keys:

- CI failure key: failing check name + repo
- conflict key: sorted conflict file set + repo

On a match, do NOT file a duplicate. Instead:
`bd dep add <this-merge-bead> <existing-fix-bead>` so this PR also waits on
it, and comment BOTH beads noting the correlation, e.g. "PR #43 red on same
check as PR #42 — shared cause suspected".

## 1. File the fix bead (always unassigned)

```
bd create "Fix <problem> (PR #N)" \
  --deps discovered-from:<merge-bead> \
  -l agent:coder \
  --metadata '{"pr":N,"branch":"<branch>","failure":"ci|conflict|review",
               "check":"<failing check>","origin_actor":"<actor>",
               "origin_bead":"<work-bead-id>"}' \
  -d "<diagnosis>"
```

The description is the handover — fresh coders get no other context (handover
files are machine-local; PR bodies are not agent context). It must carry:

- the exact error: failing check names + log excerpt
  (`gh run view <run-id> --log-failed`, cap ~30 lines), the conflict file
  list, or the review summary
- a reproduction command: `gh pr checks N`, the failing test invocation, or
  `git merge-tree --write-tree origin/<base> origin/<branch>`
- the warm-context pointer: "Read <origin_bead>'s comments/notes first" — the
  bead trail carries the author's residual context
- unrelated-failure diagnosis: when the same check is red on the base branch
  or on sibling PRs, state "failure appears pre-existing on <base>, not
  introduced by this branch" and label the fix bead with the component when
  identifiable — this stops a fresh coder bisecting the wrong branch

`origin_actor` / `origin_bead`: take them from the merge bead's metadata when
the creator recorded them, else from the merge bead's `created_by` and its
`discovered-from` trail; omit the keys when unknown. Informational only —
they say whose branch/worktree/context this concerns.

Route review-response fixes that the reviewer owns with `-l agent:reviewer`
instead; the label is still a queue, never an assignment.

## 2. Park the merge bead and release

```
bd dep add <merge-bead> <fix-bead>   # merge bead leaves bd ready until fixed
bd comments add <merge-bead> "<what is wrong, what was filed (<fix-bead>), routing>"
bd update <merge-bead> --assignee "" --status open   # release the claim
```

## Routing rules

- Fix beads are ALWAYS created unassigned with a routing label. Never pin
  `--assignee`; never guess whether the origin session is alive.
- Warm-context routing is the orchestrator's optimization: a live orchestrator
  holding the origin worker may claim the fix bead on its behalf and route it
  through its own channel. The shepherd's contract ends at filing unassigned.
- Related but non-blocking observations (a flaky-looking test that passed on
  retry, warning-level findings) become `related`-linked beads or comments on
  the merge bead — never blocking deps.
