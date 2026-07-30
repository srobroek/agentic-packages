#!/usr/bin/env python3
"""CI check: hook scripts must agree with the manifests and targets that ship them.

Every defect a recent audit of this repository found was a WIRING defect, and each
one passed a fully green pipeline. The existing checks validate invocation modes,
release baselines, applyTo coverage, and Codex manifest shape; none reads what a
hook script does against what its manifest and target claim it does.

Three rules, each mechanically decidable from the committed files:

1. A tool surface the script branches on appears in a matcher that routes it.
   `hooks-chezmoi-guard` carried an `apply_patch` branch no matcher ever bound, so
   the branch was dead under Codex while the docs claimed the alias was covered.

2. A script in a `target: all` package emits only fields both tools accept, and no
   script anywhere emits `permissionDecision: "ask"`. `hooks-git-workflow` emitted
   `systemMessage`, a Claude-only field, so under Codex it did its work and then
   emitted something Codex ignores. The `ask` ban is constitution III and was
   enforced by nothing.

3. Every hook script ships a test suite, which is authoring rule 3 of the contract
   and likewise enforced by nothing.

Deliberately excluded: anything that infers intent, compares documentation prose
against behavior, or asserts that two packages' wrapper tables match. That last one
was proposed and rejected during the audit -- it encodes a false invariant, because
`hooks-git-safety` legitimately handles git options `hooks-bash-safety` does not.

The predecessor of this check, check-hook-wiring.py, was deleted for passing
silently: it required a settings profile that exists only in a chezmoi checkout, and
printed success when handed nothing. A check that cannot fail is worse than no
check, because it reads as coverage. Hence test_check_hook_contract.py, which feeds
this deliberately broken fixtures and asserts it rejects them.

Exit 0 when clean, 1 with a per-finding report otherwise.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / "packages"

# Tool surfaces a PreToolUse matcher can name. `apply_patch` is Codex's alias for
# the edit tools; the contract asserts the alias, and several packages list it
# explicitly rather than relying on it.
TOOL_SURFACES = (
    "apply_patch",
    "MultiEdit",
    "Edit",
    "Write",
    "Bash",
    "Agent",
    "Skill",
    "Read",
    "Task",
)

# Tools only one agent exposes. A manifest is not at fault for omitting a tool the
# tool's own agent does not have, so these are required only in a manifest that
# faces the agent providing them. `speckit` splits exactly this way: its
# codex-hooks.json binds `apply_patch` and its claude-hooks.json correctly does not.
TOOL_OWNER = {"apply_patch": "codex"}


def manifest_audience(manifest: Path) -> str:
    """Which agent a manifest targets, inferred from its filename.

    A `*-claude-hooks.json` / `*-codex-hooks.json` pair is the repository's
    convention for target-specific wiring; anything else serves both.
    """
    name = manifest.name
    if "claude" in name:
        return "claude"
    if "codex" in name:
        return "codex"
    return "all"

# Fields only Claude consumes. A `target: all` package that emits one of these is a
# silent no-op on Codex for that path.
CLAUDE_ONLY_FIELDS = (
    "systemMessage",
    "suppressOutput",
    "stopReason",
)

# Where a script decides which tool it was invoked for. Matching an EMISSION or a
# comparison rather than any mention of the word: every guard in this repository
# discusses tool names and decisions in its header comment, and a substring check
# would flag all of them and promptly be muted.
# TOOL is substituted textually rather than through str.format, whose field syntax
# collides with the braces these patterns need.
BRANCH_PATTERNS = (
    # Python: tool_name == "Edit", tool_name in ("Edit", "Write"), in {"Edit"}
    r'tool_name\s*(?:==|!=|\bin\b)\s*[\(\{\[]?[^\n\)\}\]]*?["\']TOOL["\']',
    # Shell: case "$tool_name" in Edit|Write)
    r'case\s+"?\$\{?tool_name\}?"?\s+in(?:[^\n]*\n){0,12}?[^\n]*\bTOOL\b[^\n]*\)',
    # Shell: [ "$tool_name" = "Edit" ]
    r'\$\{?tool_name\}?"?\s*(?:=|==)\s*"?TOOL\b',
)

# `permissionDecision: "ask"` as an emitted value, in either language, rather than
# the word appearing in prose about the ban.
ASK_EMISSION = re.compile(
    r"""permissionDecision["']?\s*[:=]\s*["']ask["']"""
    r"""|["']permissionDecision["']\s*:\s*["']ask["']"""
    r"""|--arg\s+\w+\s+["']ask["']""",
)

