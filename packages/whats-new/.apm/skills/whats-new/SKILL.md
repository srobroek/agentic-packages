---
name: whats-new
description: Research what changed in a tool, CLI, library, framework, language runtime, package, plugin, or any software dependency between the version in use and the latest — breaking changes, deprecations, new features, and bug fixes. Use when the user asks "what's new in X", "what changed since <version>", "is it safe to upgrade X", "should I bump X", "what will break if I update X", "review the changelog for X", "what's the diff between X 2.1 and 3.0", or asks about an upgrade / migration / release notes for any named tool or dependency. With no target named, researches the outdated dependencies in the current repository.
---

# What's New (Upgrade Research)

On-demand research skill. For a named tool/CLI/library/dependency — or, with no
target, the things the current repo depends on — find what changed between the
**current** version and the **latest**, and summarize it as: breaking changes,
deprecations, new features, and notable fixes.

You decide where the changes live and how to fetch them. The job is to do that
**programmatically**, not by reading rendered web pages: every version number,
tag list, and changelog has a machine endpoint that returns small structured
output. `references/recipes.md` is the cookbook of those commands, organized by
ecosystem and host. Reserve web fetching for genuine prose (a migration guide,
a post explaining a breaking change) — never to discover data you can query.

## When to use

Triggers: "what's new in <X>", "what changed since <version>", "is it safe to
upgrade <X>", "should I bump <X>", "what breaks if I update <X>", "review the
changelog / release notes for <X>", "migration notes for <X>", "diff between
<X> a.b and c.d". X can be a library, CLI, framework, language runtime, build
tool, plugin, container image, or any other versioned software.

## Inputs

Honor whatever the user supplies; only discover the rest. Always weave in user
requests — focus areas ("only breaking changes", "security fixes", "does it
still support node 18"), depth, and output destination.

- **Target** — the tool/library name. If absent, discover it (step 1).
- **Current version** — from the user, else from the lockfile/manifest.
- **Latest / target version** — from the user, else the registry's latest.

## Workflow

1. **Resolve the target.** If the user named one, use it. Otherwise run
   `scripts/detect.sh [dir]` — it lists the repo's declared dependencies and
   pinned versions across ecosystems, offline. Pick the target(s); ask the user
   if several are equally plausible.
2. **Resolve versions + source repo (programmatically).** Using
   `references/recipes.md` step A/B: get the current version (prefer the
   lockfile's exact pin), then query the registry for the latest version, the
   version list, the upstream repo URL, and any deprecation flag. One
   `curl | jq` per ecosystem — do not scrape a web page for this.
3. **Gather the changes (programmatically).** Using recipes step C: the
   host-agnostic core is a bare `git` clone of the resolved repo — read the
   CHANGELOG as tracked at the target tag and the classified commit log between
   the two tags. This works for GitHub, GitLab, Bitbucket, Codeberg, sr.ht, or a
   private remote identically. Then enrich with the host's **release notes** via
   its API (GitHub/GitLab/Gitea recipes provided). Cover the whole span, not
   just the endpoints.
4. **Fill prose gaps (only if needed).** For a migration guide or a
   deprecation-timeline explanation not in the changelog, fetch the specific
   page (recipes step D) — the orchestrator should pass a web-fetch/web-search
   capability. Prefer the project's own guide over third-party blogs.
5. **Summarize into the template.** LOAD `references/report-template.md` and
   fill every section: Breaking changes, Deprecations, New features, Fixes,
   Upgrade notes, Coverage. Cite a source (release tag, commit SHA, CHANGELOG
   heading, doc URL) for each material claim.
6. **Save or return** per the user's request (default: return inline; save to a
   file if asked or if the report is long).

## Steering

- **Report, don't upgrade.** Research and summarize only; never edit manifests,
  bump versions, or run installers.
- **Programmatic over manual.** If you catch yourself about to read a rendered
  registry page or a docs site to find a version or a changelog, stop and use
  the matching recipe instead. Web fetch is for prose, not data.
- **Cover the whole span.** Changes accumulate across every intermediate
  version. The commit log and CHANGELOG span it; release notes are per-tag —
  gather all tags in range.
- **Classification is heuristic.** A `feat:`/`fix:`/`!` prefix or a
  `BREAKING CHANGE:` trailer is a signal, not ground truth; read the actual
  diff for anything load-bearing.
- **State coverage honestly.** Name which sources were available (releases vs.
  commits vs. changelog vs. migration guide) and which were missing. A summary
  built from one source of five is not a researched upgrade — say so.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/detect.sh` | No-network enumeration of the repo's declared dependencies + pinned versions across ecosystems (npm/pnpm/yarn, pip/poetry/uv, cargo, go, rubygems, composer). Use to pick a target when none is named. Optional arg: project dir (default `.`). |

For everything network-facing (latest version, repo URL, releases, changelog,
commit log) use the commands in `references/recipes.md` — these are documented
so they stay deterministic without hard-coding a single rigid pipeline.
