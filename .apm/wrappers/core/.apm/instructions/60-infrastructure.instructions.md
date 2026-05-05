---
description: Infrastructure, platform, IaC, and pipeline steering.
applyTo: "{infrastructure/**,**/*.tf,**/*.hcl,.github/workflows/**}"
---

# Infrastructure

Use root `infrastructure/` for shared platform/IaC. Keep service-local deployment
config with the owning deployable when it is not shared platform state.

Terraform/OpenTofu is the baseline. CDK is opt-in when application code and AWS
constructs are tightly coupled. Kubernetes and Helm are opt-in platform
capabilities.

Prefer official/vendor Terraform modules first, maintained community modules
second, and custom thin wrappers last.
