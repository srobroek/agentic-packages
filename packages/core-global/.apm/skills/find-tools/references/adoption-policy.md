# Adoption Policy

## Decisions

- `Use existing`: already available in the project or a registered marketplace.
- `Adopt`: add to a resolved checkout of `srobroek/agentic-packages` so future
  projects can install it as an APM package.
- `Trial`: useful but risky or unclear; test temporarily without changing
  project source or the first-party marketplace.
- `Reject`: unsafe, stale, unlicensed, duplicate, incompatible, or too weak.
- `Build`: no good existing capability fits.

## Project-Only Adoption

Use when the tool is useful for one repo, not yet generally proven, or already
APM-installable from a selected marketplace.

1. Inspect the project `apm.yml`.
2. Prefer `apm install <package>@<marketplace>`.
3. Run relevant install/compile/patch checks.
4. Do not edit the first-party marketplace checkout unless the user asks to
   promote it.

## Marketplace Adoption

Use when the tool should become reusable, needs metadata, needs a wrapper, or
requires local policy before project use.

1. Resolve a local checkout whose git remote matches
   `srobroek/agentic-packages`; if none exists, clone it only with user approval
   or report the missing checkout.
2. Edit that checkout, not generated runtime folders.
3. Add the source as an external package, git subdir, wrapper, or intentional
   fork/vendor.
4. Update `THIRD_PARTY.md` with source, license, package shape, version policy,
   verification result, and local policy.
5. Rebuild and validate marketplace metadata.
6. Smoke-test install when network and approvals allow.

## Quality Bar

Evaluate serious candidates for:

- popularity: installs, downloads, stars, usage, reviews
- maintenance: recent commits/releases, maintainer identity, issue response
- code quality: clear source, tests/CI, schemas, typed config, error handling
- security: license, secrets, destructive permissions, telemetry, install path
- fit: overlap, APM compatibility, local-vs-hosted tradeoff, simplicity

Reject prompt-only wrappers around tools already exposed cleanly, broad secret
requirements without strong reason, hidden install scripts, missing licenses, or
duplicates of a better maintained installed package.
