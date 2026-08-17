#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Inject package-owned model mappings into APM-generated Codex agents."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path

import yaml

MAPPING_NAME = "agent-models.yml"
ALLOWED_CODEX_FIELDS = {"model", "reasoning_effort"}
AGENT_NAME = re.compile(r"^name:\s*[\"']?([^\"'\s]+)", re.MULTILINE)


class MappingError(ValueError):
    pass


def mapping_files(root: Path) -> list[Path]:
    candidates = [root / ".apm" / MAPPING_NAME]
    candidates.extend(root.glob(f"packages/*/.apm/{MAPPING_NAME}"))
    candidates.extend(root.glob(f"apm_modules/**/.apm/{MAPPING_NAME}"))
    candidates.extend(root.glob(f".apm/apm_modules/**/.apm/{MAPPING_NAME}"))
    resolved = {path.resolve() for path in candidates if path.is_file()}
    return sorted(path for path in resolved if ".apm-resolution-staging" not in path.parts)


def load_mappings(root: Path) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    origins: dict[str, Path] = {}
    for path in mapping_files(root):
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise MappingError(f"{path}: invalid YAML: {exc}") from exc
        if not isinstance(document, dict):
            raise MappingError(f"{path}: document must be a mapping")
        if type(document.get("version")) is not int or document["version"] != 1:
            raise MappingError(f"{path}: version must be 1")
        agents = document.get("agents") or {}
        if not isinstance(agents, dict):
            raise MappingError(f"{path}: agents must be a mapping")
        for name, runtime_data in agents.items():
            if not isinstance(name, str) or not name.strip():
                raise MappingError(f"{path}: agent names must be non-empty strings")
            name = name.strip()
            codex = runtime_data.get("codex") if isinstance(runtime_data, dict) else None
            if not isinstance(codex, dict) or not codex:
                raise MappingError(f"{path}: {name}.codex must be a non-empty mapping")
            unknown = sorted(str(key) for key in codex if key not in ALLOWED_CODEX_FIELDS)
            if unknown:
                raise MappingError(f"{path}: {name}.codex has unknown fields {unknown}")
            normalized: dict[str, str] = {}
            for field in ALLOWED_CODEX_FIELDS:
                value = codex.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise MappingError(
                        f"{path}: {name}.codex requires non-empty string {field}"
                    )
                normalized[field] = value.strip()
            if name in merged:
                if merged[name] == normalized:
                    continue  # identical re-declaration across bundles; first occurrence wins
                raise MappingError(
                    f"conflicting mapping for {name}:\n"
                    f"  {origins[name]}: {merged[name]}\n"
                    f"  {path}: {normalized}"
                )
            merged[str(name)] = normalized
            origins[str(name)] = path
    return merged


def agent_source_files(root: Path) -> list[Path]:
    # Check both authored package agent trees and the target-specific APM tree;
    # deployed `.codex/agents` coverage remains enforced by `patch_codex`.
    candidates = list(root.glob("packages/*/agents/*.md"))
    candidates.extend(root.glob("packages/*/.apm/agents/*.agent.md"))
    candidates.extend(root.glob(".apm/agents/*.agent.md"))
    return sorted({path.resolve() for path in candidates if path.is_file()})


def validate_source_coverage(root: Path, mappings: dict[str, dict[str, str]]) -> None:
    missing: list[str] = []
    for path in agent_source_files(root):
        match = AGENT_NAME.search(path.read_text(encoding="utf-8"))
        if match is None:
            raise MappingError(f"agent source has no frontmatter name: {path}")
        name = match.group(1)
        if name not in mappings:
            missing.append(f"agent source lacks {MAPPING_NAME} entry: {path} ({name})")
    if missing:
        raise MappingError("\n".join(missing))


