# Unstuck Checklist

Baseline of observable facts to gather before naming assumptions or hypotheses.

- What is the exact failing command and exact error output?
- What is the smallest reproduction or feedback loop, or why does none exist?
- Did `diagnose` run first? If not, why was it skipped?
- What changed most recently? (`git diff --stat`, `git log --oneline -10`)
- Which files are affected, and which were recently edited?
- Is the error from config, environment, or code?
- What has already been tried, and what was the observed result?
