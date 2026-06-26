# Changelog

## 0.1.0

### Features

* Initial release: on-demand CI gate that lints shipped hook scripts for the
  portability failure modes surfaced by the Phase-1/Phase-2 audits.
  `scripts/portability-check.sh [dir]` discovers every `*.sh` under
  `*/scripts/` and `*/hooks` paths (defaulting to `packages/`) and runs three
  checks per script: a bash 3.2 parse via `/bin/bash -n` plus a `mapfile`/
  `readarray` grep (bash-4 runtime builtins that parse but exit 127 on 3.2);
  a GNU-only sed/grep scan (`\b` word boundaries in sed, `+?`/`*?` lazy
  quantifiers in sed/grep that BSD tooling rejects), skipping comment lines;
  and a string-form `tool_input` payload probe (wall-clock bounded) that
  asserts the script does not crash jq with "Cannot index string ...". Prints a
  per-failure summary and exits non-zero on any failure so it can gate CI.
  Portable to bash 3.2.57 + BSD sed/grep (stock macOS).
