# <Language / Format> — Sniff Reference

> Authoring template for a sniff language doc. Copy this, fill every section,
> keep it self-contained (a `bloodhound` agent reads ONLY this doc for the
> language). Aim for tight, concrete content — checklists over prose. Delete
> this blockquote in real docs.

One-line scope: what this doc covers (e.g. "Go source: `.go` files, `go.mod`").

## Detect

How sniff knows this language/format is present: key files, extensions, config.
- Files/extensions: `...`
- Config that governs it: `...`

## Tools

The analyzers to run, primary first. Exact invocation + machine-readable flag.
Pull canonical detail from `../tooling.md`; this section is the runnable subset.

| Tool | Invocation | Covers | Installed via |
|------|-----------|--------|---------------|
| <primary> | `...--json...` | <dimensions> | `install-tools.sh --install <bundle>` |
| <secondary> | `...` | <dimensions> | ... |

Notes: which tool is the meta-linter, what overlaps, what to skip if another is
present. Note when the standard toolchain already covers a dimension.

## Smell checklist

The smells to look for, beyond what tools flag. Each: what it looks like + the
idiomatic alternative. Group by category. Be language-specific — not generic OO.

| Smell | What it looks like (this language) | Idiomatic alternative |
|-------|-----------------------------------|-----------------------|
| ... | ... | ... |

## Idioms & style authorities

The leading style guide(s)/handbook(s) for this language, with URLs. State the
few conventions most worth enforcing.

- <Guide name> — <URL>
- Key conventions: ...

## refactoring.guru mappings

The smells common in this language → the catalog entry to cite (see
`../refactoring-catalog.md`). Note where the language-idiomatic fix differs from
the generic catalog.

| This-language smell | refactoring.guru smell | Idiomatic refactoring |
|---------------------|------------------------|-----------------------|
| ... | ... | ... |

## Pragmatism notes (for the adversarial pass)

Where "fixes" commonly over-reach in this language — the false positives and
non-idiomatic-but-fine patterns the `refactor-challenger` should protect.

- ...
