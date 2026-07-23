# Agentic-Packages Constitution

## Core Principles

### I. Self-Contained Packages
Each package under `packages/` is independently installable, testable, and
releasable. No package reaches into another's internals at runtime.

### II. Generated Artifacts Are Not Hand-Edited
Files produced by `apm compile`, `inject-agent-models.py`, `render-docs.py`, or
`build-native-plugins.py` are regenerated on every build. Edit the source, not
the output.

### III. Hooks Fail Open
PreToolUse guards emit `allow` + advisory or `deny` with a self-correction
message. No guard emits `ask` (blocks autonomous agents). Catastrophic-only
operations receive `deny`; everything else is non-blocking.

### IV. Conventional Commits and Release-Please
All commits follow `type(scope): message`. Release-please reads commit history
to produce changelogs and version bumps per package.

## Governance

The constitution applies to all contributions. Amendments require a versioned
commit updating this file.

**Version**: 1.0.0 | **Ratified**: 2026-07-23