# A Claude-only field being WRITTEN into hook output: a JSON key, or a jq object key.
def claude_only_emission(field: str) -> re.Pattern[str]:
    return re.compile(
        rf'["\']?{field}["\']?\s*:\s*(?:\$|["\'{{])'  # jq or dict literal key
        rf'|["\']{field}["\']\s*:'  # plain JSON key
    )


# Packages allowed to ship a hook script with no suite. Empty, and meant to stay
# that way: the packages listed when this check was introduced (beads,
# speckit) all have suites now. An entry here is recorded debt rather than
# a silent skip, and the check fails on a stale entry, so a listing cannot
# outlive the gap it describes.
UNTESTED_HOOK_PACKAGES: set[str] = set()


class Finding:
    def __init__(self, rule: str, where: str, detail: str) -> None:
        self.rule = rule
        self.where = where
        self.detail = detail

    def __str__(self) -> str:
        return f"[{self.rule}] {self.where}: {self.detail}"


def hook_manifests(package: Path) -> list[Path]:
    """Every hook manifest a package ships, native and APM."""
    return sorted(
        path
        for path in package.rglob("*.json")
        if "hooks" in path.parts or "hooks" in path.name
        if path.name.endswith(".json") and "hooks" in path.as_posix()
    )


def manifest_matchers(manifest: Path) -> tuple[set[str], set[str]]:
    """The matcher alternatives and event names ONE manifest binds."""
    matchers: set[str] = set()
    events: set[str] = set()
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return matchers, events
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return matchers, events
    for event, entries in hooks.items():
        events.add(event)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            matcher = entry.get("matcher")
            if isinstance(matcher, str):
                # An empty matcher means every tool, so it binds everything.
                matchers.update(matcher.split("|") if matcher else ["*"])
    return matchers, events


def matchers_and_events(package: Path) -> tuple[set[str], set[str]]:
    """Every matcher and event the package binds, across all its manifests."""
    matchers: set[str] = set()
    events: set[str] = set()
    for manifest in hook_manifests(package):
        found_matchers, found_events = manifest_matchers(manifest)
        matchers |= found_matchers
        events |= found_events
    return matchers, events


def hook_scripts(package: Path) -> list[Path]:
    """Scripts a hook manifest actually invokes, by name."""
    referenced: set[str] = set()
    for manifest in hook_manifests(package):
        text = manifest.read_text(encoding="utf-8", errors="replace")
        referenced.update(re.findall(r"scripts/([A-Za-z0-9_.-]+\.(?:py|sh))", text))
    directory = package / "scripts"
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.iterdir() if path.name in referenced)


def package_target(package: Path) -> str:
    manifest = package / "apm.yml"
    if not manifest.is_file():
        return ""
    try:
        meta = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return ""
    target = meta.get("target")
    return target if isinstance(target, str) else ""


def branches_on(source: str, tool: str) -> bool:
    """Whether the script dispatches on `tool` as a tool-name value."""
    for template in BRANCH_PATTERNS:
        pattern = template.replace("TOOL", re.escape(tool))
        if re.search(pattern, source, re.MULTILINE):
            return True
    return False


def check_matcher_coverage(package: Path, scripts: list[Path]) -> list[Finding]:
    """Each manifest is judged alone, not against the union of them all.

    A package's native and APM manifests are separate deploy targets and drift apart
    independently, so unioning their matchers lets one file mask a gap in the other:
    dropping `apply_patch` from `hooks/hooks.json` went unnoticed while
    `.apm/hooks/hooks.json` still listed it.
    """
    findings: list[Finding] = []
    sources = {
        script: script.read_text(encoding="utf-8", errors="replace") for script in scripts
    }
    for manifest in hook_manifests(package):
        matchers, events = manifest_matchers(manifest)
        if not events or "*" in matchers:
            # No hooks here, or an empty matcher that routes every tool.
            continue
        relative = manifest.relative_to(package).as_posix()
        for script, source in sources.items():
            if script.name not in manifest.read_text(encoding="utf-8", errors="replace"):
                # This manifest does not invoke this script.
                continue
            audience = manifest_audience(manifest)
            for tool in TOOL_SURFACES:
                owner = TOOL_OWNER.get(tool)
                if owner is not None and audience not in (owner, "all"):
                    # This agent does not expose the tool, so its manifest is right
                    # to omit it; the paired manifest carries the binding.
                    continue
                if branches_on(source, tool) and tool not in matchers:
                    findings.append(
                        Finding(
                            "matcher-coverage",
                            f"{package.name}/{relative}",
                            f"scripts/{script.name} branches on tool {tool!r}, but no "
                            f"matcher here routes it (matchers: "
                            f"{sorted(m for m in matchers if m) or 'none'}). The branch "
                            f"is unreachable; add {tool!r} to the matcher or drop the "
                            f"branch.",
                        )
                    )
    return findings


