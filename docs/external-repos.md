# External repositories

The catalog carries no external entries right now: every plugin lives under
[`packages/`](../packages/) and is vendored into this repo.

The mechanism remains supported. A marketplace entry may name a whole plugin kept
in its **own git repository**, which `apm` then **fetches from that repo on
install** rather than reading from `packages/`. Such an entry pins its `ref` to a
tag or commit SHA for reproducible resolution, because `apm pack` rejects mutable
branch refs. Add one by giving the `marketplace:` entry in `apm.yml` a `source:`
and `ref:` instead of a local path; the table below is generated from those
entries, so it fills in on its own.

<!-- BEGIN:external-repos -->
| Plugin | Category | Pinned ref | Tags |
| --- | --- | --- | --- |
<!-- END:external-repos -->

---

See also: [bundles](bundles.md) · [skills](skills.md) · [agents](agents.md) · [steering](steering.md) · [hooks and MCP](hooks-and-mcp.md) · [SpecKit](speckit.md)
