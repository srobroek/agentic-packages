#!/usr/bin/env bash
# CRITICAL: this script lives at
#   .apm/skills/example-skill/scripts/check.sh
# i.e. NESTED under the skill directory, because SKILL.md references it with
# the file-relative path `scripts/check.sh`. Root-level scripts/ would NOT
# resolve for a skill. (Hooks are the opposite -- see the hooks template.)
set -euo pipefail

# Replace with the real read-only check for your skill.
echo "example-skill: running checks"
