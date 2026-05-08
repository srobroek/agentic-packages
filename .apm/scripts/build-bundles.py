#!/usr/bin/env python3
"""Materialize curated wrapper bundles from canonical first-party assets."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APM = ROOT / ".apm"
WRAPPERS = APM / "wrappers"
HOBSON = "wshobson/agents/plugins"
MATT = "mattpocock/skills/skills"
RETIRED_GENERATED_WRAPPERS = ("frontend-design",)


@dataclass(frozen=True)
class McpDependency:
    name: str
    command: str
    args: tuple[str, ...] = ()
    registry: bool = False
    transport: str = "stdio"


@dataclass(frozen=True)
class InlineInstruction:
    filename: str
    content: str


@dataclass(frozen=True)
class Bundle:
    name: str
    description: str
    skills: tuple[str, ...] = ()
    agents: tuple[str, ...] = ()
    instructions: tuple[str, ...] = ()
    inline_instructions: tuple[InlineInstruction, ...] = ()
    contexts: tuple[str, ...] = ()
    scripts: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    mcp_dependencies: tuple[McpDependency, ...] = ()


PLAYWRIGHT_MCP = McpDependency(
    name="playwright",
    command="npx",
    args=("-y", "@anthropic-ai/playwright-mcp@latest"),
)

LSP_GO_MCP = McpDependency(
    name="lsp-go",
    command="mcp-language-server",
    args=("--workspace", ".", "--lsp", "gopls"),
)

LSP_PYTHON_MCP = McpDependency(
    name="lsp-python",
    command="mcp-language-server",
    args=("--workspace", ".", "--lsp", "pyright-langserver", "--lsp-arg", "--stdio"),
)

LSP_RUST_MCP = McpDependency(
    name="lsp-rust",
    command="mcp-language-server",
    args=("--workspace", ".", "--lsp", "rust-analyzer"),
)

LSP_TYPESCRIPT_MCP = McpDependency(
    name="lsp-typescript",
    command="mcp-language-server",
    args=("--workspace", ".", "--lsp", "typescript-language-server", "--lsp-arg", "--stdio"),
)

TOOL_ROUTING_INSTRUCTION = InlineInstruction(
    filename="25-tool-routing.instructions.md",
    content="""---
description: Tool routing preferences for code discovery, GitHub operations, and MCP usage
applyTo: "**/*"
---

Use codebase-memory-mcp for graph-aware code orientation, `rg` for exact text
or path searches, and repomix only for bulk snapshots. Use `gh` for GitHub
operations, context7 for current library docs, and mcp-package-version before
adding dependencies.
""",
)

FRONTEND_TOOLS_INSTRUCTION = InlineInstruction(
    filename="25-frontend-tools.instructions.md",
    content="""---
description: Frontend tool routing including Playwright browser automation
applyTo: "**/*"
---

For UI work, verify in-browser behavior with Playwright MCP after the dev server
is running. Use terminal tools for API checks, static analysis, component unit
tests, and performance benchmarks.
""",
)

QUALITY_TOOLS_INSTRUCTION = InlineInstruction(
    filename="25-quality-tools.instructions.md",
    content="""---
description: Quality analysis CLI tools for dead code, dependencies, and metrics
applyTo: "**/*"
---

Use focused quality tools when their signal fits the task: `knip` for unused
JS/TS exports and dependencies, `madge` for circular imports, `scc` for code
size and complexity, and `sg`/ast-grep for structural searches.
""",
)

SECURITY_TOOLS_INSTRUCTION = InlineInstruction(
    filename="25-security-tools.instructions.md",
    content="""---
description: Security scanning tool routing and CLI patterns
applyTo: "**/*"
---

