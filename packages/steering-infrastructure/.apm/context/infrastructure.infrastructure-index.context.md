# Infrastructure Context

Use this context for infrastructure, platform code, deployment config, CI/CD,
Terraform, OpenTofu, CDK, Kubernetes, Helm, environments, policies, and
observability infrastructure.

Use root `infrastructure/` for shared platform and IaC. Keep service-local
deployment config with the owning deployable when it is not shared platform
state.

Terraform or OpenTofu is the baseline. Prefer official or vendor modules first,
maintained community modules second, and custom thin wrappers last.

Use CDK only when application code and AWS constructs are tightly coupled enough
to justify that tradeoff. Use Kubernetes and Helm only when the project already
has, or clearly needs, platform-level orchestration.
