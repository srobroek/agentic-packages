# Writing an agent brief

Every subagent starts with fresh context. The brief must carry everything the agent
needs to act and participate in the run — bead id, owned scope, base ref, run epic
id, artifacts path, deterministic commands, protocol pointers, tool guidance, and
escalation rules — templates below.

## Prepare the checkout before spawning

The orchestrator creates every checkout. Agents never request harness worktree
isolation and never run `git worktree`.

Load the `worktrunk-writer` dependency. Run `prepare` without `--bead`, then
store its returned anchors on the unclaimed node. Its underlying creation
command and minimum anchor extraction are:

```bash
checkout="$(
  wt switch --create "<role>/<run-id>/<node>" \
    --base "<base-ref>" \
    --no-cd \
    --format=json
)"
branch="$(printf '%s' "$checkout" | jq -er '.branch')"
worktree="$(printf '%s' "$checkout" | jq -er '.path')"
bd update <bead> --metadata \
  "{\"branch\":\"$branch\",\"worktree\":\"$worktree\",\"base_sha\":\"<sha>\"}"
```

Use the `branch` and `path` returned by Worktrunk; do not predict the rendered
path from `worktree-path`. Set the spawned agent's working directory to
`worktree`. When the harness has no `cwd` field, put the absolute path in the
brief and require every file/tool call to use that directory. Spawn with a
wait-only brief and bind the runtime ID without `--bead`. Release only the T0
claim plus `validate --bead`; authorize repository tools after validation
returns `status=valid`.

If the Bead anchor stamp fails, sweep the new checkout before retrying. Never
spawn an agent whose branch/path are not durably recorded.

Writer anchors use `branch`/`worktree`. Separate tool-using checkouts use
`review_branch`/`review_worktree`, `advisor_branch`/`advisor_worktree`, or the
matching role prefix. Create reviewer and advisor branches from the writer
branch so they see the exact candidate commit. Stamp the role anchors before
spawn.

## Domain-specialist brief — copyable shape

```
ASSIGN <node>
  title:    <one line>
  bead:     <bead-id>                            # your node bead; BEADS_ACTOR=domain-specialist-<node>
  scope:    <globs you own; stay inside them>
  base:     <ref@sha>
  epic:     <epic-bead-id>
  artifacts: <abs>/.orchestration/run-<id>/artifacts/
  branch:   <Worktrunk-returned branch>
  worktree: <Worktrunk-returned absolute path>
  lease:    <Worktrunk writer lease token>
  deps:     <node(done), …>
  commands:
    claim:  bd update <bead> --claim
    lease:  worktrunk-writer validate --repo <repo> --path <worktree> --actor <actor> --lease <lease> --bead <bead>
    state:  bd set-state <bead> state=<name> --reason "<why>"
    log:    bd audit record --actor domain-specialist-<node> --kind tool_call --tool-name orc.<verb> --issue-id <bead>
            + bd comment <bead> "<VERB> <node> …fields… output_ref=<artifact path>"
    verify: <project verify cmd, e.g. `just test` / `cargo test -p <crate>`>
  protocol: on block → BLOCKED kind:<design|debug> to main (do NOT spawn). After green:
            commit + push branch, stamp pushed metadata, state=reported, send REPORTED
            to main, STAY ALIVE. Apply only FIX items; same reviewer re-reviews delta.
            Dismissed on DISMISS.
  tools:    <codebase-memory / context7 / etc. as relevant>
  ASK:      raise ASK <node> for anything needing product intent not covered here.
```

The orchestrator's Worktrunk anchor stamp plus the domain-specialist's
`--claim` is the resumable record (assignee, branch, worktree, base). See
`references/lifecycle.md` (Resume) and the git-anchor contract in
`references/beads-store.md`.

## Delegated implementation child

The domain-specialist may delegate bounded implementation inside its prepared
checkout. It performs this sequence for each child:

1. Spawn the child wait-only with the specialist's absolute Worktrunk path.
   Do not request harness isolation and do not include a Bead id.
2. Bind the returned child runtime id to the specialist's existing path,
   actor, and lease with `worktrunk-writer bind` without `--bead`.
3. After `status=bound`, send the implementation brief. Limit it to the
   specialist's scope and prohibit Beads, Worktrunk lifecycle commands,
   commits, pushes, and further delegation.
4. Collect the child before review, commit, or `REPORTED`. The specialist
   reviews all child edits and remains the only lifecycle owner.

This shared checkout exception applies only to throwaway children of the
claim-holder. Another claim-holder, reviewer, advisor, debugger, researcher,
or auditor receives a separate prepared Worktrunk checkout.

## Persistent-infra brief (once each)

Give the **shepherd** only the epic bead id, the artifacts path, and its job
pointer. Invoke the audit reporter separately when a report is needed.
Example: `You are the run shepherd. epic=<bead-id>. Integrate approved branches
under the merge slot without waiting; if held, report the holder, defer, and
retry. Order follows successful acquisition, not FIFO. Message me MERGED/CONFLICT. Await
approved nodes.`

## Reviewer brief (one per code node)

Create a review branch with
`wt switch --create <review-branch> --base <writer-branch>`, then spawn
`reviewer` with no harness isolation:
`Review node <node> (bead <bead-id>): writer branch <b>; your read-only branch
<review-b> at Worktrunk path <review-wt> (base <ref>). Scope <globs>. Report
REVIEW <node> verdict=approve|changes; for changes give a numbered list, each`
file:line — problem — required action `(one clause each). Log the verdict as
an audit record + bead comment. Kept alive to re-review the delta only.`
Escalate the reviewer a tier in the brief when the diff is complex or security-critical.

## Advisor / debugger brief

Create a branch with
`wt switch --create <role-branch> --base <writer-branch>`, stamp the role
branch/path, then spawn an `advisor` (kind:design) or
`debugger`/`general-purpose` (kind:debug) there whenever it will invoke tools.
Pass the domain-specialist's question verbatim + the minimal code context from
its `BLOCKED`. Reply ADVICE back in one call, read-only; relay to the
domain-specialist, dismiss, then sweep the role checkout with
`worktree-sweep.sh --discard-branch <path>`.
