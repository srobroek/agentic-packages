---
name: adr
description: Register and author an architecture decision record. Use when a hard-to-reverse choice is made, when superseding a record, or when `adrs doctor` reports findings.
---

# Architecture decision records

Registers a decision the moment it lands and discharges it into a MADR file. The
`decision` bead is the live record; the file is the durable one. Both exist so a
choice cannot be lost between being made and being written.

Requires the `adrs` binary (`brew install adrs` or `cargo install adrs`). Without it
the format and path still apply, and the gate is skipped rather than blocking.

## When to use

- A choice is hard to reverse, constrains later work, or crosses a package,
  contract, or agent boundary.
- An accepted decision is being replaced, which is a supersede rather than an edit.
- `adrs doctor` reports findings and they need resolving.
- Someone asks "why is it built this way", and the answer is not written down.

Do not use for a choice a later commit can undo at no cost, or a naming preference.

## Registering, while the work happens

1. Create the `decision` bead before the choice affects anything else. Fields and
   link types are in the beads carrier doctrine: `decision_key`, `decision_owner`,
   `design`, `acceptance`, `decision_disposition`.
2. Link affected work `relates-to` and evidence-supplying work `validates`. Both are
   non-blocking.
3. Leave the disposition `proposed` while the choice is still open. No file yet.
4. On `accepted`, write the file, cite its path on the bead, and close the bead with
   a disposition-specific reason.

A decision that never reaches `accepted` still leaves a bead explaining what was
weighed and why nothing was chosen, which is itself worth having.

## Authoring

```bash
adrs new --no-edit --format madr "Adopt X for Y"   # --no-edit is mandatory in scripts
adrs list
adrs doctor                                        # exit 0; 1 with --warnings-as-errors
adrs search <term>
```

`--no-edit` matters: without it the command spawns `$EDITOR` and blocks, and
`EDITOR=true` does not help. The file is created either way, so a blocked run leaves
a half-finished record behind.

Write the sections in this order, because each constrains the next:

1. **Context and Problem Statement** — the forces that made a choice necessary.
   Not a restatement of the decision.
2. **Decision Drivers** — the criteria options are judged against, written before
   the winner is known.
3. **Considered Options** — every option genuinely weighed. A straw option added to
   flatter the winner makes the record worthless.
4. **Decision Outcome** — the choice in one sentence, and which driver settled it.
5. **Consequences** — including what becomes harder. A record with no cost was not a
   decision between real alternatives.
6. **Confirmation** — the observable check that verifies compliance.

## Superseding

Never edit an accepted record to change its decision. Write a new record, mark the
old one superseded, and name the successor in both. The old record stays readable:
its value is that it explains what was believed at the time.

The roadmap is the forward-looking document and is re-sequenced as plans change. An
ADR is point-in-time and append-only. When a decision changes, the roadmap moves and
a new ADR records why.

## Conventions

| Property | Value |
|---|---|
| Format | MADR 4.0.0 (`full`, `minimal`, `bare`, `bare-minimal` variants) |
| Path | `docs/adr/NNNN-kebab-title.md` |
| Directory config | `.adr-dir` holding `docs/adr`; the tool defaults to `doc/adr` |
| Numbering | sequential, never reused |
| Gate | `adrs doctor`, wired as a pre-commit hook by the scaffold layer |

Rule findings carry an ID and a location, for example
`warning: [ADR014] Section '## Context and Problem Statement' appears to be empty
[docs/adr/0002-....md:3]`. Suppress a rule with `--ignore ADR014` or the
`[doctor].ignore` list in `adrs.toml`, and say why in the config rather than in a
commit message.
