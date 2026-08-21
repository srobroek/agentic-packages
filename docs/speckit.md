# SpecKit orchestration

The SpecKit workflow lives in its own repository:
**[srobroek/speckit-conductor](https://github.com/srobroek/speckit-conductor)**.

It was three packages here (`speckit`, `speckit-beads`, `steering-speckit`), merged
into one and then extracted. This repository no longer ships it.

## Install

```bash
apm install srobroek/speckit-conductor --target claude,codex
```

Or as a dependency:

```yaml
dependencies:
  apm:
    - git: srobroek/speckit-conductor
      ref: '>=3.0.0 <4.0.0'
      targets: [claude, codex]
```

APM install is the supported path. `apm pack` synthesises a `plugin.json` with no
`dependencies` field, and a Codex plugin manifest has no such field at all, so a
native `/plugin` install resolves that package's skills and hooks but none of its
dependencies. APM composes the full graph; a native install does not.

## What it still depends on from here

Two packages, resolved from published tags rather than vendored:

| Package | Supplies |
|---|---|
| [`beads`](../packages/beads) | the `bd` workflow engine the phase DAG is poured into |
| [`adr-as-beads`](../packages/adr-as-beads) | decisions as `decision` beads, rendered to `docs/adr/` |

A copy across a repository boundary has no checker behind it, and a drifted guard
script is not recoverable the way a drifted generated file is. So `speckit-conductor`
references these rather than carrying them, and a breaking change here needs a
release before that repository can adopt it.

## Why it moved

The workflow had grown past one package: formulas planned at three depths, bonded
loop formulas for the review and iterate cycles, four agents, two skills, a Python
guard with tests, and a 432-line setup script. It also releases on its own rhythm,
which a monorepo release train serialises for no benefit.

The same reasoning extracted `project-setup` earlier, and this followed that
precedent: merge first, migrate the dependents, then extract, so no consumer sees a
package renamed and relocated in one step.
