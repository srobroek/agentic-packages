# Terraform Module and State Defaults

- Prefer official vendor modules, then maintained community modules, then thin
  custom wrappers. Document the rationale when bypassing official or community
  modules.
- Use remote state with locking (e.g. an S3 backend with DynamoDB lock table,
  or the equivalent for your cloud) rather than local state for shared stacks.
- Pin provider and module versions; use `~>` constraints and commit the
  `.terraform.lock.hcl`.
- Keep environments and stacks explicit; separate state per environment.
- Run `terraform fmt` and `terraform validate` before plan; gate applies behind
  a reviewed plan.

Keep existing project choices unless the task is explicitly about setup,
migration, or standardization.
