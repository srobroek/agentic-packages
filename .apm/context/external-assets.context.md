# External Asset Audit

Some local skills and agents originated in external repositories or public
skill collections. Prefer APM dependencies over vendored copies when the
upstream package is maintained, compatible, and does not need local model or
tooling changes.

Known candidates for source verification:

- `mattpocock/skills`: APM-compatible marketplace plugin. Direct whole-package
  `dependencies.apm` entry works, and individual skill virtual-package paths
  also work. Pin to a commit before using in real projects. Whole-package
  install currently deploys: `caveman`, `diagnose`, `grill-me`,
  `grill-with-docs`, `improve-codebase-architecture`,
  `setup-matt-pocock-skills`, `tdd`, `to-issues`, `to-prd`, `triage`,
  `write-a-skill`, `zoom-out`.
- `setup-matt-pocock-skills`: local adaptation exists, but prefer consuming the
  upstream APM dependency when the project wants the Matt Pocock workflow set.
- `remotion`: upstream reference in skill docs points to `remotion-dev/remotion`.
- `interface-design`: `SOURCE.md` points to `Dammyjay93/interface-design`.
- `impeccable`: locally adapted, based on Anthropic frontend-design.
- Stitch-related skills: local custom workflows around the Stitch MCP.
- `shadcn-ui`: local guide around upstream shadcn/ui docs and component source.

Do not replace a local adaptation with an upstream dependency until behavior,
license, and model/tool metadata have been reviewed.
