# Changelog

## 0.1.0

### Features

* Initial `dependency-quality` bundle aggregating the independently-installable
  dependency-hygiene components: `hooks-package-file-guard` (warn on direct
  manifest edits), `hooks-package-investigate` (investigate a dependency before
  adding), `hooks-pkg-version-warn` (install latest compatible version),
  `dep-audit` (CVE scanning), and `mcp-package-version` (version-discovery MCP
  server). Install the bundle for the full surface, or any component on its own.
