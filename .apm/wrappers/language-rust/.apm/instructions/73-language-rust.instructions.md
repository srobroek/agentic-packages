---
description: Rust steering.
applyTo: "**/*.rs"
---

# Rust

Keep crates domain-driven. Keep pure library crates free of runtime/framework
dependencies unless the crate's purpose is explicitly integration or platform
glue.

For cargo workspace, error handling, CLI, HTTP, async, and desktop defaults, use
the always-loaded toolchain defaults and the project setup skill.
