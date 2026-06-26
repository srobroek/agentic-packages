#!/usr/bin/env bash
# SKILL script -> nested under the skill dir
# (.apm/skills/example-hybrid/scripts/run.sh) because SKILL.md references it
# with the file-relative path `scripts/run.sh`. This is distinct from the
# HOOK script at the package root (scripts/notify.sh) in this same hybrid.
set -euo pipefail

echo "example-hybrid skill: running"
