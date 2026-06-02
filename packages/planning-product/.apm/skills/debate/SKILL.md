---
name: debate
description: Use for deep tradeoff analysis on architectural decisions, technology choices, and feature proposals. Tests an idea from both sides before recommending a path. Agents may suggest this when the user faces a non-trivial decision.
---

# Debate

Analyze and debate: **$ARGUMENTS**

Always start by lightly grilling the user (use the `grill-me` skill) to sharpen the topic: what is the decision, proposed approach, boundaries, constraints, and context. A well-formed topic makes a better debate.

## Process

### Phase 0: Context questions

Ask these THREE questions in a single call (they render as UI menus):

1. **Decision type**: Feature proposal, Architecture decision, Technology choice, or Process change
2. **Context scope**: Isolated (clean-room, no codebase) or Full context (codebase-aware)
3. **Knowledge source**: LLM knowledge only (fast) or Research with subagents (thorough, slower)

### Phase 1: Decomposition

Break the topic into 4-6 investigation angles tailored to the decision type. Each type has its own angle set (user need, implementation complexity, simpler alternatives, reversibility, operational complexity, exit strategy, etc.).

### Phase 2: Research (conditional)

If "Research with subagents":
- Launch 3-5 parallel subagents, one per angle
- Full context: use **Explore** agents -- they examine local code
- Isolated: use **general-purpose** agents -- they must NOT reference local code or conversation history

If "LLM knowledge only": skip to Phase 3.

### Phase 3: Main analysis

Synthesize into structured sections:
- **Problem Validation** -- is the problem real and worth solving?
- **Pros** -- with evidence strength (strong / moderate / weak)
- **Cons** -- with severity (blocker / major / minor)
- **Tradeoffs** -- what you gain vs. what you give up
- **Alternatives** -- "Do nothing" is always first; "Simplest viable approach" is always second
- **Overengineering Assessment** -- answer these 5 questions:
  1. Would doing nothing solve the problem adequately?
  2. What is the simplest thing that could possibly work?
  3. Which part of this solution is solving a problem we don't have yet?
  4. If we had to ship this in 48 hours, what would we cut?
  5. How hard is this to undo if we're wrong?
- **Reversibility** -- one-way door, two-way door, or reversible with cost

### Phase 4: Devil's advocate

Launch a single **adversarial-challenger** subagent with ONLY the finished Phase 3 analysis (never raw research). It must:
- Challenge every pro
- Deepen every con
- Check for biases: survivorship, sunk cost, herd mentality, optimism, complexity, resume-driven
- Identify unstated assumptions
- Name the single strongest argument against the proposal

### Phase 5: Synthesis

Merge the main analysis with the devil's advocate critique:
- Incorporate valid criticisms; note deflected ones with reasoning
- Calibrate confidence: High (75-95%), Medium (40-74%), Low (10-39%)
- Produce a conditional verdict: "This makes sense IF... It does NOT make sense IF..."

Then offer interactive debate rounds, capped at 3. Each round genuinely updates the assessment. After round 3: "We've explored this from three additional angles. Here's where things stand. Want to continue or call it?"

### Phase 6: Save

Save the report to `research/debate-<slug>.md` relative to the project root. Only skip if the user explicitly declines.

## Workflow turbo-path (optional, Claude only)

The prose Process above is the default. IF dynamic workflows are enabled (the user included the
"workflow" keyword, ultracode is on, or they asked for orchestration), the research fan-out and
devil's advocate become a single Workflow instead of manual subagent launches. Same phases, same
outputs -- only the orchestration moves into a script. Workflows are a Claude-only feature; where
they are unavailable, follow the prose Process.

Shape (author the script inline; do not vendor it):

- **Phase 0-1 stay in the main thread** -- context questions and angle decomposition need the user.
- **Phase 2 (research):** `parallel()` one `agent()` per angle.
  - `agentType: 'Explore'` when scope is Full context; `agentType: 'general-purpose'` when Isolated
    (and instruct it NOT to reference local code or history).
  - `model: 'sonnet'`, `effort: 'medium'` per angle (breadth, not depth).
  - Barrier on all angles before synthesis.
- **Phase 3 synthesis** in the main thread (or one `agent` at `effort: 'high'`).
- **Phase 4 (devil's advocate):** one `agent()` with `agentType: 'adversarial-challenger'`,
  `effort: 'xhigh'`, given ONLY the finished Phase 3 analysis (never the raw research) -- preserving
  the structural isolation rule below.
- **Phase 5-6** (merge, verdict, save) in the main thread.

Per-agent `model`/`effort`/`agentType` are set at the `agent()` call. `adversarial-challenger`
resolves to the existing agent definition -- do not duplicate it. First run shows a one-time
approval prompt. If workflows are unavailable, fall back to the prose Process -- behavior is
identical, only slower.

## Rules

- YAGNI is the default stance. Burden of proof is on complexity.
- "Do nothing" is mandatory and must be taken seriously.
- Devil's advocate is structurally isolated from raw research to prevent shared reasoning biases.
- Verdict is ALWAYS conditional, never binary.
- Overengineering assessment must be substantive, not perfunctory.
