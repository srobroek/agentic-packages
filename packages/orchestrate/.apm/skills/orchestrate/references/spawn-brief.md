# Writing an agent brief

Every subagent starts with fresh context. The brief must carry everything the agent
needs to act and participate in the run — bead id, owned scope, base ref, run epic
id, artifacts path, deterministic commands, protocol pointers, tool guidance, and
escalation rules — templates below.

## Domain-specialist brief — copyable shape

```
ASSIGN <node>
  title:    <one line>
  bead:     <bead-id>                            # your node bead; BEADS_ACTOR=domain-specialist-<node>
  scope:    <globs you own; stay inside them>
  base:     <ref@sha>
  epic:     <epic-bead-id>
  artifacts: <abs>/.orchestration/run-<id>/artifacts/
  deps:     <node(done), …>
  commands:
    worktree: wt switch --create <branch> --base <base-ref>
              # wt manages path, fires post-start hooks (cargo target-dir, etc.)
              # After switch: worktree_path=$(git rev-parse --show-toplevel)
    claim:  bd update <bead> --claim   THEN   bd update <bead> --metadata '{"branch":"<b>","worktree":"<abs>","base_sha":"<sha>"}'
    state:  bd set-state <bead> state=<name> --reason "<why>"
    log:    bd audit record --actor domain-specialist-<node> --kind tool_call --tool-name orc.<verb> --issue-id <bead>
            + bd comment <bead> "<VERB> <node> …fields… output_ref=<artifact path>"
    verify: <project verify cmd, e.g. `just test` / `cargo test -p <crate>`>
    push:   dgit push origin <branch>   # Code Defender blocks direct github push
  protocol: on block → BLOCKED kind:<design|debug> to main (do NOT spawn). After green:
            commit + push branch (via dgit), stamp pushed metadata, state=reported,
            send REPORTED to main, STAY ALIVE. Apply only FIX items; same reviewer
            re-reviews delta. Dismissed on DISMISS.
  tools:    <codebase-memory / context7 / etc. as relevant>
  ASK:      raise ASK <node> for anything needing product intent not covered here.
  worktree-contract: references/worktree-contract.md
```

The domain-specialist's `--claim` + metadata stamp is the resumable record (assignee, branch,
worktree, base) — see `references/lifecycle.md` (Resume) and the git-anchor
contract in `references/beads-store.md`.

Worktree must be created with `wt switch --create` (not raw `git worktree add`). The primary
checkout is shared — never commit, edit, or remove it. See
`references/worktree-contract.md` for the full contract, the `.config/wt.toml` hook
template (per-repo shared cargo target-dir), and the dgit push rule.

## Persistent-infra brief (once each)

Give the **shepherd** only the epic bead id, the artifacts path, and its job
pointer. Invoke the audit reporter separately when a report is needed.
Example: `You are the run shepherd. epic=<bead-id>. Integrate approved branches
under the merge slot without waiting; if held, report the holder, defer, and
retry. Order follows successful acquisition, not FIFO. Message me MERGED/CONFLICT. Await
approved nodes.`

## Reviewer brief (one per code node)

Spawn a `reviewer` in a Worktrunk worktree (`wt switch --create <branch>`):
`Review node <node> (bead <bead-id>): branch <b> at worktree <wt> (base <ref>).
Scope <globs>. Report REVIEW <node> verdict=approve|changes; for changes give a
numbered list, each` file:line — problem — required action `(one clause each).
Log the verdict as an audit record + bead comment. Kept alive to re-review the
delta only.`
Escalate the reviewer a tier in the brief when the diff is complex or security-critical.

## Advisor / debugger brief

Spawn a `advisor` (kind:design) or `debugger`/`general-purpose` (kind:debug)
in a Worktrunk worktree (`wt switch --create <branch>`) whenever it will invoke tools;
with the domain-specialist's question verbatim + the minimal code context from its `BLOCKED`.
Reply ADVICE back in one call, read-only; relay to the domain-specialist, then dismiss.
