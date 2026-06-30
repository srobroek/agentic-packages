---
name: goal-writer
description: Turn a vague goal prompt into a structured, actionable goal -- outcomes, concrete results, measurable KPIs, validation, and verifiable exit conditions -- saved as a context doc, then emit a self-sufficient /goal block (goal + work-definition reference + constraints + AND-joined exit conditions) to paste into the /goal command. Use when the user asks to structure a goal, turn a vague goal/objective into an actionable one, make a goal measurable, or prep text for /goal. NOT for setting a /goal condition already written (use /goal directly), PRDs or issues (use to-prd / to-issues), or open-ended planning (use debate).
---

# Goal Writer

Convert a vague goal into a structured, actionable one through a relentless
interview, save it as a context doc, then emit a self-sufficient `/goal` block
that references the doc and tests done-ness via AND-joined exit conditions.

## Workflow

1. Read the user's goal prompt. Classify each template field (see below) as
   **strong** (present and passes its bar) or a **gap** (absent or below bar).
2. Grill the gaps, one question at a time (see Interview). Skip strong fields --
   do not re-litigate a sharp answer.
3. Compose the full goal doc from `references/template.md`, enforcing the chain
   **Results -> Outcomes -> KPIs -> Validation -> Exit conditions**.
4. Show the composed doc in chat for review; apply any adjustments the user asks
   for.
5. **Always** persist the doc via `scripts/new-goal.py` (see Persistence) -- the
   `/goal` block references it by absolute path, so the file is a hard
   dependency, not an opt-in. Capture the path the script prints.
6. Emit the `/goal` block (see Output) using that real path, so it can be pasted
   immediately.

## Interview

Interview the user relentlessly about every gap until the goal is sharp. Walk
the field tree, resolving dependencies one-by-one. Ask one question at a time
and wait for the answer -- multiple questions at once is bewildering. For each
question, provide your recommended answer. If a question can be answered by
exploring the repo or prompt instead of asking, do that.

Treat a field as a gap when it is missing **or** below its quality bar:

- **Outcomes** -- an observable change in behavior or state, not a task or
  artifact. (An artifact belongs in Results.)
- **Results** -- a concrete deliverable that exists when done. (A behavior
  change belongs in Outcomes.)
- **KPIs** -- each has an acceptance **band** plus a target and a measurement
  method. Bands are first-class; the exact target may firm up during execution
  as long as the band bounds it. If genuinely unmeasurable yet, allow
  `target: TBD -- proxy: <observable signal>`, never a bare vague metric.
- **Exit conditions** -- each is an independently verifiable predicate, authored
  so they can be AND-joined into one completion condition.

Push-back rules: a "Result" that is really a behavior change -> move to Outcomes;
an "Outcome" that is really an artifact -> move to Results; an Outcome with no
KPI -> attach one or it is not a tracked outcome.

## Output

Emit one `/goal` block. It must be self-sufficient to *steer* (the across-turn
agent loses chat/compacted context) and sharp to *test*. Four parts, in order:

1. **Goal** -- the one-sentence destination.
2. **Work definition + doc reference** -- the absolute path to the saved doc,
   framed as actionable: the doc's **Results** and **Exit conditions** are the
   work to execute (build the task plan from them at execution time); re-read it
   for diagnosis, bands, and constraints. The doc is the durable backing store
   the line points at -- not just "context to read."
3. **Constraints** -- the few non-negotiables that must survive compaction
   (measurement protocol, scope boundaries, key decisions).
4. **`Done when:`** -- the **mechanical AND-join** of the verifiable exit
   conditions: `Done when: (1) <exit cond 1> AND (2) <exit cond 2> AND ...`,
   joined verbatim. No distillation. This is the part the evaluator tests, so
   every term must be independently verifiable.

The full template (`references/template.md`) is the saved doc, not pasted into
`/goal`. Do NOT paste Outcomes/KPIs (with TBD targets) into the completion
condition -- aspirational prose is not a testable done-check.

## Persistence

Run `scripts/new-goal.py` to write the context doc to
`~/.local/state/agentic-tools/goals/<project-slug>__<goal-slug>.md` with
user-private permissions. Goals are kept (not overwritten) -- a project has many
goals over time; the goal-slug distinguishes them. The doc is ephemeral local
state, never committed. Pass `--title` and the composed body on stdin; see the
script's `--help`. If the script is unavailable, create the same file contract
manually: that directory, `<project-slug>__<goal-slug>.md`, the frontmatter and
body from `references/template.md`, mode `0600`.

## Rules

- Review with the user before saving (step 4), but always save (step 5) -- the
  `/goal` block depends on the file path.
- Do not invent KPI targets the user did not give -- use the TBD-with-proxy form.
- Keep `Done when:` a literal AND-join; if it grows unwieldy, that signals too
  many exit conditions -- surface that in the interview, do not summarize.
- Do not store secrets or credential values in the goal doc.

## References

When composing the goal doc, LOAD `references/template.md` for the section
contract, field bars, and the worked example.
