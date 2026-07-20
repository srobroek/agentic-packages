#!/usr/bin/env bash
# speckit-beads-tasks-guard.sh — cross-tool hook with two roles, branched on
# hook_event_name:
#
#   PreToolUse  (Write|Edit|MultiEdit|apply_patch): DENY every write to
#     specs/*/tasks.md when the repo has an active beads workspace. tasks.md is
#     never authored under the beads workflow — task state lives in beads. The
#     deny reason carries the full replacement workflow so the agent
#     self-corrects without a human (hook-guard policy: deny is agent-facing,
#     never "ask").
#
#   PostToolUse (Read): ADVISORY ONLY — when a legacy tasks.md is read, note
#     that live task state is in beads. Reads are never denied (brownfield
#     migration needs them).
#
# Self-gating (never rely on the "if" matcher): exits 0 silently when the
# payload is empty, jq or bd is missing, the target path is not
# specs/*/tasks.md, or the repo has no active beads workspace (bd where fails).
# bash 3.2 / BSD safe.
set -euo pipefail

payload="$(cat 2>/dev/null || true)"
[ -n "$payload" ] || exit 0

# Cheap pre-jq bail: every branch below acts only on a tasks.md target, so if
# the raw payload never mentions tasks.md there is nothing to inspect.
case "$payload" in
  *tasks.md*) ;;
  *) exit 0 ;;
esac

command -v jq >/dev/null 2>&1 || exit 0
command -v bd >/dev/null 2>&1 || exit 0

# tool_input may be an object OR a bare string; the naive
# `.tool_input.command // .tool_input` THROWS on a string (silently bypassing
# the guard under swallowed stderr), so type-check first. Emit event, tool,
# file_path on single lines (none contain newlines) and the multi-line
# command/patch last via $(cat).
event=""
tool_name=""
file_path=""
cmd=""
{
  IFS= read -r event || true
  IFS= read -r tool_name || true
  IFS= read -r file_path || true
  cmd="$(cat)"
} < <(
  printf '%s' "$payload" | jq -j '
    (.hook_event_name // "") + "\n" +
    (.tool_name // .tool // "") + "\n" +
    (if (.tool_input|type)=="object" then (.tool_input.file_path // .tool_input.path // "") else "" end) + "\n" +
    (if (.tool_input|type)=="object" then (.tool_input.command // "") else "" end)
  ' 2>/dev/null
)

# Bare-string tool_input (legacy shape) parses to no fields at all -> allow.
[ -n "$tool_name" ] || exit 0

cwd="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
[ -n "$cwd" ] && [ "$cwd" != "null" ] && [ -d "$cwd" ] || cwd="$PWD"

# Is $1 a SpecKit tasks file? Matches specs/<feature>/tasks.md at any depth,
# relative or absolute.
is_tasks_md() {
  case "$1" in
    specs/*/tasks.md|*/specs/*/tasks.md) return 0 ;;
    *) return 1 ;;
  esac
}

# Active beads workspace? Only then does the beads workflow own task state.
beads_active() {
  bd -C "$cwd" where >/dev/null 2>&1
}

DENY_REASON="blocked by speckit-beads (task state lives in beads, tasks.md is never authored): this repo has an active beads workspace, so specs/*/tasks.md is read-only legacy and must not be written or created. Create implementation tasks as beads under the feature molecule's implement step instead: bd create \"T00N <title>\" --parent <implement-step-id> --spec-id <NNN-slug> -t task; wire ordering with bd dep add <later-id> <earlier-id>; bulk-create with bd create -f <tmpfile>.md (write the temp file OUTSIDE specs/). Then work the tasks via bd ready -> bd update <id> --claim -> bd close <id> --reason \"...\". Find the implement step with bd mol current <molecule-root-id>."

deny() {
  jq -cn --arg reason "$DENY_REASON" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}' 2>/dev/null || true
  exit 0
}

advise() {
  jq -cn --arg ctx "$1" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$ctx}}' 2>/dev/null || true
  exit 0
}

case "$event" in
  PreToolUse)
    case "$tool_name" in
      Write|Edit|MultiEdit)
        is_tasks_md "$file_path" || exit 0
        beads_active || exit 0
        deny
        ;;
      apply_patch|functions.apply_patch)
        # Codex sends the whole patch in tool_input.command; deny if ANY file
        # header targets a tasks.md (Add covers creation, Update/Delete edits).
        while IFS= read -r patch_path; do
          [ -n "$patch_path" ] || continue
          if is_tasks_md "$patch_path"; then
            beads_active || exit 0
            deny
          fi
        done < <(printf '%s\n' "$cmd" | sed -nE 's/^\*\*\* (Update|Add|Delete) File: (.*)$/\2/p')
        ;;
    esac
    ;;
  PostToolUse)
    case "$tool_name" in
      Read)
        is_tasks_md "$file_path" || exit 0
        beads_active || exit 0
        advise "SPECKIT-BEADS: $file_path is a legacy artifact; its checkboxes are not maintained. Live task state is in beads: bd ready (unblocked work), bd query \"spec_id=<NNN-slug>\" --json (all tasks for the spec), bd mol current <molecule-root-id> (workflow position). Use this read only for one-time migration into beads."
        ;;
    esac
    ;;
esac

exit 0
