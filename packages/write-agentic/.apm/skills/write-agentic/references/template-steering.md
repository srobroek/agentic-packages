Content policy: apply the shared rules in the parent `SKILL.md`; do not duplicate them in generated assets.
# Steering Template

Two files are used. The pointer is always loaded. The context loads on demand.

## Pointer -- `.apm/instructions/NN-<name>.instructions.md`

```markdown
---
description: <max 15 words>
# Omit applyTo for unconditional instructions compiled into global context.
applyTo: "<optional glob - include only for genuinely file-scoped rules>"
---

For <topic list, <=12 words>, read [<name>](../context/<name>.context.md).
```

NN prefix = load order band:

- 0x meta/style
- 1x toolchain
- 2x-3x structure
- 4x workflow
- 5x domain
- 7x language/docs
- 8x tools

## Context -- `.apm/context/<name>.context.md`

```markdown
# <Topic>

<AREA-1>
MUST <hard rule>
DEFAULT <default>

<AREA-2>
ASK <confirm with user>
| situation | choice |
|---|---|
| <observable condition> | <decision> |
```

## Rules

MUST Include only these items:

- decisions
- edge cases

NOT Explain well-known tools.
NOT Explain why a choice is right.

MUST Keep one home per fact.
If another steering file owns a fact, delegate with one line: "see steering-x".
NOT Restate that fact.

MUST Start every rule with one keyword:

- MUST
- DEFAULT
- ASK
- NOT

MUST Follow the keyword with an observable condition.

DEFAULT Keep context to <=50 lines. Keep the pointer to <=6 lines.
DEFAULT Omit `applyTo` for unconditional instructions.
DEFAULT Scope file-specific rules with the narrowest truthful glob.

NOT Include these forms:

- rationale paragraphs
- aphorisms
- scope disclaimers
- command catalogs.
