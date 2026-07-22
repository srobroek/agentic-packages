#!/usr/bin/env bash

set -u

readonly runtime_dir="${XDG_CONFIG_HOME:-${HOME}/.config}/1mcp"
readonly pid_file="${runtime_dir}/server.pid"
readonly lock_file="${runtime_dir}/launcher.lock"
readonly wait_seconds="${MCP1_LAUNCHER_WAIT_SECONDS:-${ONE_MCP_LAUNCHER_WAIT_SECONDS:-20}}"
readonly kill_grace="${MCP1_LAUNCHER_KILL_GRACE_SECONDS:-${ONE_MCP_LAUNCHER_KILL_GRACE_SECONDS:-1}}"
readonly async_min_servers="${MCP1_LAUNCHER_ASYNC_MIN_SERVERS:-${ONE_MCP_LAUNCHER_ASYNC_MIN_SERVERS:-1}}"
readonly async_timeout_ms="${MCP1_LAUNCHER_ASYNC_TIMEOUT_MS:-${ONE_MCP_LAUNCHER_ASYNC_TIMEOUT_MS:-5000}}"
readonly supplied_deadline="${MCP1_LAUNCHER_DEADLINE_EPOCH:-${ONE_MCP_LAUNCHER_DEADLINE_EPOCH:-}}"
readonly launcher_locked="${MCP1_LAUNCHER_LOCKED:-0}"

# 1mcp maps every ONE_MCP_* variable to a CLI option. Keep legacy launcher
# tuning compatible, but never leak launcher-only variables into 1mcp itself.
unset ONE_MCP_LAUNCHER_WAIT_SECONDS ONE_MCP_LAUNCHER_KILL_GRACE_SECONDS ONE_MCP_LAUNCHER_ASYNC_MIN_SERVERS ONE_MCP_LAUNCHER_ASYNC_TIMEOUT_MS ONE_MCP_LAUNCHER_DEADLINE_EPOCH ONE_MCP_LAUNCHER_LOCKED
unset MCP1_LAUNCHER_WAIT_SECONDS MCP1_LAUNCHER_KILL_GRACE_SECONDS MCP1_LAUNCHER_ASYNC_MIN_SERVERS MCP1_LAUNCHER_ASYNC_TIMEOUT_MS MCP1_LAUNCHER_DEADLINE_EPOCH MCP1_LAUNCHER_LOCKED

is_uint() {
  [[ "${1:-}" =~ ^[0-9]+$ ]]
}

die() {
  printf '%s\n' "$*" >&2
  exit 1
}

if ! is_uint "$wait_seconds" || ((wait_seconds == 0)); then
  die "1mcp-launcher-invalid-wait-seconds"
fi
is_uint "$kill_grace" || die "1mcp-launcher-invalid-kill-grace"
is_uint "$async_min_servers" || die "1mcp-launcher-invalid-async-min-servers"
is_uint "$async_timeout_ms" || die "1mcp-launcher-invalid-async-timeout"

one_mcp_bin="$(command -v 1mcp)" || die "1mcp-not-installed-install-agent-0.34.4-or-later"
node_bin="$(command -v node)" || die "node-not-installed-required-by-1mcp"
mkdir -p "$runtime_dir" || die "1mcp-launcher-runtime-dir-unavailable"

if [[ -n "$supplied_deadline" ]]; then
  readonly deadline="$supplied_deadline"
else
  readonly deadline="$(($(date +%s) + wait_seconds))"
fi

if command -v timeout >/dev/null 2>&1; then
  readonly timeout_mode=timeout
  readonly timeout_bin=timeout
elif command -v gtimeout >/dev/null 2>&1; then
  readonly timeout_mode=timeout
  readonly timeout_bin=gtimeout
elif command -v perl >/dev/null 2>&1; then
  readonly timeout_mode=perl
  readonly timeout_bin=perl
else
  die "1mcp-launcher-needs-timeout-gtimeout-or-perl"
fi

remaining() {
  local seconds
  seconds=$((deadline - $(date +%s)))
  ((seconds > 0)) || return 1
  printf '%s\n' "$seconds"
}

run_bounded() {
  local limit="$1"
  local available
  shift
  available="$(remaining)" || return 124
  ((limit < available)) || limit="$available"
  if [[ "$timeout_mode" == timeout ]]; then
    "$timeout_bin" -k "$kill_grace" "$limit" "$@"
  else
    "$timeout_bin" -e 'alarm shift; exec @ARGV or exit 127' "$limit" "$@"
  fi
}

