> **DEPRECATED** — This package is superseded by
> [srobroek/speckit-gate](https://github.com/srobroek/speckit-gate).
> It is kept for existing installs and will receive no new features.
> New projects should use `speckit-gate` via the `speckit-setup` skill
> (which provisions `uvx speckit-gate init/compile/install` automatically).

# speckit-dag-hooks

Opt-in enforcement hooks for the SpecKit DAG: hard-block out-of-order or
precondition-violating `/speckit.*` commands via the speckit-dag dispatcher.
Opinionated mandatory-gating — requires the `speckit` package (which ships the
dispatcher) to be installed.

## Migration

[speckit-gate](https://github.com/srobroek/speckit-gate) is a
`gates.yaml`-driven generalisation of this package. It provides the same
enforcement semantics with a richer engine (init/compile/install/dispatch), a
Claude adapter that merges hooks into `.claude/settings.json`, and a scan that
discovers installed commands (built-ins + extensions). The `speckit-setup` skill
in the `speckit` APM package provisions speckit-gate automatically.
