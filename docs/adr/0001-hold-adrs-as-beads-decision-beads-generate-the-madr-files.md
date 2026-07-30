<!-- Generated from a beads decision bead. Edit the bead, not this file:
     bd show adr-1 -->
---
number: 1
title: Hold ADRs as beads decision beads, generate the MADR files
status: accepted
date: 2026-07-29
bead: adr-1
---

# Hold ADRs as beads decision beads, generate the MADR files

## Considered Options

Keep `adrs` for the file and beads for the lifecycle, rejected because the two-writer split is the defect. A CI gate rendering from `bd dolt pull`, rejected because the ref is not commit-pinned and the doctrine forbids sync from lifecycle hooks. A banner in the generated file instead of a guard, rejected because a banner cannot prevent the edit it warns about. An open sentinel task or blocking epic to keep decisions out of `bd ready`, rejected because a decision bead cannot be blocked by an epic and an accepted epic blocker is silently ignored; `bd defer` does it with one field.

## Decision Outcome

Architecture decision records are held as beads `decision` beads. A pre-commit hook projects every closed decision into `docs/adr/NNNN-title.md`. The `adrs` binary is dropped.

### Rationale

Every MADR section maps onto a bead field, so `adrs` was writing markdown from data beads already held, and two records for one decision is what let a file and its bead disagree about whether a decision still stood. Enforcement is native and stronger: `bd lint` requires a rejected alternative and exits 1, which `adrs doctor` could not do. Pre-commit rather than CI because the bead lives in the local unpushed Dolt store and `refs/dolt/data` is versioned independently of git commits.

## More Information

Every MADR section maps onto a bead field, so the adrs binary was writing markdown from data beads already held. Holding the record twice is what let a file and its bead disagree about whether a decision still stood. bd lint enforces the rejected-alternative rule that adrs doctor could not: a single-option ADR was info severity, which --warnings-as-errors does not gate, and deleting the Considered Options heading drew nothing at all. Measured: bd export is lossless and costs ~0.45s for the whole database, where bd list --type decision --json omits design/notes/dependencies/spec_id and per-bead bd show costs ~0.45s each. refs/dolt/data is a blob store versioned independently of git commits (measured a day out of step with main), so CI cannot pin the database to the commit under test; the beads doctrine separately forbids bd dolt pull from any lifecycle hook.

Verified against bd 1.1.2 and adrs 0.10.1. bd lint's help text omits the decision type but the rules fire: a sectionless decision draws three warnings and exits 1. bd supersede puts the supersedes edge on the OLD bead pointing at the new one. bd defer with no --until is indefinite and status-based. A decision bead cannot be blocked by an epic (tasks can only block other tasks), though a plain task blocked-by the same epic IS accepted and then silently ignored by bd ready.
