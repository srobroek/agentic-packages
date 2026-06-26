# Programmatic fetch recipes

The point of these recipes: **never read a rendered web page to discover a
version number, a tag list, or a changelog.** Every fact below has a machine
endpoint that returns small, structured output. Run the command, read a few
lines, move on. Reserve web fetching / browsing for genuine prose (a migration
guide, a blog explaining a breaking change) — not for data you can query.

You decide *which* recipe applies (which ecosystem, which host) and adapt the
commands. They are a cookbook, not a fixed pipeline. All are read-only.

Prereqs, all guardable with `command -v`: `curl`, `jq`, `git`, and optionally
`gh` / `glab` for authenticated host APIs. If one is missing, fall back to the
plain-`curl` variant and say so in the report's Coverage section.

---

## Step A — resolve the current version (no network)

Use `scripts/detect.sh [dir]` to list the repo's declared dependencies as
`ecosystem<TAB>name<TAB>version` (offline, no toolchain). Pick your target's row.

For an exact pinned version, the lockfile beats the manifest range:

```sh
# npm: exact installed version of <pkg>
jq -r '.packages | to_entries[] | select(.key|endswith("node_modules/<pkg>")) | .value.version' package-lock.json | head -1
jq -r '.. | objects | select(.name=="<pkg>") | .version' pnpm-lock.yaml 2>/dev/null   # pnpm v6 lock is YAML; prefer `pnpm why`
# python (uv/poetry export or pip freeze)
grep -i '^<pkg>==' requirements.txt ; pip show <pkg> 2>/dev/null | sed -n 's/^Version: //p'
# cargo
awk '/^name = "<pkg>"/{f=1} f&&/^version/{print;exit}' Cargo.lock
# go
go list -m <module> 2>/dev/null    # prints "<module> vX.Y.Z"
```

If the user already stated the current version, skip this.

---

## Step B — resolve the latest version + source repo (registry APIs)

One `curl | jq` per ecosystem. Each returns the latest version, the version
list, and the upstream repo URL — the three things you need to scope the span.
A descriptive `-A` user-agent is **required** by some registries (crates.io
rejects requests without one).

```sh
UA='whats-new-skill (+https://github.com/srobroek/agentic-packages)'

# npm
curl -fsSL -A "$UA" "https://registry.npmjs.org/<name>" \
  | jq -r '{latest: .["dist-tags"].latest, repo: (.repository.url // .repository),
            deprecated: (.versions[.["dist-tags"].latest].deprecated // "no"),
            versions: (.versions|keys)}'

# pypi
curl -fsSL -A "$UA" "https://pypi.org/pypi/<name>/json" \
  | jq -r '{latest: .info.version,
            repo: (.info.project_urls.Source // .info.project_urls.Repository // .info.home_page),
            yanked: .info.yanked, versions: (.releases|keys)}'

# crates.io  (UA is mandatory)
curl -fsSL -A "$UA" "https://crates.io/api/v1/crates/<name>" \
  | jq -r '{latest: .crate.max_stable_version, repo: .crate.repository,
            versions: [.versions[].num]}'

# rubygems
curl -fsSL -A "$UA" "https://rubygems.org/api/v1/gems/<name>.json" \
  | jq -r '{latest: .version, repo: (.source_code_uri // .homepage_uri)}'
curl -fsSL -A "$UA" "https://rubygems.org/api/v1/versions/<name>.json" | jq -r '[.[].number]'

# packagist (php)  — name is vendor/pkg
curl -fsSL -A "$UA" "https://repo.packagist.org/p2/<vendor>/<pkg>.json" \
  | jq -r --arg n "<vendor>/<pkg>" '{latest: .packages[$n][0].version,
       repo: .packages[$n][0].source.url, abandoned: .packages[$n][0].abandoned,
       versions: [.packages[$n][].version]}'
```

### Go modules

The module path *is* the repo for the common hosts. Honor `GOPROXY`:

```sh
# default proxy
curl -fsSL "https://proxy.golang.org/<module>/@latest"            # -> {"Version": "...","Time": "..."}
curl -fsSL "https://proxy.golang.org/<module>/@v/list"            # newline-separated versions

# GOPROXY=direct (or proxy blocked): list tags straight from the repo
git ls-remote --tags --refs "https://<module-host-path>" \
  | sed -E 's#.*refs/tags/##' | sort -V | tail
```

Normalize a repo URL before using it downstream (registries return `git+`,
`ssh://git@`, scp-style `git@host:owner/repo`, trailing `.git`):

```sh
echo "$REPO" | sed -E 's#^git\+##; s#^ssh://git@#https://#; s#^git://#https://#; s#^git@([^:]+):#https://\1/#; s#\.git$##'
```

---

## Step C — fetch the changes (host-agnostic first, then enrichment)

Order of trust: the project's **migration guide** > **release notes** >
**CHANGELOG** > **commit log**. The first is prose (fetch it as a page); the
last three are queryable. Cover the whole span — changes accumulate across every
intermediate version, not just the endpoints.

