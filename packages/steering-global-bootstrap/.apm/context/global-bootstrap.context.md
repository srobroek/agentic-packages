# Global Agent Bootstrap

OWNERSHIP
MUST Use project-local APM packages for project skills, agents, hooks, MCP
  configuration, steering, and generated runtime files.
MUST Keep chezmoi limited to bootstrap/session assets and dotfile source
  management.
MUST Author reusable non-bootstrap assets in `~/dev/agentic-packages`, then
  install them through APM.

BOUNDARIES
NOT Create or edit global agents outside an APM package.
NOT Install project agents, skills, hooks, or MCP configuration through chezmoi.
MUST Use the chezmoi-editor skill for dotfile source changes.
MUST Use project-setup or brownfield-project to establish project-local APM
  configuration.