Use `semgrep` for targeted AST vulnerability checks, `trivy` for dependency,
container, and IaC scans, and the language audit tool for new or changed
dependencies (`npm audit`, `pip-audit`, `cargo audit`, or `bundler-audit`).
""",
)


COMMON_INSTRUCTIONS = (
    "00-agentic-routing",
    "10-subagent-routing",
    "15-toolchain-defaults",
    "20-project-structure",
    "30-frontend",
    "31-frontend-ui",
    "40-backend",
    "41-api-contracts",
    "42-background-jobs",
    "50-data",
    "60-infrastructure",
    "75-docs-specs",
    "80-tools-scripts",
    "90-agentic-source-of-truth",
)

COMMON_CONTEXTS = (
    "agent-routing",
    "backend/api-contracts",
    "backend/background-work",
    "backend/backend-index",
    "data/data-index",
    "docs-specs/docs-specs-index",
    "docs-specs/project-docs",
    "docs-specs/spec-workflow",
    "external-agent-marketplaces",
    "external-assets",
    "frontend/frontend-index",
    "frontend/ui-components",
    "infrastructure/infrastructure-index",
    "languages/go",
    "languages/languages-index",
    "languages/python",
    "languages/rust",
    "languages/terraform",
    "languages/typescript",
    "project-structure/docs-files",
    "project-structure/project-structure-index",
    "project-structure/ownership",
    "project-structure/top-level",
    "source-of-truth",
    "steering-index",
    "toolchain-defaults/frontend",
    "toolchain-defaults/toolchain-defaults-index",
    "toolchain-defaults/infrastructure",
    "toolchain-defaults/languages",
    "toolchain-defaults/quality-observability",
    "tools-scripts/tools-scripts-index",
)

CORE_SKILLS = (
    "catchup",
    "handover",
    "code-review",
    "codebase-index",
    "codebase-memory",
    "commit-push-merge",
    "commit-push-pr",
    "explore",
    "optimize-steering",
    "prompt-lookup",
    "quick-commit",
    "research",
    "steering-audit",
    "unstuck",
    "verify",
    "web-fetch",
    "write-a-skill",
)

CORE_AGENTS = (
    "adversarial-challenger",
    "coder",
    "external-repo-worker",
    "pr-reviewer",
)

SPECKIT_AGENTS = (
    "speckit-implement-task",
    "speckit-research",
    "speckit-sync",
    "speckit-sync-conflicts",
    "speckit-verify",
    "speckit-verify-tasks",
)

LANGUAGE_BUNDLES = (
    Bundle(
        name="language-typescript",
        description="TypeScript and JavaScript quality bundle with language steering and Hobson specialists.",
        skills=("typescript-quality",),
        instructions=("70-language-typescript",),
        contexts=(
            "languages/languages-index",
            "languages/typescript",
            "toolchain-defaults/languages",
            "toolchain-defaults/toolchain-defaults-index",
        ),
        dependencies=(f"{HOBSON}/javascript-typescript#main",),
        mcp_dependencies=(LSP_TYPESCRIPT_MCP,),
    ),
    Bundle(
        name="language-python",
        description="Python quality bundle with language steering and Hobson specialists.",
        skills=("python-quality",),
        instructions=("71-language-python",),
        contexts=(
            "languages/languages-index",
            "languages/python",
            "toolchain-defaults/languages",
            "toolchain-defaults/toolchain-defaults-index",
        ),
        dependencies=(f"{HOBSON}/python-development#main",),
        mcp_dependencies=(LSP_PYTHON_MCP,),
    ),
    Bundle(
        name="language-go",
        description="Go quality bundle with language steering and Hobson systems specialists.",
        skills=("go-quality",),
        instructions=("72-language-go",),
        contexts=(
            "languages/languages-index",
            "languages/go",
            "toolchain-defaults/languages",
            "toolchain-defaults/toolchain-defaults-index",
        ),
        dependencies=(f"{HOBSON}/systems-programming#main",),
        mcp_dependencies=(LSP_GO_MCP,),
    ),
    Bundle(
        name="language-rust",
        description="Rust quality bundle with language steering and Hobson systems specialists.",
        skills=("rust-quality",),
        instructions=("73-language-rust",),
        contexts=(
            "languages/languages-index",
            "languages/rust",
            "toolchain-defaults/languages",
            "toolchain-defaults/toolchain-defaults-index",
        ),
        dependencies=(f"{HOBSON}/systems-programming#main",),
        mcp_dependencies=(LSP_RUST_MCP,),
    ),
    Bundle(
        name="language-terraform",
        description="Terraform steering bundle with Hobson deployment and Terraform specialists.",
        instructions=("74-language-terraform",),
        contexts=(
            "infrastructure/infrastructure-index",
            "languages/languages-index",
            "languages/terraform",
        ),
        dependencies=(f"{HOBSON}/deployment-strategies#main",),
    ),
    Bundle(
        name="language-shell",
        description="Shell scripting bundle with Hobson Bash and POSIX specialists.",
        dependencies=(f"{HOBSON}/shell-scripting#main",),
    ),
    Bundle(
        name="language-dotnet",
        description=".NET development bundle with Hobson C# and ASP.NET specialists.",
        dependencies=(f"{HOBSON}/dotnet-contribution#main",),
    ),
    Bundle(
        name="language-jvm",
        description="JVM language bundle with Hobson Java, Scala, and enterprise specialists.",
        dependencies=(f"{HOBSON}/jvm-languages#main",),
    ),
    Bundle(
        name="language-web-scripting",
        description="PHP and Ruby web scripting bundle with Hobson specialists.",
        dependencies=(f"{HOBSON}/web-scripting#main",),
    ),
    Bundle(
        name="language-functional",
        description="Functional programming bundle with Hobson Elixir and Haskell specialists.",
        dependencies=(f"{HOBSON}/functional-programming#main",),
    ),
    Bundle(
        name="language-julia",
        description="Julia development bundle with Hobson scientific computing specialists.",
        dependencies=(f"{HOBSON}/julia-development#main",),
    ),
    Bundle(
        name="language-arm-cortex",
        description="ARM Cortex-M firmware bundle with Hobson embedded specialists.",
        dependencies=(f"{HOBSON}/arm-cortex-microcontrollers#main",),
    ),
)

BUNDLES: tuple[Bundle, ...] = (
    Bundle(
        name="core",
        description=(
            "Deterministic shared project baseline with core agents, code intelligence, "
            "project lifecycle, agentic maintenance, first-party skill writing, and "
            "Matt grill/diagnose workflows."
        ),
        skills=CORE_SKILLS,
        agents=CORE_AGENTS,
        instructions=COMMON_INSTRUCTIONS,
        inline_instructions=(TOOL_ROUTING_INSTRUCTION,),
        contexts=COMMON_CONTEXTS,
        scripts=("write-claude-pointers", "strip-constitution-blocks", "prune-stale-local-packages"),
        dependencies=(
            f"{MATT}/engineering/diagnose#main",
            f"{MATT}/productivity/grill-me#main",
            f"{MATT}/engineering/grill-with-docs#main",
            f"{HOBSON}/context-management#main",
            f"{HOBSON}/agent-orchestration#main",
        ),
    ),
    Bundle(
        name="developer-tools",
        description="Hobson developer tooling bundle for everyday development, debugging, review, PR, and documentation generation workflows.",
        dependencies=(
            f"{HOBSON}/developer-essentials#main",
            f"{HOBSON}/debugging-toolkit#main",
            f"{HOBSON}/comprehensive-review#main",
            f"{HOBSON}/git-pr-workflows#main",
            f"{HOBSON}/documentation-generation#main",
        ),
    ),
    Bundle(
        name="code-intelligence",
        description="Codebase understanding bundle with graph/index/search skills, PR review, and Hobson documentation/architecture agents.",
        skills=(
            "codebase-index",
            "codebase-memory",
            "explore",
            "prompt-lookup",
            "research",
            "web-fetch",
        ),
        agents=("pr-reviewer",),
        contexts=(
            "agent-routing",
            "project-structure/docs-files",
            "project-structure/project-structure-index",
            "project-structure/ownership",
            "project-structure/top-level",
            "source-of-truth",
        ),
        dependencies=(
            f"{HOBSON}/code-documentation#main",
            f"{HOBSON}/documentation-generation#main",
            f"{HOBSON}/c4-architecture#main",
        ),
    ),
    Bundle(
        name="project-lifecycle",
        description="Project lifecycle bundle for catchup, handover, local commits, PRs, merges, and verification.",
        skills=(
            "catchup",
            "handover",
            "commit-push-merge",
            "commit-push-pr",
            "quick-commit",
            "verify",
        ),
        agents=("pr-reviewer",),
    ),
    Bundle(
        name="quality",
        description="Cross-language quality bundle for reviews, verification, language checks, and Hobson test/review workflows.",
        skills=(
            "code-review",
            "go-quality",
            "python-quality",
            "rust-quality",
            "typescript-quality",
            "verify",
        ),
        agents=("pr-reviewer",),
        inline_instructions=(QUALITY_TOOLS_INSTRUCTION,),
        dependencies=(
            f"{HOBSON}/comprehensive-review#main",
            f"{HOBSON}/performance-testing-review#main",
            f"{HOBSON}/unit-testing#main",
            f"{HOBSON}/tdd-workflows#main",
        ),
    ),
    Bundle(
        name="speckit",
        description="SpecKit workflow bundle with SpecKit agents, bugfix skill, and docs/spec steering.",
        skills=("speckit-bugfix",),
        agents=SPECKIT_AGENTS,
        instructions=("75-docs-specs",),
        contexts=("source-of-truth", "steering-index"),
    ),
    Bundle(
        name="agentic-maintenance",
        description="Agentic asset maintenance bundle with steering audit, optimization, prompt lookup, first-party skill writing, and Hobson plugin/documentation evaluation.",
        skills=("optimize-steering", "prompt-lookup", "steering-audit", "write-a-skill"),
        agents=("coder", "pr-reviewer"),
        instructions=("90-agentic-source-of-truth",),
        contexts=("source-of-truth", "steering-index"),
        dependencies=(
            f"{HOBSON}/documentation-standards#main",
            f"{HOBSON}/plugin-eval#main",
        ),
    ),
    Bundle(
        name="debugging",
        description="Debugging escalation bundle with diagnose, unstuck, adversarial challenge, and Hobson debugging agents.",
        skills=("unstuck",),
        agents=("adversarial-challenger",),
        dependencies=(
            f"{MATT}/engineering/diagnose#main",
            f"{HOBSON}/debugging-toolkit#main",
            f"{HOBSON}/error-debugging#main",
            f"{HOBSON}/error-diagnostics#main",
            f"{HOBSON}/distributed-debugging#main",
            f"{HOBSON}/incident-response#main",
        ),
    ),
    Bundle(
        name="frontend",
        description="Frontend development and design bundle with Impeccable, Interface Design, Stitch skills, Playwright browser automation MCP, and Hobson frontend/UI/accessibility agents.",
        skills=("playwright",),
        instructions=("30-frontend", "31-frontend-ui"),
        inline_instructions=(FRONTEND_TOOLS_INSTRUCTION,),
        dependencies=(
            "pbakaus/impeccable/.agents/skills/impeccable#main",
            "Dammyjay93/interface-design/.claude/skills/interface-design#main",
            "google-labs-code/stitch-skills#main",
            f"{HOBSON}/frontend-mobile-development#main",
            f"{HOBSON}/ui-design#main",
            f"{HOBSON}/accessibility-compliance#main",
            f"{HOBSON}/brand-landingpage#main",
        ),
        mcp_dependencies=(PLAYWRIGHT_MCP,),
    ),
    Bundle(
        name="docs-architecture",
        description="Documentation and architecture bundle with Hobson documentation, HADS, OpenAPI, Mermaid, and C4 workflows.",
        dependencies=(
            f"{HOBSON}/documentation-standards#main",
            f"{HOBSON}/code-documentation#main",
            f"{HOBSON}/documentation-generation#main",
            f"{HOBSON}/c4-architecture#main",
        ),
    ),
    Bundle(
        name="infrastructure",
        description="Infrastructure bundle with Hobson cloud, Kubernetes, CI/CD, observability, and deployment workflows.",
        instructions=("60-infrastructure", "74-language-terraform"),
        dependencies=(
            f"{HOBSON}/cloud-infrastructure#main",
            f"{HOBSON}/kubernetes-operations#main",
            f"{HOBSON}/cicd-automation#main",
            f"{HOBSON}/deployment-strategies#main",
            f"{HOBSON}/deployment-validation#main",
            f"{HOBSON}/observability-monitoring#main",
        ),
    ),
    Bundle(
        name="security",
        description="Security bundle with Hobson scanning, compliance, API security, frontend security, and reverse-engineering workflows.",
        inline_instructions=(SECURITY_TOOLS_INSTRUCTION,),
        dependencies=(
            f"{HOBSON}/security-scanning#main",
            f"{HOBSON}/security-compliance#main",
            f"{HOBSON}/backend-api-security#main",
            f"{HOBSON}/frontend-mobile-security#main",
            f"{HOBSON}/reverse-engineering#main",
        ),
    ),
    Bundle(
        name="data-ai",
        description="Data and AI bundle with Hobson LLM application, data engineering, MLOps, and database optimization workflows.",
        instructions=("50-data",),
        dependencies=(
            f"{HOBSON}/llm-application-dev#main",
            f"{HOBSON}/data-engineering#main",
            f"{HOBSON}/machine-learning-ops#main",
            f"{HOBSON}/database-design#main",
            f"{HOBSON}/database-migrations#main",
            f"{HOBSON}/database-cloud-optimization#main",
        ),
    ),
    Bundle(
        name="governance",
        description="Governance bundle with Hobson MCP protection, signed audit trails, and review policy workflows.",
        dependencies=(
            f"{HOBSON}/protect-mcp#main",
            f"{HOBSON}/signed-audit-trails#main",
            f"{HOBSON}/review-agent-governance#main",
            f"{HOBSON}/block-no-verify#main",
        ),
    ),
    Bundle(
        name="planning-product",
        description="Planning and product bundle with first-party debate/research plus Matt PRD, issue, TDD, triage, and architecture workflows.",
        skills=("debate", "eli5", "research", "web-fetch"),
        dependencies=(
            f"{MATT}/engineering/to-prd#main",
            f"{MATT}/engineering/to-issues#main",
            f"{MATT}/engineering/tdd#main",
            f"{MATT}/engineering/triage#main",
            f"{MATT}/engineering/zoom-out#main",
            f"{MATT}/engineering/improve-codebase-architecture#main",
        ),
    ),
    *LANGUAGE_BUNDLES,
)


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def yaml_scalar(value: str) -> str:
    if value.startswith("@") or ":" in value or value.lower() in {"true", "false", "null"}:
        return "'" + value.replace("'", "''") + "'"
    return value


def materialize_bundle(bundle: Bundle) -> None:
    target = WRAPPERS / bundle.name
    target.mkdir(parents=True, exist_ok=True)

    nested_apm = target / ".apm"
    if nested_apm.exists():
        shutil.rmtree(nested_apm)

    for skill in bundle.skills:
        copy_tree(APM / "skills" / skill, nested_apm / "skills" / skill)

    for agent in bundle.agents:
        filename = f"{agent}.agent.md"
        copy_file(APM / "agents" / filename, nested_apm / "agents" / filename)

    for instruction in bundle.instructions:
        filename = f"{instruction}.instructions.md"
        copy_file(APM / "instructions" / filename, nested_apm / "instructions" / filename)

    for instruction in bundle.inline_instructions:
        path = nested_apm / "instructions" / instruction.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(instruction.content.rstrip() + "\n", encoding="utf-8")

    for context in bundle.contexts:
        filename = f"{context}.context.md"
        copy_file(APM / "context" / filename, nested_apm / "context" / filename)

    for script in bundle.scripts:
        filename = f"{script}.py"
        copy_file(APM / "scripts" / filename, nested_apm / "scripts" / filename)

    lines = [
        f"name: {bundle.name}",
        "version: 0.1.0",
        f"description: {bundle.description}",
        "author: Sjors Robroek",
        "license: MIT",
        "type: hybrid",
        "target: all",
        "includes: auto",
    ]
    if bundle.dependencies or bundle.mcp_dependencies:
        lines.extend(["", "dependencies:"])
    if bundle.dependencies:
        lines.append("  apm:")
        lines.extend(f"    - {dependency}" for dependency in bundle.dependencies)
    if bundle.mcp_dependencies:
        lines.append("  mcp:")
        for dependency in bundle.mcp_dependencies:
            lines.extend(
                [
                    f"    - name: {dependency.name}",
                    f"      registry: {str(dependency.registry).lower()}",
                    f"      transport: {dependency.transport}",
                    f"      command: {dependency.command}",
                ]
            )
            if dependency.args:
                lines.append("      args:")
                lines.extend(f"        - {yaml_scalar(arg)}" for arg in dependency.args)

    (target / "apm.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    for wrapper_name in RETIRED_GENERATED_WRAPPERS:
        wrapper = WRAPPERS / wrapper_name
        if wrapper.exists():
            shutil.rmtree(wrapper)
            print(f"removed {wrapper}")

    for bundle in BUNDLES:
        materialize_bundle(bundle)
        print(f"updated {WRAPPERS / bundle.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
