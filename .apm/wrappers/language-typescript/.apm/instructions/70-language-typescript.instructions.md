---
description: TypeScript and JavaScript steering.
applyTo: "**/*.{ts,tsx,js,jsx,mts,cts}"
---

# TypeScript

Keep modules typed and explicit. Use runtime validation at external boundaries,
not deep inside pure domain code. Keep generated clients/types in consumer
packages or dedicated generated packages, not in source-of-truth contract
folders.

For package managers, frameworks, and test runners, use the always-loaded
toolchain defaults and the project setup skill.
