---
name: debate
description: Use for deep tradeoff analysis. Tests an idea from both sides before recommending a path.
---

# Debate

Analyze and debate: **$ARGUMENTS**

## Process

### Phase 0: Context questions

Ask the user THREE questions in a single call:
1. **Decision type**: Feature proposal, Architecture decision, Technology choice, or Process change
2. **Context scope**: Isolated (clean-room, no codebase -- recommended) or Full context (codebase-aware)
3. **Knowledge source**: LLM knowledge only (fast -- recommended) or Research with subagents (thorough, slower)

### Phase 1: Decomposition

Break the topic into 4-6 investigation angles tailored to the decision type. Each type has its own angle set (user need validation, implementation complexity, simpler alternatives, reversibility, operational complexity, exit strategy, etc.).

### Phase 2: Research (conditional)

If user chose "Research with subagents": launch 3-5 parallel subagents (one per angle) to investigate. If "LLM knowledge only": skip to Phase 3.

If user chose "Full context": agents examine local code. If "Isolated": agents must NOT reference local code or conversation history.

### Phase 3: Main analysis

Synthesize into structured sections: Problem Validation, Pros (with evidence strength), Cons (with severity), Tradeoffs, Alternatives, Overengineering Assessment (5 explicit questions), and Reversibility classification.

**Mandatory alternatives**: "Do nothing" is always the first alternative. "Simplest viable approach" is always the second.

### Phase 4: Devil's advocate

Launch a SINGLE independent subagent with ONLY the finished Phase 3 analysis (never raw research). The subagent challenges every pro, deepens every con, checks for biases (survivorship, sunk cost, herd mentality, optimism, complexity, resume-driven), identifies unstated assumptions, and names the single strongest argument against.

### Phase 5: Synthesis

Merge analysis with devil's advocate critique. Incorporate valid criticisms, note deflected ones. Calibrate confidence (High 75-95%, Medium 40-74%, Low 10-39%). Produce conditional verdict: "This makes sense IF... It does NOT make sense IF..."

Then offer interactive debate rounds until the user is satisfied: counterpoints, follow-up angles, or compromise positions. Each round genuinely updates the assessment.

### Phase 6: Save (optional)

Offer to save report to `research/debate-<slug>.md`. Default: don't save.

## Rules

- YAGNI is the default stance. Burden of proof is on complexity.
- "Do nothing" is mandatory and must be taken seriously.
- Devil's advocate is structurally isolated from raw research to prevent shared reasoning biases.
- Verdict is ALWAYS conditional, never binary.
- Overengineering assessment must be substantive, not perfunctory.