ready() {
  run_bounded 2 "$one_mcp_bin" serve --status >/dev/null 2>&1
}

wait_ready() {
  while remaining >/dev/null; do
    ready && return 0
    sleep 0.2
  done
  return 1
}

read_pid() {
  "$node_bin" -e '
    const fs = require("fs");
    try {
      const pid = JSON.parse(fs.readFileSync(process.argv[1], "utf8")).pid;
      if (!Number.isSafeInteger(pid) || pid <= 0) process.exit(1);
      process.stdout.write(String(pid));
    } catch {
      process.exit(1);
    }
  ' "$pid_file"
}

is_runtime_process() {
  local pid="$1"
  local arg
  local binary=0
  local serve=0
  local bootstrap=0

  [[ "$pid" != "$$" ]] || return 1
  if [[ -r "/proc/$pid/cmdline" ]]; then
    while IFS= read -r arg; do
      case "$arg" in
        1mcp | */1mcp | */1mcp/* | *@1mcp/agent/*) binary=1 ;;
        serve) serve=1 ;;
        --background-bootstrap) bootstrap=1 ;;
      esac
    done < <(tr '\0' '\n' <"/proc/$pid/cmdline")
    ((binary == 1 && serve == 1 && bootstrap == 1))
    return
  fi

  local comm
  local args
  comm="$(ps -p "$pid" -o comm= 2>/dev/null)" || return 1
  comm="${comm##*/}"
  case "$comm" in sh | bash | zsh | fish) return 1 ;; esac
  args="$(ps -ww -p "$pid" -o args= 2>/dev/null)" || return 1
  [[ " $args " == *" 1mcp "*" serve "*" --background-bootstrap"* ||
    " $args " == *" @1mcp/agent/"*" serve "*" --background-bootstrap"* ]]
}

quarantine_stale_pid() {
  local stale
  stale="${pid_file}.stale.$(date +%s).$$"
  mv "$pid_file" "$stale" || {
    ready && return 0
    printf 'failed to quarantine stale 1mcp PID state: %s\n' "$pid_file" >&2
    return 1
  }
  printf 'quarantined stale 1mcp PID state: %s\n' "$stale" >&2
}

start_runtime() {
  local real_bin
  local -a command
  real_bin="$("$node_bin" -e '
    const fs = require("fs");
    process.stdout.write(fs.realpathSync(process.argv[1]));
  ' "$one_mcp_bin")" || return 1

  case "$real_bin" in
    *.js | *.cjs | *.mjs) command=("$node_bin" "$real_bin") ;;
    *) command=("$one_mcp_bin") ;;
  esac

  run_bounded "$wait_seconds" "${command[@]}" serve --background \
    --enable-async-loading \
    --async-min-servers "$async_min_servers" \
    --async-timeout "$async_timeout_ms" >/dev/null
}

ensure_runtime() {
  local pid

  ready && return 0
  if [[ -f "$pid_file" ]]; then
    pid="$(read_pid 2>/dev/null || :)"
    if [[ -n "$pid" ]] && is_runtime_process "$pid"; then
      wait_ready && return 0
      printf '1mcp runtime is alive but unhealthy; operator intervention required\n' >&2
      run_bounded 2 "$one_mcp_bin" serve --status >&2 || :
      return 1
    fi
    quarantine_stale_pid || return 1
  fi

  start_runtime || {
    ready && return 0
    printf '1mcp startup failed; serve --status follows\n' >&2
    run_bounded 2 "$one_mcp_bin" serve --status >&2 || :
    return 1
  }
  ready
}

acquire_and_start() {
  local available
  available="$(remaining)" || return 124
  if command -v flock >/dev/null 2>&1; then
    flock -w "$available" "$lock_file" \
      env MCP1_LAUNCHER_LOCKED=1 \
      MCP1_LAUNCHER_DEADLINE_EPOCH="$deadline" bash "$0"
  elif command -v lockf >/dev/null 2>&1; then
    lockf -t "$available" "$lock_file" \
      env MCP1_LAUNCHER_LOCKED=1 \
      MCP1_LAUNCHER_DEADLINE_EPOCH="$deadline" bash "$0"
  else
    printf '1mcp-launcher-needs-flock-or-lockf\n' >&2
    return 1
  fi
}

if [[ "$launcher_locked" == 1 ]]; then
  ensure_runtime
  exit $?
fi

ready && exec "$one_mcp_bin" proxy
acquire_and_start || {
  ready && exec "$one_mcp_bin" proxy
  die "1mcp-launcher-lock-or-startup-timeout"
}
exec "$one_mcp_bin" proxy
