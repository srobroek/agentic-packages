# Beads Semantic Audit and Reporting

AUDIT
MUST Rely on Beads' automatic audit for ordinary status, assignee, priority,
  and close field changes; do not duplicate those as explicit interactions.
MUST Add explicit `bd audit record` entries for semantic events: assignment
  decision, blocked handoff, report, review verdict, requested changes,
  approval, conflict, merge outcome, human decision, and failure.
DEFAULT Comments hold concise human-readable reasoning and artifact paths;
  audit entries hold machine-readable actor, issue, event, and outcome fields.
NOT `bd audit` as the task database: interactions augment issues, comments,
  gates, and artifacts and do not replace them.

REPORTING
DEFAULT Use a read-only on-demand reporter for recovery, requested summaries,
  and close-out; do not keep a reporter alive between requests.
MUST Give the reporter issue lists, `bd show` and comments, gate state,
  merge-slot state, `.beads/interactions.jsonl`, and referenced artifacts.
DEFAULT Reporter model and cost routing follows the repository's delegation
  policy; the reporter never invents missing state or mutates the run.
