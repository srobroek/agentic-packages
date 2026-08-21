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

Two consequences, both measured:

**Un-ignored artifacts get packed into the next artifact.** Running the tuning
sweep on a repository where graphify had been used showed `graphify-out/` was
**38% of the entire repomix pack** -- an index of an index. Adding
`**/graphify-out/**` and `**/.serena/**` to the ignore set took that repository
from a 14.9% reduction to 87%.

**An artifact inside the tree dirties `git status`.** The former `mcp-repomix`
hook refused to write unless its output was already gitignored, which no local
repository had done, so it never produced a snapshot anywhere -- a silent no-op
for as long as it shipped, and one reason the package is gone.

## The scheme

Artifacts live in the repository root, gitignored, at their tools' conventional
names:

```
<repo>/repomix-full.xml     gitignored, in .worktreeinclude
<repo>/graphify-out/        gitignored, in .worktreeinclude
<repo>/.serena/             gitignored (Serena already does this)
```

Out-of-tree storage keyed by a hash of the repository root was tried first and
FAILED the only test that mattered. Asked a where-is-X question with no steering,
a subagent answered in five `ls`/`rg` calls and reported "no mention anywhere in
my context of a pre-built repository structure map". In-tree is discoverable the
way every other file is, needs no injection hook, and `wt step copy-ignored` warms
a worktree with it because these artifacts hold no absolute paths.

The cost of in-tree is that each artifact needs a `.gitignore` entry, which is
precisely what scaffolding is for.

## What project-scaffold should provide

MUST A gitignore contribution for the tools that CANNOT be redirected, scaffolded
  into every new repository. repomix takes `--output <path>` and can be pointed
  outside the tree; `graphify` cannot. Its query verbs accept `--graph <path>`,
  but `graphify update` has NO output flag: it writes `graphify-out/` relative to
  the repository, unavoidably. So the scaffolded `.gitignore` needs at minimum:

    graphify-out/
    /repomix.xml
    .serena/

  Leaving them tracked costs twice. They are large (`graphify-out/` 9.9 MB on a
  741-file repository, 60 MB on a 4,107-file one; `repomix.xml` 4.7 MB and 39 MB),
  and they feed into the NEXT artifact -- `graphify-out/` measured 38% of one
  repository's entire repomix pack.

MUST A `.worktreeinclude` listing the artifacts, so `wt step copy-ignored` warms a
  new worktree instead of rebuilding. Both hold no absolute paths, so a copy is
  valid in any checkout: `repomix-full.xml` is 1.3 to 3.2s to rebuild against 82 KB
  to copy, `graphify-out/` 6.9s against 9.9 MB.

NOT Store an artifact outside the tree keyed by a hash of the repository root. It
  was tried and lost on discovery: a subagent asked a where-is-X question answered
  in five `ls`/`rg` calls and reported "no mention anywhere in my context of a
  pre-built repository structure map", because `SessionStart` does not fire for
  subagents. Injecting the path needs a `SubagentStart` hook on every spawn; an
  in-tree file needs one steering line naming the filename. In-tree plus
  gitignored plus `.worktreeinclude` won, and the injection hook was deleted.

## Per-worktree cost, which the scheme does not solve

A Worktrunk worktree is a separate root, so every artifact is rebuilt there. For
`repomix-full.xml` that is 1.3 to 3.2s, which `copy-ignored` avoids entirely. For graphify it is 6.9s and 9.9 MB INSIDE the tree, per
worktree, with no way to redirect it.

DEFAULT Do not build a graphify graph per worktree. Point queries at the primary
  checkout's graph with `--graph <primary>/graphify-out/graph.json`; it is a
  snapshot, so a few commits of drift is the same staleness the primary already
  tolerates.
MUST Rebuild in the worktree only when the branch has changed the code being
  queried, and gitignore the output first.

## Everything repository-local, nothing global

The artifacts live IN the tree, gitignored, and every command that maintains them
belongs in the repository's checked-in `.config/wt.toml`. The decisive argument is
cloning: a collaborator without your global config gets nothing, and no signal
names what is missing. A checked-in file travels with the clone.

This holds even for a command whose TEXT looks like a cross-repository invariant.
`repomix` is byte-identical in every repository, but what makes it correct is the
`repomix.config.json` committed beside it, so it is a repository command. Resolve
the ambiguous case toward the repository.

The only global piece is tool INSTALLATION (mise or equivalent), which is a
machine concern rather than a repository one.
