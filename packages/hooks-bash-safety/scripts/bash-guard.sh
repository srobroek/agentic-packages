#!/usr/bin/env bash
set -euo pipefail

# bash-guard.sh — PreToolUse:Bash safety guard (cross-tool: Claude + Codex).
#
# Tiers, lightest-touch first. The goal is MINIMAL impediment to autonomous
# agents: hard-block ONLY truly unrecoverable operations; everything recoverable
# is at most an ask or a non-blocking nudge.
#   * DENY — catastrophic & unrecoverable: rm -rf / (incl. // and the literal
#     /* token), rm -rf on $HOME, mkfs, dd to a block device, and the
#     sandbox-bypass flag. These deny even when prefixed with `sudo`.
#   * ASK  — recoverable but high-risk: curl|wget piped into a shell (the common
#     vendor-installer idiom). Recoverable, so confirm once instead of walling.
#   * WARN — `sudo` paired with a destructive/disruptive subcommand: a
#     non-blocking nudge only. Plain sudo (apt, systemctl status, cat, ...)
#     passes silently — sudo itself is no longer blocked.
#
# Matching is anchored to COMMAND POSITION (start of string, or right after a
# real shell separator ; & | && ||), optionally seeing through a leading `sudo`.
# This is what stops the whole-string false positives where a dangerous phrase
# merely appears inside an echo / quoted argument / heredoc, e.g.
# `echo "rm -rf /"` or `git commit -m "curl x | sh"`.

# Read the hook payload from stdin. No payload / no shell command => nothing to
# evaluate.
payload="$(cat)"
if [[ -z "$payload" ]]; then
  exit 0
fi

# tool_input may be an object ({command:"..."}) OR a bare string. The naive
# `.tool_input.command // .tool_input` form THROWS on a string (jq cannot index
# a string), which with stderr swallowed would silently bypass the guard. Branch
# on type so both shapes are read.
command="$(
  printf '%s' "$payload" | jq -r '
    if (.tool_input|type)=="string" then .tool_input
    else (.tool_input.command // empty) end
  ' 2>/dev/null || true
)"

if [[ -z "$command" || "$command" == "null" ]]; then
  exit 0
fi

# Normalize case once so the policy checks stay simple ($HOME -> $home, etc.).
lowered="$(printf '%s' "$command" | tr '[:upper:]' '[:lower:]')"

# Hard reject: the operation is refused outright.
deny() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
  exit 0
}

# Soft block: surface the reason and require the user to confirm before running.
ask() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$reason}}'
  exit 0
}

# Non-blocking nudge: allow the command but inject advisory context.
warn() {
  jq -cn --arg ctx "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",additionalContext:$ctx}}'
  exit 0
}

# Command-position boundary: start of string, OR just after a real shell
# separator (; & | && ||) with optional surrounding spaces. Deliberately NOT
# plain whitespace — matching on whitespace is exactly what makes a dangerous
# phrase inside a quoted argument (echo "...") false-positive today.
cmd='(^|[[:space:]]*[;&|]+[[:space:]]*)'

# Optional leading `sudo [opts]` so a sudo-prefixed command is still seen at
# command position (`sudo rm -rf /` -> deny). A `sudo -u <user> <verb>`
# value-argument form is not peeled (rare for an agent); accepted gap.
sx='(sudo[[:space:]]+(-[^[:space:]]+[[:space:]]+)*)?'

# --- HARD DENY: unrecoverable -------------------------------------------------

# The sandbox/approval bypass flag disables the safety envelope itself.
if [[ "$lowered" =~ --dangerously-bypass-approvals-and-sandbox ]]; then
  deny "refusing approval/sandbox bypass flag (disables the safety envelope)"
fi

# rm -rf / — also // and the literal /* token (`rm -rf /*` wipes everything
# under root just like `rm -rf /`). Matches a sudo-prefixed form too.
if [[ "$lowered" =~ ${cmd}${sx}rm[[:space:]]+-rf[[:space:]]+/[/*]*($|[[:space:]]) ]]; then
  deny "refusing rm -rf / (wipes the root filesystem; unrecoverable)"
fi

# rm -rf on the home directory, in the forms a model might emit: literal `~` and
# the un-expanded `$home`/`${home}` (lowercased from $HOME/${HOME}).
if [[ "$lowered" =~ ${cmd}${sx}rm[[:space:]]+-rf[[:space:]]+(~|\$home|\$\{home\})(/|$|[[:space:]]) ]]; then
  deny "refusing rm -rf on the home directory (unrecoverable)"
fi

# mkfs and its filesystem-specific variants (mkfs.ext4, mkfs.xfs, ...).
if [[ "$lowered" =~ ${cmd}${sx}mkfs(\.[a-z0-9]+)?([[:space:]]|$) ]]; then
  deny "refusing mkfs (formats a filesystem; destroys all data on it)"
fi

# dd writing to a block device overwrites the raw disk, unrecoverable.
if [[ "$lowered" =~ ${cmd}${sx}dd[[:space:]].*of=/dev/ ]]; then
  deny "refusing dd to a block device (overwrites the raw disk; unrecoverable)"
fi

# --- ASK: recoverable but high-risk ------------------------------------------

# curl/wget piped straight into a shell runs unverified remote code. It is the
# vendor-sanctioned installer idiom (rustup/uv/nvm) and is recoverable, so
# confirm once rather than hard-blocking.
if [[ "$lowered" =~ ${cmd}${sx}(curl|wget)[[:space:]].*\|[[:space:]]*(sh|bash)([[:space:]]|$) ]]; then
  ask "curl/wget piped into a shell executes remote code unverified — confirm the source is trusted before proceeding."
fi

# --- WARN: elevated + destructive (non-blocking) -----------------------------

# `sudo` is allowed; nudge only when it is paired with a destructive/disruptive
# subcommand. The genuinely catastrophic sudo forms (sudo rm -rf /, sudo mkfs,
# sudo dd to a device) already denied above, so this covers the recoverable but
# privilege-amplified rest (e.g. sudo rm /etc/hosts, sudo systemctl stop, sudo
# chown -R).
sudo_verbs='rm|dd|shred|wipefs|mkfs|fdisk|parted|umount|chmod|chown|chgrp|reboot|shutdown|halt|poweroff|systemctl|service|kill|pkill|killall|userdel|groupdel|passwd|visudo|iptables|nft|ufw'
if [[ "$lowered" =~ ${cmd}sudo[[:space:]]+(-[^[:space:]]+[[:space:]]+)*(${sudo_verbs})([[:space:]]|$) ]]; then
  warn "This runs a destructive/disruptive command with elevated privileges (sudo). Double-check the target is correct and the change is recoverable before proceeding."
fi

exit 0
