# Writing an agent brief

Every subagent starts with fresh context. The brief must carry everything the agent
needs to act and participate in the run — bead id, owned scope, base ref, run epic
id, artifacts path, deterministic commands, protocol pointers, tool guidance, and
escalation rules — templates below.

## Coder brief — copyable shape

```
ASSIGN <node>
  title:    <one line>
  bead:     <bead-id>                            # your node bead; BEADS_ACTOR=coder-<node>
  scope:    <globs you own; stay inside them>
  base:     <ref@sha>
  epic:     <epic-bead-id>
  artifacts: <abs>/.orchestration/run-<id>/artifacts/
  deps:     <node(done), …>
  commands:
    claim:  bd update <bead> --claim   THEN   bd update <bead> --metadata '{"branch":"<b>","worktree":"<abs>","base_sha":"<sha>"}'
    state:  bd set-state <bead> state=<name> --reason "<why>"
    log:    bd audit record --actor coder-<node> --kind tool_call --tool-name orc.<verb> --issue-id <bead>
            + bd comment <bead> "<VERB> <node> …fields… output_ref=<artifact path>"
    verify: <project verify cmd, e.g. `just test` / `cargo test -p <crate>`>
  protocol: on block → BLOCKED kind:<design|debug> to main (do NOT spawn). After green:
            commit + push branch, stamp pushed metadata, state=reported, send REPORTED
            to main, STAY ALIVE. Apply only FIX items; same reviewer re-reviews delta.
            Dismissed on DISMISS.
  tools:    <codebase-memory / context7 / etc. as relevant>
  ASK:      raise ASK <node> for anything needing product intent not covered here.
```

The coder's `--claim` + metadata stamp is the resumable record (assignee, branch,
worktree, base) — see `references/lifecycle.md` (Resume) and the git-anchor
contract in `references/beads-store.md`.

## Persistent-infra brief (once each)

Give the **gatekeeper** and **scribe** only the epic bead id, the artifacts path,
and their job pointer — they carry their own protocol in their agent definition.
Example: `You are the run gatekeeper. epic=<bead-id>. Integrate approved branches
FCFS under the merge slot, conflict-guarded; message me MERGED/CONFLICT. Await
approved nodes.`

## Reviewer brief (one per code node)

Spawn a `workflow-reviewer`:
`Review node <node> (bead <bead-id>): branch <b> at worktree <wt> (base <ref>).
Scope <globs>. Report REVIEW <node> verdict=approve|changes; for changes give a
numbered list, each` file:line — problem — required action `(one clause each).
Log the verdict as an audit record + bead comment. Kept alive to re-review the
delta only.`
Escalate the reviewer a tier in the brief when the diff is complex or security-critical.

## Advisor / debugger brief

Spawn a `workflow-advisor` (kind:design) or `debugger`/`general-purpose` (kind:debug)
with the coder's question verbatim + the minimal code context from its `BLOCKED`.
Reply ADVICE back in one call, read-only; relay to the coder, then dismiss.
