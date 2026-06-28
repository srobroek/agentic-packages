# Kubernetes manifests — Sniff Reference

Kubernetes resource manifests: YAML used *functionally* to declare workloads. This
doc covers **k8s semantics** — resource limits, probes, security context, image
pinning, availability. The pure-YAML **format** layer (indentation, anchors,
Norway/truthy, duplicate keys) is covered separately in `yaml.md`; reference that
split and do not re-flag syntax here. Dominant concerns: security misconfig,
reliability, maintainability.

## Detect

How sniff knows manifests are k8s (vs plain YAML): key markers.
- Files/extensions: `*.yaml`/`*.yml` containing `apiVersion:` + `kind:` + `metadata:`
- Kustomize: `kustomization.yaml`, `base/` + `overlays/` layout
- Helm: `Chart.yaml`, `templates/*.yaml` (templated — lint the *rendered* output via `helm template | kube-linter lint -`)
- Config that governs it: `.kube-linter.yaml`

## Tools

Primary first. Exact invocation + machine-readable flag. Canonical detail in
`../tooling.md`; this is the runnable subset.

| Tool | Invocation | Covers | Tier | Installed via |
|------|-----------|--------|------|---------------|
| kube-linter | `kube-linter lint --format json <path>` | missing limits/requests, probes, `runAsNonRoot`, `:latest`, privileged, hostPath | default-on | `install-tools.sh --install infra` |
| kubeconform | `kubeconform -output json <files>` | schema validity against the k8s OpenAPI / CRD schemas | default-on | `install-tools.sh --install infra` |
| trivy (config) | `trivy config --format json <dir>` | k8s misconfig: privileged, hostNetwork, capabilities, secrets as env | opt-in (security; overlaps kube-linter's security checks) | `install-tools.sh --install security` |
| checkov | `checkov -d . --framework kubernetes -o json` | deep policy/benchmark checks | opt-in (security) | `install-tools.sh --install security` |

Notes: `kube-linter` is the primary semantic linter (reliability + security
posture). `kubeconform` only validates *schema* (does the manifest parse against
the API spec) — run it as a cheap gate, it does not catch missing-limits/probe
smells. `trivy config` and `checkov` overlap with kube-linter on security context;
run kube-linter for posture and trivy as the security gate, reserve checkov for
benchmark-grade runs. For Helm, render first (`helm template . | kube-linter lint -`).

## Smell checklist

Beyond what tools flag. Each: what it looks like + the idiomatic alternative.

| Smell | What it looks like (k8s) | Idiomatic alternative |
|-------|--------------------------|-----------------------|
| No resource requests/limits | Container with no `resources.requests`/`limits` | Set CPU/memory `requests` + `limits` (scheduling + OOM safety) |
| `:latest` image tag | `image: myapp:latest` or untagged | Pin an immutable tag/digest: `image: myapp:1.4.2@sha256:…` |
| Missing probes | No `livenessProbe`/`readinessProbe` | Define both (readiness for traffic gating, liveness for restart) |
| Runs as root / no securityContext | No `runAsNonRoot`, writable root FS | `securityContext: { runAsNonRoot: true, readOnlyRootFilesystem: true, allowPrivilegeEscalation: false }` |
| Privileged container | `securityContext.privileged: true` | Drop privilege; add only the specific `capabilities` needed |
| Host namespace / hostPath | `hostNetwork: true`, `hostPID`, `volumes: hostPath` | Use Services + PVCs; avoid host access unless a node agent |
| No PodDisruptionBudget | Multi-replica service with no PDB | Add a `PodDisruptionBudget` for graceful drains/upgrades |
| Missing namespace | Resources land in `default` | Set an explicit `metadata.namespace` (or namespaced kustomize) |
| Secrets as plaintext env | `env: { value: "supersecret" }` | `secretKeyRef` from a `Secret` (ideally external/sealed) |
| No resource quotas | Namespace with no `ResourceQuota`/`LimitRange` | Add `ResourceQuota` + `LimitRange` per namespace |
| Single replica (stateless) | `replicas: 1` for a request-serving Deployment | `replicas: >= 2` + anti-affinity for availability |
| Label/selector conventions | Ad-hoc labels; selectors not matching | Use recommended `app.kubernetes.io/*` labels consistently |

## Idioms & style authorities

- Kubernetes configuration best practices — https://kubernetes.io/docs/concepts/configuration/overview/
- Production-readiness / recommended labels — https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/
- kube-linter checks reference — https://docs.kubelinter.io/#/generated/checks
- Key conventions: always set resource `requests`/`limits`; define liveness +
  readiness probes; enforce `runAsNonRoot` + read-only root FS + drop capabilities;
  pin images to immutable tags/digests, never `:latest`; run >=2 replicas for
  serving workloads; apply the `app.kubernetes.io/*` label conventions.

## refactoring.guru mappings

| k8s smell | refactoring.guru smell | Idiomatic refactoring |
|-----------|------------------------|-----------------------|
| Copy-pasted manifests across environments | Duplicate Code (`/smells/duplicate-code`) | Kustomize base + overlays, or Helm templating |
| One mega-manifest with every resource | Large Class (`/smells/large-class`) | Split per-resource files; compose via kustomize |

The OO catalog maps **weakly** — most k8s smells are ops/security-specific (limits,
probes, securityContext) with no refactoring.guru analogue. Cite the Kubernetes
best-practices and kube-linter URLs as the authority over forcing an OO mapping.

## Pragmatism notes (for the adversarial pass)

- Dev/test manifests legitimately skip limits and probes; weight these smells by
  whether the manifest targets production (namespace name, replica count, registry).
- `replicas: 1` is fine for batch `Job`/`CronJob` and for stateful singletons —
  the smell is single-replica *stateless serving* Deployments only.
- Not everything needs a PDB: single-replica or batch workloads gain nothing; flag
  the missing PDB only on multi-replica serving workloads.
- `readOnlyRootFilesystem: true` legitimately breaks apps that write to disk — pair
  the recommendation with a writable `emptyDir` mount rather than flagging blindly.
- Security smells (privileged, `hostNetwork`/`hostPath`, plaintext secret env,
  `runAsNonRoot` absent) are rarely false positives — weight them high in severity.
