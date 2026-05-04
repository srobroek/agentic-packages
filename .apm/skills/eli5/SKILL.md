---
name: eli5
description: Use when a topic needs explanation at multiple difficulty levels.
---

# ELI5

Use this skill to explain a topic at one or more depth levels.

## Workflow

1. Ask what level(s) the user wants if not specified.
2. Decide whether the topic is stable enough to explain directly or needs research first.
3. Generate only the requested levels -- do not always produce all four.
4. Keep each level genuinely calibrated to its audience.
5. Make higher levels add nuance, not just length.

## Default Levels

| Level | Audience | Approach |
|-------|----------|----------|
| beginner | No prior knowledge | Concrete analogies, no jargon |
| generalist | Broadly technical | Standard terminology, practical framing |
| practitioner | Domain experience | Implementation details, tradeoffs |
| expert | Deep specialist | Edge cases, formal properties, open problems |

## Steering

- Prefer accuracy over cute analogies.
- Do not flatten meaningful uncertainty just to simplify.
- If the user asks for one level only, give one level only.
- If the topic is current or disputed, pair this with the research skill first.
