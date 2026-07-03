# Compose, Don't Fork

When an existing subsystem needs new behavior, extend it through the seams it
already exposes -- do not copy, branch, or re-implement it into a variant.

## The rule

- Add a capability, don't clone the caller. Wrap or compose the existing unit
  to add behavior; leave its current code path unchanged. Prefer a new
  collaborator over a modified copy.
- Additive over modificative. A new case (provider, strategy, backend,
  format) should arrive as a new file the generic core discovers or
  dispatches to -- not as an edit that threads a special case through shared
  code.
- No caller-specific branching in generic code. Keep `if kind == "x"` out of
  the dispatch/registry/core layer. Case-specific knowledge lives only in
  that case's own module; the core stays case-agnostic.
- Preserve structural guarantees. If a layer's safety rests on what it
  cannot do (a capability it deliberately omits), compose on top rather than
  adding the capability to that layer -- the guarantee must survive the
  change.

## Make it verifiable

State the invariant as a check, not a hope. The strongest form is a
near-empty diff to the shared surface: the change adds files and an
additive extension point, and touches the generic core / critical path by
(close to) zero lines. A guard test or a reviewed diff asserting "no change
to the core beyond the additive hook" turns the principle into something a
reviewer and CI can enforce.

## When forking is the honest choice

Compose is the default, not a dogma. Fork (copy + diverge) when the two
paths have genuinely diverged in intent and a shared abstraction would only
couple them -- but say so explicitly, and don't leave a half-shared seam
that must be re-audited on every change. A clean fork beats a leaky
abstraction; a leaky abstraction beats neither.
