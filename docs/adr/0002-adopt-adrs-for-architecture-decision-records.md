---
number: 2
title: Adopt adrs for architecture decision records
status: accepted
date: 2026-07-29
---

# Adopt adrs for architecture decision records

## Context and Problem Statement

`steering-speckit` required MADR records under `docs/adr/` and nothing implemented
that requirement: no format guidance, no tooling, no gate. Dropping the `memory-md`
extension removed the only installed thing that captured durable decisions at all,
as prose in `DECISIONS.md` rather than ADR format, so the rule had nothing behind it
in either direction.

A survey of the 142-entry spec-kit community catalog found no dedicated ADR
extension, confirming an earlier finding made against 121 entries. The choice was
therefore between building one and adopting an external tool.

## Decision Drivers

* Deterministic validation: a record's shape should be checkable without an LLM.
* Scriptable from a hook, a formula step, and CI, with a usable exit code.
* MADR 4.0.0, because that is the format the existing steering already named.
* Maintained, since an abandoned tool becomes our maintenance burden.
* No per-session context cost.

## Considered Options

* `adrs` (joshrotenberg/adrs), a Rust CLI
* `adr/adr-manager`, from the official `adr` organisation
* `adr-kit` (rvdbreemen/adr-kit)
* Build a `speckit-adr` extension, per the design in `speckit-adr-design`
* `npryce/adr-tools`, the historic standard

## Decision Outcome

Chosen: **`adrs`**, because it is the only maintained option with both a MADR-native
CLI and a deterministic validator returning a usable exit code, which is what the
scriptability driver demanded.

### Consequences

* A binary dependency enters the toolchain. A repository without `adrs` on PATH gets
  no gate, so the steering degrades to advisory rather than assuming presence.
* `adrs new` blocks on `$EDITOR` unless `--no-edit` is passed, and `EDITOR=true` does
  not help. Every documented invocation carries the flag; a hook that forgets it hangs.
* Setup is `adrs init docs/adr`, not a hand-written `.adr-dir`. Writing that file
  alone leaves `adrs new` failing with "ADR directory not found", and a later bare
  `adrs init` silently rewrites it to the tool's `doc/adr` default.
* `adrs doctor` does NOT catch the two rules that make a record worth writing. A
  single-option ADR is `info` severity, which `--warnings-as-errors` does not gate,
  and an ADR with no `## Considered Options` heading draws nothing. Whether a real
  alternative was rejected, and whether a consequence names a cost, stay reviewer's
  work.
* Its release cadence is not ours. Its latest GitHub release ships zero assets, so a
  `latest-release:` style install would silently fetch nothing.

### Confirmation

`adrs doctor --warnings-as-errors` exits 1 on a placeholder record and 0 on a filled
one, verified against 0.10.1. This file is the repository's own first record, so the
documented setup is exercised rather than asserted.

## Pros and Cons of the Options

### `adrs`

* Good: MADR 4.0.0 with all four template variants, matching the required format.
* Good: `adrs doctor` is rule-based with IDs and `file:line`, and
  `--warnings-as-errors` gives a real exit code.
* Good: `adr-tools` compatible, so an existing repository works unchanged.
* Good: a single cross-platform binary with no runtime.
* Neutral: ships an optional MCP server, deliberately unwired because the CLI covers
  every operation without per-session tool schemas.
* Bad: 105 stars and one maintainer.

### `adr/adr-manager`

* Good: 159 stars, official `adr` organisation, MADR-native.
* Bad: browser-only with GitHub OAuth, no CLI. Unusable from an agent, a hook, or CI,
  which ruled it out on the scriptability driver alone.

### `adr-kit`

* Good: production-grade features including supersession and quality scoring.
* Bad: a Claude Code plugin plus CLI plus MCP server where one binary suffices, at
  4 stars.

### Build `speckit-adr`

* Good: exactly the desired shape, and the design already existed.
* Bad: unnecessary once a maintained binary covers it, and it would tie ADRs to
  SpecKit when decisions get made in repositories that never touch SpecKit.

### `npryce/adr-tools`

* Good: the historic standard at 5,578 stars.
* Bad: last pushed 2024-04, Bash, and Nygard format rather than MADR.

## More Information

MADR itself (`adr/madr`, 2,357 stars) ships only four markdown templates and no
tooling; `adrs` exposes exactly those four, so adopting it changed no format.

`docguard` was considered for the adjacent problem of documentation drift and
rejected: its drift validators all report `N/A` without adopting its
`docs-canonical/` methodology, verified against this repository.
