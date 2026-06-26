---
name: whats-new
description: Research what changed in a tool, CLI, library, framework, language runtime, package, plugin, software dependency — OR a technology, cloud service, hosted API, platform, or model family (e.g. AWS Bedrock, Anthropic / Claude models, OpenAI, GCP BigQuery, Azure, Stripe, GitHub Actions) — between the version or point in time in use and the latest: breaking changes, deprecations, new features, new capabilities, and fixes. Use when the user asks "what's new in X", "what changed since <version/date>", "is it safe to upgrade X", "should I bump X", "what will break if I update X", "review the changelog / release notes for X", "what's the diff between X 2.1 and 3.0", "what new models/features did <vendor> ship", or asks about an upgrade / migration / release notes / recent announcements for any named tool, dependency, technology, or service. With no target named, researches the outdated dependencies in the current repository.
---

# What's New (Upgrade & Change Research)

On-demand research skill. For a named target — or, with no target, the things
the current repo depends on — find what changed between what is **in use** and
the **latest**, and summarize it as: breaking changes, deprecations, new
features/capabilities, and notable fixes.

You decide where the changes live and how to fetch them. The job is to do that
**programmatically**, not by reading rendered web pages: versions, tag lists,
changelogs, and even service announcement streams have machine endpoints (JSON,
RSS/Atom, git) that return small structured output. `references/recipes.md` is
the cookbook of those commands. Reserve web fetching for genuine prose (a
migration guide, a post explaining a breaking change) — never to discover data
you can query.

## Target kinds

First decide which kind of target you have — the sourcing differs:

- **Versioned software** (library, CLI, framework, runtime, package, container
  image): has a registry + a git repo + semver. Research a *version span*
  current→latest. Recipes steps A–D.
- **Service / technology / platform / API / model family** (AWS Bedrock,
  Anthropic/Claude models, OpenAI, GCP, Azure, Stripe, GitHub Actions): usually
  no semver and no single git repo. "What's new" is a *dated announcement
  stream* — research everything since the user's reference point (a date, or
  "what they currently use"). Recipes step E.

A target can be both (e.g. an SDK is versioned software; the service behind it
is a stream) — research both sides when relevant.

## Inputs

Honor whatever the user supplies; only discover the rest. Always weave in user
requests — focus areas ("only breaking changes", "security fixes", "does it
still support node 18", "only the new models"), depth, and output destination.

- **Target** — the tool/library/service name. If absent, discover it (step 1).
- **Reference point** — for software, the current version (from the user, else
  the lockfile/manifest); for a service, the user's baseline date or "what we
  use now". If none is given for a service, ask, or default to a sensible window
  (e.g. last 6–12 months) and say so.
- **Latest** — the registry's latest version, or "now" for a service stream.

## Workflow

1. **Resolve the target and its kind.** If the user named one, use it.
   Otherwise run `scripts/detect.sh [dir]` — it lists the repo's declared
   dependencies and pinned versions across ecosystems, offline. Pick the
   target(s); ask if several are equally plausible. Decide: versioned software
   or service/stream (see Target kinds).

2. **Resolve sources programmatically.**
   - *Software* (recipes A/B): current version (prefer the lockfile pin), then
     the registry's latest version, version list, upstream repo URL, and
     deprecation flag — one `curl | jq` per ecosystem.
   - *Service/stream* (recipes E): the vendor's machine-readable change source
     (RSS/Atom feed, release-notes JSON, a models API, or a changelog repo), and
     the time window to cover.

3. **Gather the changes programmatically.**
   - *Software* (recipes C): bare `git` clone of the repo — CHANGELOG at the
     target tag + the conventional-commit-classified log across the whole span
     (host-agnostic: GitHub/GitLab/Bitbucket/Codeberg/sr.ht/private). Enrich
     with host **release notes** via its API.
   - *Service* (recipes E): pull the feed/release-notes/model-list, filter to
     the window, group. If the vendor also keeps notes in a repo/SDK, use C.

4. **Fill prose gaps only if needed** (recipes D): a migration guide, a
   deprecation timeline, or a JS-rendered release-notes page that returns no
   data to `curl`. Fetch the specific page (orchestrator passes web-fetch);
   prefer the vendor's own guide over third-party blogs.

5. **Summarize into the template.** LOAD `references/report-template.md` and
   fill every section: Breaking changes, Deprecations, New features, Fixes,
   Upgrade notes, Coverage. Cite a source (release tag, commit SHA, CHANGELOG
   heading, feed entry date, doc URL) for each material claim.

6. **Save or return** per the user's request (default: return inline; save to a
   file if asked or if the report is long).

> Anthropic / Claude models: the repo ships a dedicated **`claude-api`** skill
> with current model IDs, pricing, and migration notes — prefer it for Claude
> specifics, and use this skill's step E only for the broader "what shipped
> since" stream.

## Steering

- **Report, don't upgrade.** Research and summarize only; never edit manifests,
  bump versions, or run installers.
- **Programmatic over manual.** If you catch yourself about to read a rendered
  registry page or a docs site to find a version or a changelog, stop and use
  the matching recipe instead. Web fetch is for prose, not data.
- **Cover the whole span.** Changes accumulate across every intermediate version
  (software) or the full window (service) — not just the endpoints.
- **Classification is heuristic.** A `feat:`/`fix:`/`!` prefix or a
  `BREAKING CHANGE:` trailer is a signal, not ground truth; read the actual
  diff for anything load-bearing.
- **State coverage honestly.** Name the sources that ran and the ones that were
  missing. A summary built from one source of five is not researched — say so.
- **Services have no semver — don't invent one.** For a stream target, anchor on
  dates, not version numbers, and be explicit about the window covered. A
  vendor feed shows what was *announced*, not always what is *GA in your region/
  account* — flag that distinction when it matters.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/detect.sh` | No-network enumeration of the repo's declared dependencies + pinned versions across ecosystems (npm/pnpm/yarn, pip/poetry/uv, cargo, go, rubygems, composer). Use to pick a target when none is named. Optional arg: project dir (default `.`). |

For everything network-facing (latest version, repo URL, releases, changelog,
commit log, service feeds/APIs) use the commands in `references/recipes.md` —
documented so they stay deterministic without hard-coding one rigid pipeline.