def set_toml_string(text: str, key: str, value: str) -> str:
    line = f"{key} = {json.dumps(value, ensure_ascii=False)}"
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    in_table = False
    first_table = None
    root_key = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for index, current in enumerate(lines):
        stripped = current.lstrip()
        if stripped.startswith("["):
            in_table = True
            if first_table is None:
                first_table = index
        if not in_table and root_key.match(current):
            ending = "\r\n" if current.endswith("\r\n") else "\n" if current.endswith("\n") else ""
            lines[index] = line + (ending or newline)
            return "".join(lines)

    # Codex agent fields are root-level TOML keys. Insert before the first
    # table so a generated file without developer_instructions cannot
    # accidentally place them inside a nested table.
    if first_table is not None:
        lines.insert(first_table, line + newline)
        return "".join(lines)

    for index, current in enumerate(lines):
        if re.match(r"^\s*developer_instructions\s*=", current):
            lines.insert(index, line + newline)
            return "".join(lines)

    return text.rstrip("\r\n") + newline + line + newline


def expected_text(text: str, mapping: dict[str, str]) -> str:
    text = set_toml_string(text, "model", mapping["model"])
    return set_toml_string(
        text,
        "model_reasoning_effort",
        mapping["reasoning_effort"],
    )


def patch_codex(root: Path, mappings: dict[str, dict[str, str]], *, check: bool) -> int:
    agents_dir = root / ".codex" / "agents"
    errors: list[str] = []
    changed = 0
    pending: list[tuple[Path, str]] = []
    deployed: dict[str, Path] = {}
    for path in sorted(agents_dir.glob("*.toml")):
        try:
            parsed = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"invalid deployed Codex agent {path}: {exc}")
            continue
        name = parsed.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"deployed Codex agent has no name: {path}")
            continue
        if name in deployed:
            errors.append(
                f"duplicate deployed Codex agent name {name}: {deployed[name]} and {path}"
            )
            continue
        deployed[name] = path

    # Only APM-managed agents (those a currently-installed package maps) are
    # injected. A deployed toml with no mapping is not APM's to own -- a
    # hand-authored agent, or an orphan left by a retired/removed package -- so
    # skip it instead of failing the lifecycle at deploy. Package-level coverage
    # (every APM agent source has a mapping) is enforced in CI by
    # validate_source_coverage, so re-checking it here would only duplicate CI
    # and false-positive on non-APM files.
    unmanaged = sorted(name for name in deployed if name not in mappings)
    if unmanaged:
        print(f"Codex agent models: skipping {len(unmanaged)} unmanaged deployed agent(s): {', '.join(unmanaged)}")

    for name, mapping in sorted(mappings.items()):
        path = deployed.get(name)
        if path is None:
            errors.append(f"missing deployed Codex agent: {agents_dir / f'{name}.toml'}")
            continue
        current = path.read_text(encoding="utf-8")
        desired = expected_text(current, mapping)
        try:
            parsed = tomllib.loads(desired)
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"invalid generated TOML for {path}: {exc}")
            continue
        if parsed.get("model") != mapping["model"]:
            errors.append(f"model injection failed for {path}")
            continue
        if parsed.get("model_reasoning_effort") != mapping["reasoning_effort"]:
            errors.append(f"reasoning effort injection failed for {path}")
            continue
        if desired == current:
            continue
        changed += 1
        pending.append((path, desired))

    if errors:
        raise MappingError("\n".join(errors))
    if not check:
        for path, desired in pending:
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(desired, encoding="utf-8")
            os.replace(temporary, path)
    verb = "need injection" if check else "injected"
    print(f"Codex agent models: {changed} {verb}; {len(mappings) - changed} already current")
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root containing .codex/agents")
    parser.add_argument("--check", action="store_true", help="Report drift without writing")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    try:
        mappings = load_mappings(root)
        if not mappings:
            raise MappingError(f"no {MAPPING_NAME} files found below {root}")
        validate_source_coverage(root, mappings)
        changed = patch_codex(root, mappings, check=args.check)
    except MappingError as exc:
        print(f"agent model injection failed: {exc}", file=sys.stderr)
        return 1
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
