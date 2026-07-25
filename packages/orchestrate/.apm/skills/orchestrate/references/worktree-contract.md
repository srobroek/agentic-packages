# Worktree contract: Worktrunk lifecycle and per-repo build cache

Tracking: bead astro-plan-ki35 (platevault). Deliverable: agentic-packages
package source only — no platevault build changes.

---

## Problem statement

Raw `git worktree add /tmp/…` bypasses Worktrunk entirely. Consequences:

- `wt`'s path template, post-start hooks, and config never fire.
- Every parallel worktree grows its own `target/` tree: N Rust worktrees
  each accumulate multiple GB, filling the disk (ENOSPC observed live under
  `claude-worktrees/<repo>/`).
- Orphaned physical dirs under the harness prefix (`/private/tmp/claude-worktrees/<repo>/`)
  pin git's concurrent-worktree cap long after the agent that created them
  finished and was dismissed.

---

## Worktree creation — use `wt switch --create`

Every tool-using agent (domain-specialist, reviewer, advisor) that needs a
worktree MUST create it with Worktrunk:

```sh
# From inside the primary checkout (or any worktree of the same repo):
wt switch --create <branch> --base <base-ref>
```

`wt` computes the path from its configured template
(`~/.config/worktrunk/config.toml: worktree-path`), registers the worktree
with git, and fires `post-start` hooks (including the cargo target-dir hook
below). The agent records the resulting absolute path:

```sh
# After wt switch --create succeeds, the new worktree is the current dir.
# Record the path for the bead metadata stamp:
worktree_path="$(git rev-parse --show-toplevel)"
bd update <bead> --metadata "{\"branch\":\"<branch>\",\"worktree\":\"$worktree_path\",\"base_sha\":\"<sha>\"}"
```

### dgit push rule (Code Defender repos)

Direct `git push` to GitHub is blocked by Code Defender on work-profile
hosts. All branches MUST be pushed via `dgit push origin <branch>`. The
spawn brief carries this rule explicitly; do NOT attempt a bare `git push`
to a `github.com` remote.

### Primary checkout is off-limits

The primary checkout is shared across the whole run and may be in use by
the orchestrator. Never commit, edit, or `git worktree remove` it. Agents
work only in their own `wt`-created worktree.

---

## Per-repo shared cargo target-dir

### Why `.cargo/config.toml`, not an env var

Non-interactive build shells (cargo spawned by `just`, CI scripts, or a
subagent's build step) load neither `mise` env activations nor `~/.bashrc`.
`CARGO_TARGET_DIR` set in a login shell is invisible to them. The only
mechanism that works unconditionally is a `[build]` stanza in
`.cargo/config.toml` inside the worktree.

### Path formula (verified)

```
dirname(git -C <worktree> rev-parse --path-format=absolute --git-common-dir) / target
```

`--git-common-dir` returns the path to the shared `.git` directory (same for
the main checkout and every worktree). `dirname` strips `.git` to give the
repo root. All worktrees of one repo therefore resolve to the same absolute
`<repo-root>/target`. Verified on git 2.31+ (`--path-format` added 2.31).

### `.config/wt.toml` hook template

Drop this in the **target project's** `.config/wt.toml`. It runs once at
worktree creation (post-start) and writes a gitignored per-worktree
`.cargo/config.toml` that points cargo at the shared dir:

```toml
# .config/wt.toml — project Worktrunk configuration
# Place in the repo root. Commit it so all contributors and agents share
# the same hook without per-machine setup.

[[hooks.post-start]]
name    = "cargo-shared-target"
command = """
set -euo pipefail
common="$(git -C '{{ worktree_path }}' rev-parse --path-format=absolute --git-common-dir)"
repo_target="$(dirname "$common")/target"
mkdir -p '{{ worktree_path }}/.cargo'
printf '[build]\ntarget-dir = "%s"\n' "$repo_target" \
  > '{{ worktree_path }}/.cargo/config.toml'
# Gitignore .cargo/ inside this worktree (local, not tracked).
grep -qxF '.cargo/' '{{ worktree_path }}/.gitignore' 2>/dev/null \
  || printf '.cargo/\n' >> '{{ worktree_path }}/.gitignore'
"""
```

Template variables available in hooks: `{{ worktree_path }}` (absolute
path to the new worktree), `{{ branch }}` (branch name), `{{ worktree_name }}`
(sanitized branch name). See <https://worktrunk.dev/hook/> for the full list.

### What this achieves

- All worktrees of the same repo share `<repo>/target`. Cargo's internal
  locking serializes the link step; the `deps/` tree (typically the bulk of
  a Rust build) is built once.
- `sccache` (`RUSTC_WRAPPER=sccache`) complements this: dedupes compilation
  units across runs. Set it in the project's `.cargo/config.toml` (tracked)
  if sccache is available on the build host.
- Reclaim `target/` at `state=reported` (pushed branch present, checkout no
  longer needed for build). The wipe-worktree wisp handles checkout removal
  at merge.

### Do NOT do these

| Anti-pattern | Why it breaks |
|---|---|
| `target-dir` committed in a tracked `.cargo/config.toml` using a relative path | relative = per-worktree = no sharing |
| `target-dir` with a hardcoded absolute path committed to the repo | unportable across machines and agents |
| Single global `~/.cargo/config.toml` with a fixed `target-dir` | wrong granularity: all repos collide; one repo's build clobbers another's |
| Setting `CARGO_TARGET_DIR` only in an interactive shell's dotfile | invisible to non-interactive build shells |

---

## Worktree cleanup

### At merge (normal path)

The wipe-worktree wisp (`[wisp:recovery] wipe-worktree <abs-path>`) is
created at worktree-create time and blocked by the node's merge bead. When
the merge bead closes, the shepherd (or next patrol) runs:

```sh
# Remove via wt (preferred — deregisters from wt and git, fires pre-remove hooks):
wt remove <branch> --no-delete-branch   # branch is already merged; deletion
                                         # is the shepherd's separate step

# Fallback when wt is not available or the worktree is not wt-registered:
scripts/worktree-sweep.sh <abs-worktree-path>
```

### Orphaned physical dirs (harness prefix)

Dirs under `/private/tmp/claude-worktrees/<repo>/` that are no longer
registered in git's worktree list are physically present but git-invisible.
They do NOT count against git's worktree cap but they consume disk. The
`worktree-sweep.sh --prune <repo-path>` mode reclaims them. Run it at
run-end cleanup or any time ENOSPC risk is elevated.

---

## Reviewer and advisor worktrees

Apply the same rule: "separately prepared Worktrunk worktree" means
`wt switch --create <branch>`. The post-start hook fires automatically and
sets up the cargo target-dir. No manual `.cargo/config.toml` setup.

---

## Summary table

| Step | Command |
|---|---|
| Create worktree | `wt switch --create <branch> --base <base-ref>` |
| Record path | `git rev-parse --show-toplevel` (run from inside the new worktree) |
| Cargo target-dir | Written automatically by the `post-start` hook in `.config/wt.toml` |
| Push branch | `dgit push origin <branch>` (Code Defender repos) |
| Remove at merge | `wt remove <branch>` (primary path); `worktree-sweep.sh` (fallback) |
| Reclaim orphans | `worktree-sweep.sh --prune <repo-path>` |
