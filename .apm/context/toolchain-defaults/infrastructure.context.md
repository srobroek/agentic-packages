# Infrastructure Defaults

Use Terraform or OpenTofu as the baseline for shared infrastructure.

Use CDK only when application code and AWS constructs are tightly coupled enough
to justify that tradeoff. Use Kubernetes and Helm only when the project already
has, or clearly needs, platform-level orchestration.

Treat `just`, `mise`, and `moon` as independent setup choices:

- `just` for task aliases and repeatable local workflows.
- `mise` for language and tool version management.
- `moon` for task orchestration in larger monorepos.
