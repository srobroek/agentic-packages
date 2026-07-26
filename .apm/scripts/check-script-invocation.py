#!/usr/bin/env python3
"""CI check: every bare-path script invocation targets a committed-executable file.

Two invocation styles ship in this repo:

- interpreter-prefixed -- `uv run --quiet <path>`, `python3 <path>`,
  `bash <path>`. The file mode is irrelevant; the interpreter reads the file.
- bare path -- `${PLUGIN_ROOT}/scripts/guard.sh`, or a skill telling the agent
  to run `.claude/hooks/<pkg>/scripts/<name>.py bind <id>`. The kernel needs
  the executable bit, so a mode-644 source ships a command that exits
  "permission denied" on every install.

APM deploys the source mode on first write, but it compares content and skips
identical files, so a later mode-only source fix never reaches an install that
already has the wrong bit. That makes the mode part of the shipped contract:
a bare-path reference to a mode-644 script is a defect at author time, and
correcting it afterwards cannot repair existing installs.

Scopes checked:

1. hook JSON commands (packages/*/hooks/*.json, packages/*/.apm/hooks/*.json,
   .apm/hooks/*.json) -- the command that Claude or Codex executes directly.
2. agent-facing markdown under packages/*/.apm/ -- backticked runtime paths
   under a `hooks/` or `skills/` directory, which is how a skill tells an agent
   to invoke an installed script.

Exit 0 when clean, 1 when a bare-path reference resolves to a non-executable
committed file.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

# Interpreter forms that make the file mode irrelevant.
INTERPRETER_RE = re.compile(
    r"(?:^|[\s;&|(`])(?:uv\s+run(?:\s+--\S+)*|python3?|bash|sh|zsh|node|deno)\s+$"
)

# Any script-looking token in a hook command.
SCRIPT_TOKEN_RE = re.compile(r"[^\s\"']*[\w.-]+\.(?:py|sh)\b")

# `.claude/hooks/<pkg>/scripts/<name>.py` and the `.codex` / `skills` variants,
# as written inside agent-facing markdown.
RUNTIME_PATH_RE = re.compile(
    r"\.(?:claude|codex)/(?:hooks|skills)/[\w.-]+/(?:scripts/)?[\w.-]+\.(?:py|sh)\b"
)

HOOK_JSON_GLOBS = (
    "packages/*/hooks/*.json",
    "packages/*/.apm/hooks/*.json",
    ".apm/hooks/*.json",
)


def committed_modes(root: Path) -> dict[str, str]:
    """Map repo-relative path -> git index mode for every tracked file."""
    out = subprocess.run(
        ["git", "ls-files", "-s"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    modes: dict[str, str] = {}
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        modes[path] = meta.split()[0]
    return modes


def hook_commands(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    commands: list[str] = []
    for groups in (data.get("hooks") or {}).values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            for handler in group.get("hooks", []):
                command = handler.get("command")
                if isinstance(command, str):
                    commands.append(command)
    return commands


def bare_script_refs(command: str) -> list[str]:
    """Script tokens in a command that no interpreter precedes."""
    refs = []
    for match in SCRIPT_TOKEN_RE.finditer(command):
        if INTERPRETER_RE.search(command[: match.start()]):
            continue
        refs.append(match.group(0))
    return refs


def resolve_hook_ref(ref: str, package: Path) -> Path | None:
    """Map a hook command token onto its source file inside the package."""
    cleaned = ref.replace("${PLUGIN_ROOT}", "").replace("$PLUGIN_ROOT", "")
    cleaned = cleaned.replace('"${CLAUDE_PROJECT_DIR:-.}"', "")
    cleaned = cleaned.replace("${CLAUDE_PROJECT_DIR}", "")
    cleaned = cleaned.lstrip("/")
    if not cleaned:
        return None
    candidate = package / cleaned
    if candidate.is_file():
        return candidate
    # Skill-scoped hooks name the installed layout (.claude/skills/<skill>/...);
    # the source lives under the package's .apm tree.
    tail = Path(cleaned)
    for parent in (package / ".apm", package):
        for depth in range(len(tail.parts)):
            probe = parent.joinpath(*tail.parts[depth:])
            if probe.is_file():
                return probe
    return None


def resolve_runtime_ref(ref: str, root: Path) -> Path | None:
    """Map an installed runtime path (.claude/hooks/<pkg>/...) onto its source."""
    parts = Path(ref).parts  # (.claude, hooks|skills, <name>, ...)
    if len(parts) < 4:
        return None
    kind, name, tail = parts[1], parts[2], Path(*parts[3:])
    packages = root / "packages"
    if kind == "hooks":
        candidates = [packages / name / tail, packages / name / ".apm" / tail]
    else:
        candidates = [
            packages / pkg.name / ".apm" / "skills" / name / tail
            for pkg in packages.iterdir()
            if pkg.is_dir()
        ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def check(root: Path) -> list[str]:
    modes = committed_modes(root)
    problems: list[str] = []

    def require_executable(source: Path, where: str, ref: str) -> None:
        rel = source.relative_to(root).as_posix()
        mode = modes.get(rel)
        if mode is None:
            return  # untracked (generated locally); the committed copy governs
        if mode != "100755":
            problems.append(
                f"{where}: invokes '{ref}' as a bare path but {rel} is mode {mode};"
                " chmod +x the source or invoke it through an interpreter"
            )

    for pattern in HOOK_JSON_GLOBS:
        for config in sorted(root.glob(pattern)):
            package = config.parent
            while package.name in {"hooks", ".apm"}:
                package = package.parent
            for command in hook_commands(config):
                for ref in bare_script_refs(command):
                    source = resolve_hook_ref(ref, package)
                    if source is not None:
                        require_executable(source, config.relative_to(root).as_posix(), ref)

    for markdown in sorted((root / "packages").glob("*/.apm/**/*.md")):
        text = markdown.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), 1):
            for match in RUNTIME_PATH_RE.finditer(line):
                if INTERPRETER_RE.search(line[: match.start()]):
                    continue
                source = resolve_runtime_ref(match.group(0), root)
                if source is not None:
                    where = f"{markdown.relative_to(root).as_posix()}:{line_no}"
                    require_executable(source, where, match.group(0))

    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="agentic-packages checkout root",
    )
    args = parser.parse_args()

    problems = check(args.root.resolve())
    if problems:
        print(f"check-script-invocation: {len(problems)} bare-path mode defect(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("check-script-invocation: every bare-path invocation targets an executable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
