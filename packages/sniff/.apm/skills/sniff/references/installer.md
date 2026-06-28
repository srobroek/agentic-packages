# Installer Flow

How sniff handles tool availability. The contract: **tools are always optional,
never auto-installed, never sudo.** Missing tools become reported coverage gaps,
not errors.

The script `scripts/install-tools.sh` does the mechanical work; this doc is the
agent's playbook for using it.

## First-run / step-2 sequence

1. **Probe.** `scripts/install-tools.sh --probe`. It prints, per bundle, which
   tools are installed and which are missing (with an install hint each).
2. **Translate to a menu.** Do not dump raw probe output and ask "install all?".
   Present a decision shaped like:

   ```
   Detected stack: Go, TypeScript, Dockerfile, GitHub Actions
   Installed:  golangci-lint ✓  eslint ✓
   Missing:    semgrep ✗  hadolint ✗  actionlint ✗  jscpd ✗

   Depth options:
     lean    install semgrep            → cross-language smell + hardcoded-value coverage
     full    + hadolint, actionlint     → Dockerfile + CI security gaps closed
     custom  pick bundles yourself

   Overlap note: jscpd is redundant with golangci-lint's dupl for Go; it only
   adds value for TS, where eslint+sonarjs already cover duplication — so skip it.
   ```
   Pull the overlap/gap facts from `references/tooling.md`.
3. **Install only what the user approves.**
   `install-tools.sh --install <bundle>...` or `--all`. Use `--dry-run` first if
   the user wants to see commands.
4. **Proceed regardless.** If the user declines an install, continue with what
   is present and list the gaps in the final report's coverage note.

## Bundles

| Bundle | Tools | When |
|--------|-------|------|
| `core` | semgrep, lizard, scc | Always useful; the cross-language floor |
| `dup` | jscpd | Only for languages without native dup (Python, SQL, configs) |
| `security` | trivy, checkov, gitleaks | When IaC/containers/secrets are in scope |
| `rust` | clippy (rustup), cargo-machete | Rust repos |
| `go` | golangci-lint | Go repos |
| `python` | ruff, vulture, pylint, mypy, pyright | Python repos (ruff is primary; pylint adds design smells, mypy/pyright type smells — pick whichever the repo configures) |
| `js-ts` | eslint, knip, biome | JS/TS repos (project-local — see note) |
| `shell` | shellcheck, shfmt | Shell scripts |
| `sql` | sqlfluff | SQL |
| `css` | stylelint | CSS/SCSS (project-local) |
| `data` | yamllint, taplo, check-jsonschema | YAML/TOML/JSON |
| `api` | spectral, buf | OpenAPI / Protobuf / GraphQL |
| `infra` | hadolint, tflint, actionlint, kube-linter | Dockerfile / Terraform / CI / k8s |
| `docs` | markdownlint-cli2, lychee | Markdown |

## Package managers

The script tries, in order of fit: `brew`, `pipx` (or `uv tool` if pipx is
absent), `npm -g`, `cargo`, `rustup`. If none is present for a tool, it prints
the manual install command and moves on. It never calls sudo.

## Project-local tools

`eslint`, `knip`, `biome`, `stylelint` are JS ecosystem tools that belong in the
**repo's own** `devDependencies`, pinned with the project. The script does **not**
install them globally; it reports them and prints the `npm i -D ...` line to run
inside the repo. Run them via `npx` so the project's config and plugin versions
apply.

## Rust note

`clippy` ships with the Rust toolchain (`rustup component add clippy`) and
already covers most Rust dimensions. Do not push the user to install extra Rust
tooling beyond `cargo-machete` unless they ask for a deep pass (then
`cargo-udeps`, nightly).
