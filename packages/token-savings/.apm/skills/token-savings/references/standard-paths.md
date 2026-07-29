# Standardised artifact paths, for project-scaffold to adopt

A brief for the `project-scaffold` project. Every agent tool that builds an index
picks its own location, and the choices conflict: some write into the working
tree, none of them gitignore themselves, and two tools generating "the index"
into different places means neither is discoverable.

This proposes one scheme, derived from what broke.

## What broke, and what it cost

| Tool | Where it writes | Gitignored | Size |
| --- | --- | --- | --- |
| `repomix` (default) | `<repo>/repomix.xml` | **no** | 4.7 MB to 39 MB |
| `graphify` | `<repo>/graphify-out/` | **no** | 9.9 MB to 60 MB |
| Serena | `<repo>/.serena/` | yes | 960 KB |
| `token-savings` map | `$XDG_STATE_HOME/...` | n/a, outside the tree | 82 KB |

Two consequences, both measured:

**Un-ignored artifacts get packed into the next artifact.** Running the tuning
sweep on a repository where graphify had been used showed `graphify-out/` was
**38% of the entire repomix pack** -- an index of an index. Adding
`**/graphify-out/**` and `**/.serena/**` to the ignore set took that repository
from a 14.9% reduction to 87%.

**An artifact inside the tree dirties `git status`.** The existing
`mcp-repomix` hook refuses to write unless its output is already gitignored,
which no local repository had done, so it never produced a snapshot on any
repository -- a silent no-op for as long as it shipped.

## The scheme

```
${XDG_STATE_HOME:-$HOME/.local/state}/agentic-tools/<tool>/<sha256(repo_root)[:16]>-<artifact>
${XDG_STATE_HOME:-$HOME/.local/state}/agentic-tools/<tool>/<sha256(repo_root)[:16]>.head
```

Four properties, each earning its place:

1. **Outside the working tree.** No gitignore entry to add, no `git status`
   noise, nothing to accidentally commit, and it survives `git clean -xfd`.
2. **Keyed by a hash of the absolute repository root.** One artifact per
   checkout, so worktrees of the same repository do not collide -- each has its
   own root path and therefore its own key.
3. **`XDG_STATE_HOME`, not `XDG_CACHE_HOME`.** These are regenerable but not
   disposable: losing one costs a rebuild during a session. State is the right
   category, and it keeps them out of cache-eviction sweeps.
4. **A `.head` marker beside each artifact**, holding the commit the artifact was
   built from. That single file answers "is this stale" without running git.

Total footprint on this machine for two repositories plus a spill store: **184 KB**.

## What project-scaffold should provide

MUST A resolver every tool can call, rather than each reimplementing the hash.
  Same input (repo root, tool name, artifact name) gives the same path from any
  language. `token-savings` implements this in `repomix-map.py:state_dir()` and
  `map_paths()`; that is the reference, not the API.

MUST A gitignore contribution for the tools that CANNOT be redirected. repomix
  can be pointed anywhere with `--output`, but `graphify` writes `graphify-out/`
  relative to the repository with no override flag found. Those need
  `.gitignore` entries scaffolded, or they land in commits.

MUST A staleness convention. Read the `.head` marker, compare to `HEAD`, and
  report the commit distance rather than rebuilding. Rebuilding at session start
  charges every session for an artifact that goes stale on the first edit.

SHOULD A single prune entry point. Each tool bounding its own store means N
  policies; `token-savings` caps its spill store at 200 files and 7 days, and
  nothing bounds the maps.

NOT Put an artifact in the tree because agents will not otherwise find it. That
  is a real problem with a better fix: inject the path. A subagent asked a
  where-is-X question with no steering answered in five `ls`/`rg` calls and
  reported seeing "no mention anywhere in my context of a pre-built repository
  structure map" -- the parent knew, the child did not, because `SessionStart`
  does not fire for subagents. A `SubagentStart` hook naming the absolute path
  and the exact `rg` command to search it fixes discovery without touching the
  tree.

## Global versus per-project

This belongs in a **global** install. The paths are machine-wide by construction
(`$XDG_STATE_HOME`), the tools are installed once per machine, and per-project
copies of the same resolver would drift. A project-local install would also mean
a repository without the scaffolding writes to a different location than one
with it, which defeats the point of standardising.