### C1 — CHANGELOG + commit log from git (works for ANY host)

This is the host-agnostic core: it needs only `git` and the clone URL from Step
B, so it works for GitHub, GitLab, Bitbucket, Codeberg, sr.ht, or a private
remote identically. Bare + blobless clone keeps it cheap.

```sh
REPO_URL=<from step B>; FROM=<current tag>; TO=<latest tag>
TMP=$(mktemp -d); git clone --bare --filter=blob:none "$REPO_URL" "$TMP/r.git" 2>/dev/null \
  || git clone --bare "$REPO_URL" "$TMP/r.git"
G="git --git-dir=$TMP/r.git"

# tags vary: 1.2.3 / v1.2.3 / pkg-v1.2.3 / pkg@1.2.3. Find the real ones:
$G tag --list | grep -E "(^|[-@/])v?$FROM$"
$G tag --list | grep -E "(^|[-@/])v?$TO$"

# CHANGELOG as tracked at the target tag (no web page, no rendering):
for f in CHANGELOG.md CHANGELOG CHANGES.md HISTORY.md NEWS.md docs/CHANGELOG.md; do
  $G cat-file -e "$TO:$f" 2>/dev/null && { echo "== $f =="; $G show "$TO:$f"; break; }
done

# commit log between tags, classified by conventional-commit prefix:
RANGE="$FROM..$TO"
$G log --no-merges --reverse --pretty='%h %s' "$RANGE" | grep -iE '^[0-9a-f]+ [a-z]+(\(.+\))?!:'  # BREAKING (! marker)
$G log --reverse --pretty='%h %s%n%b' "$RANGE" | grep -iE 'BREAKING CHANGE'                        # BREAKING (body)
$G log --no-merges --reverse --pretty='%h %s' "$RANGE" | grep -iE '^[0-9a-f]+ feat(\(.+\))?!?:'    # features
$G log --no-merges --reverse --pretty='%h %s' "$RANGE" | grep -iE '^[0-9a-f]+ fix(\(.+\))?!?:'     # fixes

rm -rf "$TMP"
```

`!` after the type, or a `BREAKING CHANGE:` body trailer, marks a breaking
change — a *signal*, not ground truth. Read the actual diff for anything
load-bearing: `$G show <sha>` or `$G diff $FROM..$TO -- <path>`.

### C2 — curated release notes (host API enrichment)

Release notes live in the host's API, not in git. Fetch only those whose tag
falls in the span; don't page through everything.

```sh
# GitHub (gh handles auth+rate-limits; else curl with optional token)
gh api "repos/<owner>/<repo>/releases?per_page=100" \
  | jq -r '.[] | select((.tag_name|sub("^v";"")) >= "<FROM>" and (.tag_name|sub("^v";"")) <= "<TO>")
                | "## \(.tag_name) (\(.published_at))\n\(.body)\n"'
# no gh:
curl -fsSL -H "Accept: application/vnd.github+json" \
  ${GITHUB_TOKEN:+-H "Authorization: Bearer $GITHUB_TOKEN"} \
  "https://api.github.com/repos/<owner>/<repo>/releases?per_page=100" | jq -r '...as above...'

# GitLab (project path URL-encoded; PROJECT=owner%2Frepo)
curl -fsSL ${GITLAB_TOKEN:+-H "PRIVATE-TOKEN: $GITLAB_TOKEN"} \
  "https://gitlab.com/api/v4/projects/<PROJECT>/releases?per_page=100" \
  | jq -r '.[] | "## \(.tag_name) (\(.released_at))\n\(.description)\n"'
# glab equivalent: glab api "projects/<PROJECT>/releases"

# Gitea / Codeberg
curl -fsSL "https://codeberg.org/api/v1/repos/<owner>/<repo>/releases" \
  | jq -r '.[] | "## \(.tag_name)\n\(.body)\n"'
```

### C3 — when there's no changelog and no releases

Some projects ship neither. Then the commit log (C1) is the primary source —
classify it and read the breaking/feat commits' diffs directly. Say so in the
report: "no CHANGELOG or releases; summary derived from the commit log."

---

## Step D — prose sources (only when needed)

For a major bump, the migration guide is the payload and it's usually prose, not
data. *Now* a targeted web fetch is justified — fetch the specific
"Upgrading to vN" / "Migration" page, not the docs home. Find its URL from the
repo (`UPGRADING.md`, `MIGRATING.md`, `docs/`) or the release notes' links
rather than searching blind:

```sh
$G ls-tree -r --name-only "$TO" | grep -iE 'migrat|upgrad|breaking'
```

Prefer the project's own guide over third-party blogs; flag blogs as derivative.

---

## Coverage discipline

Always end knowing — and reporting — which of these ran and which didn't:
current version (lockfile vs. range vs. user-supplied), latest (registry),
release notes (present per-tag? or only some?), CHANGELOG (found? at which tag?),
commit log (tags resolved?), migration guide (exists?). A clean-looking summary
built from one source out of five is not the same as a researched upgrade.
