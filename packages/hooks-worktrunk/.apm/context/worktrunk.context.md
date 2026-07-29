---
x-lint:
  allow: [W6]
  reason: "the global contract keeps all lifecycle events, cache boundaries, native plugins, and agent checkout rules together"
---

# Worktrunk Workflow

MANAGEMENT
MUST WT-1: use Worktrunk for worktree lifecycle operations; never run
  `git worktree add|list|move|remove|prune|lock|unlock|repair`.
MUST Create branches with `wt switch --create <branch> --base <base>`.
MUST Open existing branches with `wt switch <branch>` and inspect with `wt list`.
MUST Remove with `wt remove <branch-or-path>` and relocate with
  `wt step relocate [branch]`.
MUST Preview integrated cleanup with `wt step prune --dry-run`; cleanup is
  `wt step prune`.

AGENT CHECKOUTS
MUST Every agent that writes receives a parent-prepared Worktrunk checkout,
  including domain specialists and delegated implementation agents.
DEFAULT A claim-holder may bind throwaway implementation children to its
  prepared checkout; those children never manage worktrees or durable state.
MUST A tool-using reviewer, auditor, researcher, or advisor receives a separate
  read-only Worktrunk checkout; a remote-only or conversational agent is exempt.
MUST Capture `wt switch --create <branch> --base <base> --no-cd --format=json`
  and record the returned branch/path in durable task state before spawn.
NOT Use harness `isolation:"worktree"` when a workflow requires a
  parent-prepared checkout and durable pre-spawn anchors.
DEFAULT Ad hoc Claude isolation may use `isolation:"worktree"` after the
  official Worktrunk plugin is installed; its lifecycle hooks route Claude's
  create/remove events through Worktrunk. Codex has no equivalent isolation.

PULL REQUESTS
MUST Open a GitHub pull request with `wt switch pr:<number>` or its pull-request
  URL; never use `gh pr checkout`.
DEFAULT Browse open pull requests with `wt switch --prs`.

NATIVE PLUGINS
MUST Install the official Claude plugin with `wt config plugins claude install`;
  it owns activity markers, `WorktreeCreate`, `WorktreeRemove`, and
  `/wt-switch-create`.
MUST Register the Codex marketplace with `wt config plugins codex install`, then
  install Worktrunk through Codex `/plugins`.
NOT Reimplement native activity markers or Claude lifecycle events in this
  package.

PROJECT START
DEFAULT Warm allowlisted ignored state with
  `wt step copy-ignored --require-include` in `post-start`.
NOT Copy Python virtual environments; run `uv sync` because their paths are
  absolute.
NOT Copy `target/` when the repository-scoped Cargo target hook is active.
NOT Treat `copy-ignored` as a shared writable build directory; it creates a
  copy-on-write warm start where the filesystem supports reflinks.
DEFAULT Run a dev server with
  `wt step tether -- <command> --port {{ branch | hash_port }}` and expose the
  matching `[list] url`.
MUST Put every project command in the repository's checked-in `.config/wt.toml`,
  never in the global user config, even when the command itself looks like an
  invariant. A collaborator cloning the repository has no global config and gets
  nothing, with no signal naming what is missing; a checked-in file travels with
  the clone. This holds for the repomix refresh, builds, watchers, dev servers,
  and database setup alike:

    [post-start]
    repomix = "repomix"

  `repomix` with no arguments reads the repository's committed
  `repomix.config.json`, so the hook line stays identical across repositories
  while each one supplies its own patterns.
MUST Gitignore the pack and list it in `.worktreeinclude`. Copying beats
  rebuilding and the pack holds no absolute paths, so a copy is valid in any
  checkout: 1.3 to 3.2s to rebuild against 82 KB to copy, near-free on a reflink
  filesystem. `copy-ignored` runs first, so `repomix` only repacks what the branch
  changed.
NOT Read the pack whole. It is 6,349,248 tokens on a 4,107-file repository; a
  `PreToolUse` guard denies the read and names `rg`/`awk` instead.
NOT Build a graphify graph per worktree. `graphify update` has no output flag and
  writes `graphify-out/` into the tree: 6.9s and 9.9 MB on a 741-file repository,
  paid again in every worktree. Gitignore it, list it in `.worktreeinclude` so a
  new checkout copies it, and query the primary checkout with
  `--graph {{ primary_worktree_path }}/graphify-out/graph.json`, which carries the
  same staleness the primary already tolerates. Rebuild locally only when the
  branch changed the code being queried.

HOOK OWNERSHIP
MUST User hooks contain cross-repository invariants only. Repository commands
  belong in checked-in `.config/wt.toml`.
MUST Resolve the ambiguous case toward the repository. A command can look like an
  invariant (`repomix`, `just build`, `pnpm install`) because its TEXT is the same
  everywhere, and still belong in the repository: what makes it work is the
  committed config beside it. Put it in the global config and a collaborator who
  clones the repository gets silence, with nothing naming what they lack.
DEFAULT Repositories encode repeatable setup, validation, dev servers,
  databases, and cleanup in project hooks instead of agent instructions or
  manual runbooks.

| event | global user hook | project hook |
|---|---|---|
| `pre-switch` | none | destination policy required before resolution |
| `post-switch` | none | notifications or context refresh |
| `pre-start` | repository Cargo target materialization; mise trust | required env generation and dependency setup |
| `post-start` | allowlisted `copy-ignored` warm start | builds, watchers, tethered dev servers, databases |
| `pre-commit` | none | fast formatter, lint, type checks |
| `post-commit` | none | CI triggers or notifications |
| `pre-merge` | none | tests, security scans, build verification |
| `post-merge` | none | deployment, notifications, local binary refresh |
| `pre-remove` | none | save artifacts or back up worktree state |
| `post-remove` | none | stop external resources and remove branch services |

CACHES
MUST Share Cargo output per repository, never per machine: each Worktrunk
  Rust checkout receives a marker-owned Cargo config that points to
  `{{ primary_worktree_path }}/target` and is ignored through the repository's
  shared Git exclude file.
MUST Refuse to overwrite an existing `.cargo/config.toml`; that repository
  owns target configuration through its tracked config or project hook.
NOT Export `CARGO_TARGET_DIR` from a lifecycle hook as the only configuration;
  hook environment changes do not persist into later agent build shells.
MUST Preserve native user-level content-addressed/download stores for npm,
  pnpm, Bun, uv/pip, Go, Gradle/Maven, NuGet, and compiler caches.
NOT Share writable `node_modules`, virtual environments, Python bytecode,
  branch-derived build output, dev-server state, or databases across live
  worktrees.
DEFAULT Warm safe ignored state with copy-on-write through
  `.worktreeinclude`; Python environments use `uv sync`.

CONFIG
MUST Keep `commit.generation.command` in user config; project config may set
  only `commit.generation.template-append`.
DEFAULT Use Worktrunk `[aliases]` for repeatable lifecycle commands and Fish
  only for shell integration or commands that must change the parent shell.

SOURCES
MUST Base hook behavior on https://worktrunk.dev/hook/ and agent integration
  on https://worktrunk.dev/claude-code/.
MUST Base cache copying on
  https://worktrunk.dev/step/#wt-step-copy-ignored and operational recipes on
  https://worktrunk.dev/tips-patterns/.
