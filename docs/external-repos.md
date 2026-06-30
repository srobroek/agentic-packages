# External repositories

Most of this marketplace's catalog lives under [`packages/`](../packages/), but some entries are whole plugins maintained in their **own git repositories** and referenced here so they stay discoverable from this catalog.

Unlike local packages, these are **fetched from their source repo on install** rather than vendored into `packages/`. Their `ref` is therefore pinned to a tag or commit SHA for reproducible resolution (`apm pack` rejects mutable branch refs). See each source repo for full documentation, issues, and releases.

<!-- BEGIN:external-repos -->
| Plugin | Category | Pinned ref | Tags |
| --- | --- | --- | --- |
| [`project-setup`](https://github.com/srobroek/project-setup) | project-lifecycle | `project-setup-v0.5.0` | `skill`, `lifecycle`, `bootstrap` |
| [`vibe-hero`](https://github.com/srobroek/vibe-hero) | onboarding | `v0.2.0` | `mcp`, `steering`, `onboarding`, `learning` |
<!-- END:external-repos -->

---

See also: [bundles](bundles.md) · [skills](skills.md) · [agents](agents.md) · [steering](steering.md) · [hooks and MCP](hooks-and-mcp.md) · [SpecKit](speckit.md)
