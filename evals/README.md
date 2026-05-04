# Agent Model Evals

This directory contains one generated eval record per migrated or candidate agent.

`agent-model-evals.jsonl` is designed to compare the recommended model against plausible alternatives before locking metadata into APM packages. Each record contains:

- the recommended model and reasoning effort
- candidate models to run against the same fixture
- expected tool and sandbox behavior
- a scenario prompt shaped by the agent prompt and category
- a common scoring rubric

Run strategy:

1. For each record, run the scenario with every `candidate_models` entry using the same agent prompt.
2. Capture trace, commands, file diffs, and final answer.
3. Score `primary_accuracy_checks` plus the rubric fields.
4. Keep the cheapest/fastest model only if it matches or beats the recommended model on role adherence, correctness, tool routing, and verification quality.

These are model-selection tests, not final task fixtures. The next migration step should add concrete fixture repos/data packets for high-risk agents first: `coder`, `speckit-implement-task`, `pr-reviewer`, `api-designer`, `ai-engineer`, data agents, security agents, Terraform agents, and frontend/UI agents.
