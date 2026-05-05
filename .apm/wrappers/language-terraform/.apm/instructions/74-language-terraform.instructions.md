---
description: Terraform and HCL steering.
applyTo: "**/*.{tf,hcl}"
---

# Terraform

Keep environments and stacks explicit. Prefer vendor modules, then maintained
community modules, then custom thin wrappers. Document rationale when bypassing
official or community modules.