def check_output_fields(package: Path, scripts: list[Path], target: str) -> list[Finding]:
    findings: list[Finding] = []
    for script in scripts:
        source = script.read_text(encoding="utf-8", errors="replace")

        if ASK_EMISSION.search(source):
            findings.append(
                Finding(
                    "no-ask",
                    f"{package.name}/scripts/{script.name}",
                    'emits permissionDecision "ask", which waits for a human and '
                    "stalls an autonomous run. Constitution III forbids it: deny "
                    "with actionable guidance, or allow with an advisory.",
                )
            )

        if target != "all":
            continue
        for field in CLAUDE_ONLY_FIELDS:
            if claude_only_emission(field).search(source):
                findings.append(
                    Finding(
                        "cross-tool-output",
                        f"{package.name}/scripts/{script.name}",
                        f"emits {field!r}, which only Claude consumes, but the "
                        f"package declares target: all. Under Codex this path is a "
                        f"silent no-op. Emit a field from the cross-tool decision "
                        f"table, or narrow the package target.",
                    )
                )
    return findings


def has_test_suite(package: Path) -> bool:
    """Whether the package ships a suite under any convention the contract lists.

    Searched package-wide rather than only under tests/, because `orchestrate`
    legitimately keeps `scripts/rules-eval-test.py` and `_test_*.py` beside the code
    they cover. Naming is what identifies a suite here, not location.
    """
    for candidate in package.rglob("*"):
        if not candidate.is_file():
            continue
        if candidate.suffix == ".bats":
            return True
        name = candidate.name
        if candidate.suffix == ".py" and (
            name.startswith(("test_", "_test_")) or name.endswith(("-test.py", "_test.py"))
        ):
            return True
    return False


def check_tests_exist(package: Path, scripts: list[Path]) -> list[Finding]:
    if not scripts or has_test_suite(package):
        return []
    if package.name in UNTESTED_HOOK_PACKAGES:
        return []
    return [
        Finding(
            "test-coverage",
            package.name,
            f"ships {len(scripts)} hook script(s) and no test suite anywhere in the "
            f"package. Authoring rule 3 requires *.bats, test_*.py, or _test_*.py; a "
            f"guard's negative cases matter more than its positive ones.",
        )
    ]


def main() -> int:
    if not PACKAGES.is_dir():
        print(f"check-hook-contract: no packages directory at {PACKAGES}", file=sys.stderr)
        return 1

    findings: list[Finding] = []
    inspected = 0
    still_untested: set[str] = set()

    for package in sorted(PACKAGES.iterdir()):
        if not package.is_dir():
            continue
        matchers, events = matchers_and_events(package)
        if not events:
            continue
        scripts = hook_scripts(package)
        if not scripts:
            continue
        inspected += 1
        target = package_target(package)
        findings.extend(check_matcher_coverage(package, scripts))
        findings.extend(check_output_fields(package, scripts, target))
        findings.extend(check_tests_exist(package, scripts))
        if package.name in UNTESTED_HOOK_PACKAGES and not has_test_suite(package):
            still_untested.add(package.name)

    # An allowlist entry that no longer describes a real gap is worse than no entry,
    # because it silently exempts a package that has since grown a suite -- and would
    # keep exempting one that later loses it.
    #
    # Only entries whose package is actually present are judged. A synthetic tree
    # holding one test fixture must not be told that every allowlisted package has
    # been fixed.
    present = {package.name for package in PACKAGES.iterdir() if package.is_dir()}
    stale = (UNTESTED_HOOK_PACKAGES & present) - still_untested
    for name in sorted(stale):
        findings.append(
            Finding(
                "stale-allowlist",
                name,
                "is listed in UNTESTED_HOOK_PACKAGES but now has a test suite (or no "
                "longer ships a hook script). Remove it from the list so the rule "
                "applies again.",
            )
        )

    if not inspected:
        # The predecessor of this check reported success while inspecting nothing.
        print(
            "check-hook-contract: inspected no hook packages, which means the "
            "discovery above is broken rather than the repository being clean",
            file=sys.stderr,
        )
        return 1

    for finding in findings:
        print(f"ERROR: {finding}", file=sys.stderr)
    print(f"check-hook-contract: {inspected} hook package(s), {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
