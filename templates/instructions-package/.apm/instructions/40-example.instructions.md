---
description: One-line summary shown to the model about when this rule applies.
applyTo: "{services/**,functions/**,workers/**}"
---

Keep the always-on instruction body SMALL. Its job is to point at the heavier
context file, not to inline everything -- that keeps the steering cheap until
it is actually needed.

For <the situations matched by applyTo>, read
[example context](../context/example.context.md).
