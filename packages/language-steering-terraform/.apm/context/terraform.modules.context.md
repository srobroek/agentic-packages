# Terraform Module and State Defaults

- Prefer official vendor modules, then maintained community modules, then thin
  custom wrappers. Document the rationale when bypassing official or community
  modules.
- Use remote state with locking for shared stacks, never local state. Prefer a
  managed backend (HCP Terraform/Terraform Cloud, or the platform's native
  state backend); when self-managing, default to S3 with state locking, or the
  equivalent for your cloud.
- Pin provider and module versions; use `~>` constraints and commit the
  `.terraform.lock.hcl`.
- Keep environments and stacks explicit; separate state per environment.
- Run `terraform fmt` and `terraform validate` before plan; gate applies behind
  a reviewed plan.
