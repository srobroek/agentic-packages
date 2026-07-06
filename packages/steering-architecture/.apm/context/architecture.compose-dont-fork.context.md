# Compose, Don't Fork

| Situation | Choice |
|-----------|--------|
| Need new behavior in existing subsystem | Wrap/compose; leave existing code path unchanged |
| New case (provider/strategy/backend) | New file; core discovers/dispatches |
| Core has `if kind == "x"` branch | Move case logic to its own module |
| Layer's safety depends on what it cannot do | Compose on top |

Make it verifiable: the strongest form is a near-empty diff to the shared
surface — the change adds files and an additive extension point, touching the
generic core by close to zero lines.

Fork (copy + diverge) when the two paths have genuinely diverged in intent and
a shared abstraction would only couple them — say so explicitly, and don't leave
a half-shared seam that must be re-audited on every change.
