# Changelog

## 0.1.0

### Features

* Initial release: on-demand dependency CVE scanner skill. Detects the
  ecosystem(s) present from lockfiles/manifests and dispatches to the native
  scanner for each (npm/pnpm audit, pip-audit, cargo audit, govulncheck,
  osv-scanner), guarding every scanner with `command -v`. Reports which
  scanners ran versus were unavailable (with install hints) and never
  auto-fixes. `scripts/audit.sh` exits non-zero when any HIGH/CRITICAL
  vulnerability is found so it can gate CI.
