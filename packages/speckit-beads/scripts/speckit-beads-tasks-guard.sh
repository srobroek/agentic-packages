#!/usr/bin/env bash
# speckit-beads-tasks-guard.sh — cross-tool hook with several roles, branched
# on hook_event_name:
#
#   PreToolUse  (Write|Edit|MultiEdit|apply_patch): DENY every write to
#     specs/*/tasks.md when the repo has an active beads workspace. tasks.md is
#     never authored under the beads workflow — task state lives in beads. The
#     deny reason carries the full replacement workflow so the agent
#     self-corrects without a human (hook-guard policy: deny is agent-facing,
#     never "ask").
#
#   PreToolUse  (Bash): ADVISORY ONLY — a command string referencing a
#     specs/*/tasks.md path gets a non-blocking additionalContext note (task
#     state lives in beads). No redirect parsing; plain substring match.
#
#   PreToolUse  (Skill): ADVISORY ONLY — invoking speckit-implement gets a
#     non-blocking note that /speckit.implement is deprecated in beads repos;
#     route through the agent-assign chain instead.
#
# Self-gating (never rely on the "if" matcher): exits 0 silently when the
# payload is empty, jq or bd is missing, the target path is not
# specs/*/tasks.md, or the repo has no active beads workspace (bd where fails).
# bash 3.2 / BSD safe.
set -euo pipefail

payload="$(cat 2>/dev/null || true)"
[ -n "$payload" ] || exit 0

# Cheap pre-jq bail: every branch below acts on a tasks.md target or a
# speckit-implement skill invocation; anything else needs no inspection.
case "$payload" in
  *tasks.md*|*speckit.implement*|*speckit-implement*) ;;
  *) exit 0 ;;
esac

command -v jq >/dev/null 2>&1 || exit 0
command -v bd >/dev/null 2>&1 || exit 0

# tool_input may be an object OR a bare string; the naive
# `.tool_input.command // .tool_input` THROWS on a string (silently bypassing
# the guard under swallowed stderr), so type-check first. Single jq pass
# (repo idiom): emit event, tool, file_path, skill, cwd on single lines (none
# contain newlines) and the multi-line command/patch last via $(cat).
event=""
tool_name=""
file_path=""
skill_name=""
cwd=""
cmd=""
{
  IFS= read -r event || true
  IFS= read -r tool_name || true
  IFS= read -r file_path || true
  IFS= read -r skill_name || true
  IFS= read -r cwd || true
  cmd="$(cat)"
} < <(
  printf '%s' "$payload" | jq -j '
    (.hook_event_name // "") + "\n" +
    (.tool_name // .tool // "") + "\n" +
    (if (.tool_input|type)=="object" then (.tool_input.file_path // .tool_input.path // "") else "" end) + "\n" +
    (if (.tool_input|type)=="object" then (.tool_input.skill // "") else "" end) + "\n" +
    (.cwd // "") + "\n" +
    (if (.tool_input|type)=="object" then (.tool_input.command // "") else "" end)
  ' 2>/dev/null
)

# Bare-string tool_input (legacy shape) parses to no fields at all -> allow.
[ -n "$tool_name" ] || exit 0

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

# advise <event> <context>: non-blocking additionalContext for either phase.
advise() {
  jq -cn --arg ev "$1" --arg ctx "$2" '{hookSpecificOutput:{hookEventName:$ev,additionalContext:$ctx}}' 2>/dev/null || true
  exit 0
}

BASH_ADVICE="SPECKIT-BEADS: tasks.md is not authored in beads repos; task state lives in beads: bd ready / bd update <id> --claim / bd close <id> --reason. If reading legacy tasks.md for migration, that's fine."

IMPLEMENT_ADVICE="SPECKIT-BEADS: /speckit.implement is deprecated in beads repos; route through the agent-assign chain instead (/speckit.agent-assign.assign -> validate -> execute), working the molecule steps via bd mol current / bd ready / bd update --claim / bd close."

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
      Bash)
        # Advisory only (user decision): a Bash command touching a
        # specs/*/tasks.md path may be legitimate (migration reads, greps), so
        # never deny -- just remind where task state lives. Plain substring
        # match on the path pattern; no redirect parsing.
        case "$cmd" in
          *specs/*/tasks.md*)
            beads_active || exit 0
            advise "PreToolUse" "$BASH_ADVICE"
            ;;
        esac
        ;;
      Skill)
        # /speckit.implement is deprecated under the beads workflow; advise
        # the agent-assign route (non-blocking).
        case "$skill_name $cmd" in
          *speckit-implement*|*speckit.implement*)
            beads_active || exit 0
            advise "PreToolUse" "$IMPLEMENT_ADVICE"
            ;;
        esac
        ;;
    esac
    ;;
esac

exit 0
