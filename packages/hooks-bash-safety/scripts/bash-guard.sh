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

# Decision helpers. The `2>/dev/null || true` before `exit 0` is load-bearing:
# under `set -euo pipefail` a jq hiccup would otherwise exit NONZERO, which
# Codex's exit-code contract reads as a hard block. The decision lives in the
# JSON, not the exit code.

# deny: BLOCK the command. The reason is fed back to the model (Claude), which
# adapts and re-issues — no human needed, so it works in non-interactive/auto
# mode. Reserved for truly unrecoverable operations. We deliberately NEVER emit
# `ask` (the human-confirmation decision): it would stall an autonomous run.
deny() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}' 2>/dev/null || true
  exit 0
}

# warn: ALLOW the command but inject a relevant advisory for the model. The
# command proceeds; the note just lets the agent confirm intent. Used for
# recoverable-but-risky operations.
warn() {
  jq -cn --arg ctx "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",additionalContext:$ctx}}' 2>/dev/null || true
  exit 0
}

# Command-position boundary: start of string (allowing leading whitespace/tabs,
# e.g. an indented `  rm -rf /`), OR just after a real shell separator
# (; & | && ||) with optional surrounding spaces. Deliberately NOT bare
# whitespace mid-string — matching on that is what makes a dangerous phrase
# inside a quoted argument (echo "...") false-positive.
cmd='(^[[:space:]]*|[[:space:]]*[;&|]+[[:space:]]*)'

# Optional leading command WRAPPERS and ENV-ASSIGNMENTS so a prefixed command is
# still seen at command position: `sudo rm -rf /`, `FOO=bar rm -rf /`,
# `env rm -rf /`, `time mkfs ...` all still reach the verb. Any number of
# `NAME=value` assignments and/or one wrapper (with its own options) are peeled.
# (`sudo -u <user> <verb>` value-arg form is not modelled; accepted gap.)
sx='(([a-z_][a-z0-9_]*=[^[:space:]]*[[:space:]]+)*((sudo|doas|env|time|nice|command|exec|xargs|stdbuf|nohup|setsid|ionice)[[:space:]]+(-[^[:space:]]+[[:space:]]+([^-][^[:space:]]*[[:space:]]+)?)*)?)*'

# --- HARD DENY: unrecoverable -------------------------------------------------

# The sandbox/approval bypass flag disables the safety envelope itself.
if [[ "$lowered" =~ --dangerously-bypass-approvals-and-sandbox ]]; then
  deny "blocked by BS-3 (no sandbox-bypass flag): refusing --dangerously-bypass-approvals-and-sandbox (disables the safety envelope)"
fi

# `rm` with both recursive+force as a BUNDLED single short-flag token, in either
# letter order and with extra letters: -rf, -fr, -rfv, -vrf, -rvf, ... This is
# the overwhelmingly common form and is cheap defense-in-depth here. The SIBLING
# guard rm-rf-guard.sh is the authoritative, more-nuanced rm handler and already
# covers split flags (-r -f), --recursive/--force long opts, target-first, tabs,
# and path normalization — so bash-guard intentionally does NOT duplicate that.
# `rmrf_b` matches the bundled flag token (r…f or f…r) plus the whitespace after.
rmrf_b="rm[[:space:]]+(-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*)[[:space:]]+"

# `q` is an optional LEADING quote char before the path (`rm -rf "/`). We match
# NO trailing closing quote: doing so let a separator-inside-quotes form like
# `echo "x; rm -rf /"` satisfy the end-anchor (the command-position branch
# matched the `;` INSIDE the quotes, and the closing `"` was consumed as the
# trailing quote) — a benign-echo FALSE POSITIVE. A genuinely-quoted catastrophic
# target (`rm -rf "/"`) is still denied by the sibling rm-rf-guard.sh, which
# strips quotes and classifies the resolved path.
q="['\"]?"

