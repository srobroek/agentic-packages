---
description: Go steering.
applyTo: "**/*.go"
---

# Go

Use `cmd/` for binaries and `internal/` for non-exported implementation code.
Keep packages small and explicit. Avoid framework imports in domain packages.

For `urfave/cli`, `koanf`, routing, RPC, and SQL tooling defaults, use the
always-loaded toolchain defaults and the project setup skill.
