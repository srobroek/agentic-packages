# GraphQL — Sniff Reference

One-line scope: GraphQL schema/SDL contracts — `*.graphql` / `*.gql` schema
files and code-first schemas. The dominant concern is **contract design and
backwards compatibility**; this feeds the sniff report's back-compat column.

## Detect

How sniff knows a GraphQL contract is present.
- Files/extensions: `*.graphql`, `*.gql`, `schema.graphql`; SDL embedded in
  `gql\`...\`` / `graphql\`...\`` template literals; a `type Query`/`type
  Mutation`/`type Subscription` root somewhere in the schema.
- Config that governs it: `.graphqlrc` / `graphql.config.{js,ts,yaml}`,
  `codegen.yml`, an ESLint config enabling `@graphql-eslint/eslint-plugin`, and
  a vendored prior schema (`schema.prev.graphql`, a git ref, or a registry
  baseline) for breaking-change diffs.

## Tools

Primary first. graphql-eslint lints SDL design; graphql-inspector diffs two
schema versions for breaking changes.

| Tool | Invocation | Covers | Installed via |
|------|-----------|--------|---------------|
| graphql-eslint | `npx eslint --format json <schema-glob>` (ESLint config enabling `@graphql-eslint/eslint-plugin` with a `*.graphql` override) | SDL smells: naming, nullability hints, deprecation, descriptions, unused types | `install-tools.sh --install api` |
| graphql-inspector | `graphql-inspector diff <old-schema> <new-schema>` | breaking-/dangerous-/non-breaking-change classification between two schema versions | `install-tools.sh --install api` |

Notes: graphql-eslint runs **through ESLint** — it needs an ESLint config with a
`*.graphql`/`*.gql` override applying the GraphQL processor and parser; if the
project has no such config, that is a coverage gap to report, not a silent skip.
graphql-inspector is the back-compat workhorse: `diff` labels each change as
`BREAKING`, `DANGEROUS`, or `NON_BREAKING`, which maps directly to the report's
back-compat column. N+1 resolver smells are **not** detectable from SDL alone —
they require resolver-code inspection (note the dataloader remedy below).

## Smell checklist

Beyond what tools flag. Group by category.

| Smell | What it looks like (GraphQL) | Idiomatic alternative |
|-------|------------------------------|-----------------------|
| Over-broad nullability | Everything nullable, or everything `!` non-null, with no intent | Make a field non-null only when it can never legitimately be absent; nullable signals "may fail / may be empty" |
| N+1 resolvers | Per-item resolver hits the DB/service inside a list (visible only in resolver code) | Batch with a DataLoader; flag for code review, not SDL fix |
| Missing pagination | List fields return `[T]` with no slicing args | Relay-style Connection (`edges`/`node`/`pageInfo`, cursor args) |
| Inconsistent nullability design | Mixed null intent across sibling fields with no rationale | A documented nullability convention per type |
| Mutation lacks payload | Mutations return the bare entity or a scalar | A dedicated `XPayload` type (entity + `userErrors`/metadata) for evolvability |
| Deeply nested input types | Input objects nested several levels, hard to evolve/validate | Flatten or split into named input types |
| DB schema exposed 1:1 | Types mirror table columns including internal/audit fields | Model the client-facing graph; hide internal columns |
| Missing `@deprecated` | Fields/enum values removed outright with no prior deprecation | Mark `@deprecated(reason: ...)` for a release before removal |
| Enum vs string misuse | A `String` field with a fixed, known value set (or an enum used for open-ended values) | Use `enum` for closed sets; `String`/custom scalar for open values |

## Idioms & style authorities

- GraphQL Specification — https://spec.graphql.org/
- GraphQL best practices — https://graphql.org/learn/best-practices/
- Relay Cursor Connections Specification —
  https://relay.dev/graphql/connections.htm
- Key conventions: nullability expresses intent (non-null = always present);
  use Connections for lists; `@deprecated` before removal; input + `XPayload`
  types for mutations; custom scalars/enums over stringly-typed fields.

## refactoring.guru mappings

Many of these are **schema-design moves**, not code rewrites — cite the smell
for vocabulary, but the fix is a schema edit.

| This-language smell | refactoring.guru smell | Idiomatic refactoring |
|---------------------|------------------------|-----------------------|
| Stringly-typed fields for fixed value sets | Primitive Obsession (`/smells/primitive-obsession`) | Replace with `enum` or a custom scalar |
| God type with dozens of unrelated fields | Large Class (`/smells/large-class`) | Split into focused types; compose via fields/relations |
| Repeated field sets across types/queries | Duplicate Code (`/smells/duplicate-code`) | Extract a shared `interface`/`union`, or reuse via fragments client-side |

## Pragmatism notes (for the adversarial pass)

- **Additive is safe; removal/retype/narrowing is breaking.** Adding a field, a
  type, an optional input arg, or an enum value (mostly) is backwards-compatible.
  Removing a field, removing an enum value, or changing a field's type is
  breaking — **always flag in the back-compat column**.
- **Nullability direction matters.** On an **output** field, nullable→non-null is
  safe (clients already handle null); non-null→nullable is **breaking**. On an
  **input** arg the reverse holds: non-null→nullable is safe; nullable→non-null
  (or adding a required input) is **breaking**. State the direction explicitly.
- **Deprecate before removing.** A field marked `@deprecated` for a release cycle
  before deletion is the idiomatic path; flag direct removal of a live field.
- Don't demand non-null everywhere. Nullable is often the correct, resilient
  choice (partial failures, optional data) — over-eager `!` is itself a smell.
- N+1 is a resolver-implementation concern; do not assert it from SDL alone.
  Flag it as "needs DataLoader, verify in resolver code," not as a schema defect.
- Adding an enum value can still break clients with exhaustive switches; note it
  as `DANGEROUS` rather than always-safe.