# rm -rf / — also // and the literal /* token (`rm -rf /*` wipes everything under
# root just like `rm -rf /`). Bundled flag, optional LEADING quote, prefix-aware.
if [[ "$lowered" =~ ${cmd}${sx}${rmrf_b}${q}/[/*]*($|[[:space:]]) ]]; then
  deny "blocked by BS-4 (no rm -rf on filesystem root): refusing rm -rf / (wipes the root filesystem; unrecoverable)"
fi

# rm -rf on the home ROOT itself: literal `~` and the un-expanded
# `$home`/`${home}` (lowercased from $HOME/${HOME}). Only the home root is denied
# here — a SUBPATH like `rm -rf ~/cache` is left to rm-rf-guard.sh's
# git-recoverability model. The trailing class stops at `/`-then-EOL or
# whitespace, NOT a deeper path.
home_t="(~|\\\$home|\\\$\\{home\\})"
if [[ "$lowered" =~ ${cmd}${sx}${rmrf_b}${q}${home_t}(/?($|[[:space:]])) ]]; then
  deny "blocked by BS-4 (no rm -rf on home root): refusing rm -rf on the home directory root (unrecoverable). If you meant a subdirectory, pass its explicit path."
fi

# mkfs and its filesystem-specific variants (mkfs.ext4, mkfs.xfs, ...).
if [[ "$lowered" =~ ${cmd}${sx}mkfs(\.[a-z0-9]+)?([[:space:]]|$) ]]; then
  deny "blocked by BS-5 (no mkfs): refusing mkfs (formats a filesystem; destroys all data on it)"
fi

# dd writing to a block device overwrites the raw disk, unrecoverable. But the
# PSEUDO-devices /dev/null, /dev/zero, /dev/random, /dev/urandom, /dev/stdout and
# /dev/stdin are harmless sinks/sources an agent legitimately uses (e.g.
# `dd if=/dev/zero of=/dev/null`, `... of=/dev/stdout`) — allow those, deny only a
# real block/char device target.
if [[ "$lowered" =~ ${cmd}${sx}dd[[:space:]].*of=/dev/ ]] \
  && ! [[ "$lowered" =~ of=/dev/(null|zero|random|urandom|stdout|stdin)([[:space:]]|$) ]]; then
  deny "blocked by BS-6 (no dd to block device): refusing dd to a block device (overwrites the raw disk; unrecoverable)"
fi

# --- WARN: recoverable but high-risk (non-blocking) --------------------------

# curl/wget piped straight into a shell runs unverified remote code. It is the
# vendor-sanctioned installer idiom (rustup/uv/nvm) and is fully recoverable, so
# it is a non-blocking warn — the agent is informed but not stalled.
if [[ "$lowered" =~ ${cmd}${sx}(curl|wget)[[:space:]].*\|[[:space:]]*(sh|bash)([[:space:]]|$) ]]; then
  warn "BS-7 (warn on curl|sh pipe): curl/wget piped into a shell executes remote code unverified. Make sure the source URL is trusted (prefer downloading, inspecting, then running). Proceeding."
fi

# --- WARN: elevated + destructive (non-blocking) -----------------------------

# `sudo` is allowed; nudge only when it is paired with a destructive/disruptive
# subcommand. The genuinely catastrophic sudo forms (sudo rm -rf /, sudo mkfs,
# sudo dd to a device) already denied above, so this covers the recoverable but
# privilege-amplified rest (e.g. sudo rm /etc/hosts, sudo systemctl stop, sudo
# chown -R).
sudo_verbs='rm|dd|shred|wipefs|mkfs|fdisk|parted|umount|chmod|chown|chgrp|reboot|shutdown|halt|poweroff|systemctl|service|kill|pkill|killall|userdel|groupdel|passwd|visudo|iptables|nft|ufw'
ro_subcmds='status|show|list-units|list-unit-files|is-active|is-enabled|is-failed|cat|get-default'

# Evaluate PER SHELL CLAUSE, not against the whole command: a read-only
# `systemctl status` clause must NOT suppress the warn for a destructive sibling
# clause (e.g. `sudo systemctl stop app && sudo systemctl status app`, or
# `sudo systemctl status app; sudo rm /etc/hosts`). We split $lowered on the
# shell separators (; & |) and warn as soon as ONE clause is a sudo+destructive
# verb that is NOT a read-only systemctl/service form.
sctl_ro_clause="^[[:space:]]*sudo[[:space:]]+(-[^[:space:]]+[[:space:]]+([^-][^[:space:]]*[[:space:]]+)?)*systemctl[[:space:]]+(${ro_subcmds})([[:space:]]|$)"
svc_ro_clause="^[[:space:]]*sudo[[:space:]]+(-[^[:space:]]+[[:space:]]+([^-][^[:space:]]*[[:space:]]+)?)*service[[:space:]]+[^[:space:]]+[[:space:]]+(${ro_subcmds})([[:space:]]|$)"
sudo_verb_clause="^[[:space:]]*sudo[[:space:]]+(-[^[:space:]]+[[:space:]]+([^-][^[:space:]]*[[:space:]]+)?)*(${sudo_verbs})([[:space:]]|$)"

# Split on ; & | (collapse runs of separators), then test each clause.
_ifs_save="$IFS"
IFS=$'\n'
for clause in $(printf '%s' "$lowered" | tr ';&|' '\n'); do
  if [[ "$clause" =~ $sudo_verb_clause ]]; then
    # A privilege-amplified destructive verb in THIS clause — unless it is a
    # read-only systemctl/service form, warn (and stop; one warn is enough).
    if [[ "$clause" =~ $sctl_ro_clause ]] || [[ "$clause" =~ $svc_ro_clause ]]; then
      continue
    fi
    IFS="$_ifs_save"
    warn "BS-7 (warn on sudo+destructive): this runs a destructive/disruptive command with elevated privileges (sudo). Double-check the target is correct and the change is recoverable before proceeding."
  fi
done
IFS="$_ifs_save"

exit 0
