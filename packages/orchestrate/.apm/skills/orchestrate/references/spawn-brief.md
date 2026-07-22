# Writing an agent brief

Every task-scoped agent starts with fresh context. A directed brief carries the
bead and selected actor. A generic-pull brief carries the queue contract until
an atomic claim returns the bead. Both carry owned scope, base ref, run epic,
artifacts path, deterministic commands, protocol pointers, tool guidance,
evidence mode, and escalation rules.

## Coordinator handoff to a selected actor

Exact assignment is a durable Beads operation, not only a prompt:

```
bd update <bead> --assignee <actor> \
  --set-metadata execution_agent=<agent-type> \
  --set-metadata execution_dispatch=<explicit|specialist>
```

Send the brief only after that succeeds. The selected worker exports
`BEADS_ACTOR=<actor>` and runs `bd update <bead> --claim`; Beads 1.1.0 treats a
claim already assigned to the same actor as idempotent. A different assignee
means another actor owns the node: do not overwrite or steal it.

## Directed worker brief — copyable shape

```
ASSIGN <node>
  title:      <one line>
  bead:       <bead-id>
  actor:      <exact assignee; export as BEADS_ACTOR>
  task-kind:  <execution_kind>
  capabilities: <required cap slugs>
  evidence:   <git|artifact|comment|external>
  scope:      <owned file globs or canonical non-git resource prefixes>
  base:       <ref@sha; required for git evidence>
  epic:       <epic-bead-id>
  artifacts:  <abs>/.orchestration/run-<id>/artifacts/
  deps:       <node(done), …>
  commands:
    claim:    bd update <bead> --claim
    anchors:  git → stamp branch/worktree/base_sha metadata immediately;
              non-git → preserve evidence mode and scope metadata
    state:    bd set-state <bead> state=<name> --reason "<why>"
    log:      bd audit record --actor <actor> --kind tool_call --tool-name orc.<verb> --issue-id <bead>
              + bd comment <bead> "<VERB> <node> …fields… output_ref=<ref>"
    verify:   <project command or evidence check>
  protocol:   on block → BLOCKED kind:<design|debug> to main (do NOT spawn).
              After verification, report evidence, set state=reported, send
              REPORTED to main, STAY ALIVE. For git evidence, commit + push
              first. For non-git evidence, do not create an empty branch or
              commit. Apply only FIX items; the same reviewer re-reviews.
              Dismissed on DISMISS after merge or approved non-git closure.
  tools:      <codebase-memory / context7 / etc. as relevant>
  ASK:        raise ASK <node> for product intent not covered here.
```

The claim plus anchors are the resumable record. Git-backed work stamps
branch/worktree/base. Non-git work already carries its resource scope and later
adds `output_ref` in its report. See `references/lifecycle.md` and the git
anchor contract in `references/beads-store.md`.

## Generic pull brief — copyable shape

```
ASSIGN queue:<queue>
  actor:      <worker actor; export as BEADS_ACTOR>
  epic:       <epic-bead-id>
  queue:      agent:<queue>
  task-kind:  <allowed execution_kind>
  capabilities: <worker capability slugs>
  evidence:   <allowed evidence modes>
  base:       <ref@sha for git-capable queues>
  artifacts:  <abs>/.orchestration/run-<id>/artifacts/
  commands:
    claim:    bd ready --parent <epic> --label orc-node --label agent:<queue>
              --metadata-field execution_kind=<kind> --unassigned
              --sort priority --claim --json
    after:    accept the returned bead; verify its routing envelope; stamp
              execution_agent=<agent-type> and execution_dispatch=generic;
              stamp applicable git anchors; set state=working
    log:      bd audit record + bd comment on the claimed bead
    verify:   <project command or evidence check>
  protocol:   one activation claims at most one bead. Never list and choose.
              Do not claim another until this node is terminal. Empty claim
              result after a race changes no bead. Mismatch → do no task work,
              record evidence, BLOCKED kind:design to main. Otherwise follow
              the directed worker protocol for the claimed node.
```

The coordinator adds `agent:<queue>` only after the bead's task kind and every
required capability fit the queue contract. The worker still verifies the
claimed envelope before editing; the queue label is routing data, not authority
to exceed the brief.

## Completion evidence and review

| Evidence | `REPORTED` carries | Review and terminal path |
|---|---|---|
| `git` | branch, worktree, commit SHAs, verification | independent workflow-reviewer, then gatekeeper merge |
| `artifact` | absolute `output_ref`, method and verification | independent compatible read-only reviewer, then orchestrator closes as `dismissed` |
| `comment` | bead comment or audit-event ref plus verification | independent compatible read-only reviewer, then orchestrator closes as `dismissed` |
| `external` | resource identity, before/after or read-back evidence, verification | independent compatible read-only reviewer, then orchestrator closes as `dismissed` |

Non-code does not mean non-git. Documentation or configuration that changes a
tracked file uses `git` evidence. Research, analysis, and read-only review use
artifact or comment evidence. External operations use read-back evidence. An
empty commit, placeholder branch, or invented PR is prohibited.

## Persistent-infra brief (once each)

Give the **gatekeeper** and **scribe** only the epic bead id, the artifacts path,
and their job pointer — they carry their own protocol in their agent definition.
Example: `You are the run gatekeeper. epic=<bead-id>. Integrate approved branches
FCFS under the merge slot, conflict-guarded; message me MERGED/CONFLICT. Initial
APPROVE opens and parks GitHub PR waits. An APPROVE with
source=release-queue-watch wakes exact PR/head revalidation; the watcher never
owns the merge slot. Await approved nodes.`

## Reviewer brief (one per deliverable node)

The reviewer must be a different actor from the worker. Use
`workflow-reviewer` for git evidence and a compatible read-only Evidence
reviewer otherwise:

`Review node <node> (bead <bead-id>) against its acceptance criteria. Evidence
mode <mode>; evidence ref <branch/worktree/output_ref/resource>; base <ref when
git>; owned scope <scope>. Report REVIEW <node> verdict=approve|changes. For
changes give a numbered list, each` file-or-evidence-ref — problem — required
action `(one clause each). Log the verdict as an audit record + bead comment.
Stay available to re-review the delta only.`

Escalate the reviewer a tier in the brief when the change is complex,
security-critical, or a high-stakes external mutation.

## Advisor / debugger brief

Spawn a `workflow-advisor` (kind:design) or `debugger`/`general-purpose`
(kind:debug) with the worker's question verbatim plus the minimal context from
its `BLOCKED`. Reply `ADVICE` back in one call, read-only; relay to the worker,
then dismiss.
