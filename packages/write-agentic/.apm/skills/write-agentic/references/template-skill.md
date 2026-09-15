Content policy: apply the shared rules in the parent `SKILL.md`; do not duplicate them in generated assets.
# Skill Template

Copy the template. Fill required sections. Delete unused sections. Target <=60 lines. Move overflow to `references/`.

```markdown
---
name: <kebab-name>
description: <max 25 words. What it does plus concrete trigger phrases. Third person. The trigger surface only.>
---

# <Title>

TRIGGER
+ <user phrase or observable repo condition>
+ <...>
- <near-miss that must NOT trigger> -> <where it goes instead>

GATES  (only if the skill must stop before acting)
ASK <decision only the user can make - one line each>

## Workflow

1. <imperative step. Reference scripts as `scripts/x.sh`; state what it emits>
2. <...> -> <observable success condition>
3. LOAD references/<topic>.md <only when: named condition>

## Rules

MUST <hard constraint - safety or correctness>
DEFAULT <default - override needs a stated reason>
NOT <known failure mode or trap, one line>

OUTPUT  (only if the skill produces a report)
L1 <verdict/summary line shape>
   <section> - only if non-empty
CAP <N>w clean - <M>w with findings
```

Checks before lint:

- every step is verifiable
- no hedge in a MUST, DEFAULT, or NOT line
- the description has a phrase the user would actually type
- scripts own deterministic work such as parsing, counting, and validation
- prose never re-does script work
