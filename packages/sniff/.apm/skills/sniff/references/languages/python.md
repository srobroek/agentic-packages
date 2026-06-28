# Python — Sniff Reference

One-line scope: Python source — `.py`, `.pyi` files; packages with
`pyproject.toml` / `setup.cfg` / `setup.py`.

## Detect

How sniff knows this language/format is present: key files, extensions, config.
- Files/extensions: `.py`, `.pyi`; `pyproject.toml`, `setup.py`, `setup.cfg`,
  `requirements*.txt`, `Pipfile`, `poetry.lock`, `uv.lock`.
- Config that governs it: `[tool.ruff]` / `ruff.toml` (line length, rule
  selection, `target-version`); `[tool.pylint]` / `.pylintrc`; `[tool.mypy]` /
  `mypy.ini`; `pyrightconfig.json`. Respect the project's selected/ignored rules.

## Tools

The analyzers to run, primary first. Exact invocation + machine-readable flag.

| Tool | Invocation | Covers | Installed via |
|------|-----------|--------|---------------|
| ruff | `ruff check --extend-select C901,B,SIM,PL,RUF,UP --output-format json .` — **use `--extend-select`, NOT `--select`**: `--select` discards the repo's pinned `[tool.ruff] select` *and* its line-length, flooding a well-configured repo with noise it already triaged (Hard Rule: respect project config). `--extend-select` keeps project config and adds the design/complexity rules ruff's E/F defaults omit. | flake8 + isort + pyupgrade + mccabe (C901) + bugbear + pylint subset | `install-tools.sh --install python` (`pip/uv install ruff`) |
| pylint | `pylint --output-format json <pkg>` | unique refactoring smells R09xx (too-many-branches/args/locals, duplicate-code) | `pip install pylint` |
| vulture | `vulture <path> --min-confidence 80` | dead code (unused functions, vars, imports, unreachable) | `pip install vulture` |
| mypy | `mypy --no-error-summary <pkg>` | type smells (untyped defs, `Any` leakage, missing returns) | `pip install mypy` |
| pyright | `pyright --outputjson` | type smells (faster, stricter inference) | `npm i -g pyright` / `pip install pyright` |

Notes: **ruff is the meta-linter** — it reimplements the flake8 family plus
`mccabe` (C901 complexity) and a `pylint` subset in one fast AST pass; run it
first. **`--extend-select`, never `--select`:** ruff's *defaults* enable only
`E`/`F`, so a bare `ruff check` reports "clean" while missing complexity (`C901`,
`PLR09xx`), bugbear (`B`), and modernization (`UP`) — the smells sniff most cares
about. `--extend-select` ADDS those on top of whatever the repo configures, so a
repo that pins `[tool.ruff] select` and a custom `line-length` keeps both; bare
`--select` would replace them and dump hundreds of false findings (e.g. E501 on a
repo whose configured line-length you just discarded) — a direct violation of the
Hard Rule. Add `pylint` only on deep runs for the design smells ruff lacks
(R09xx: `too-many-branches`, `too-many-arguments`, `too-many-locals`,
`duplicate-code`).
`vulture` covers dead code ruff does not fully detect. Pick **one** type
checker (mypy or pyright) per project — match whatever the repo already configures.
`jscpd` is only worth installing if cross-file duplication matters and neither
ruff nor pylint's `duplicate-code` is catching it.

## Smell checklist

The smells to look for, beyond what tools flag. Each: what it looks like + the
idiomatic alternative. Be language-specific.

| Smell | What it looks like (this language) | Idiomatic alternative |
|-------|-----------------------------------|-----------------------|
| Bare / broad except | `except:` or `except Exception:` swallowing everything | catch the specific exception type; re-raise or log with context (ruff `E722`, `BLE001`) |
| Mutable default arg | `def f(x, items=[])` / `={}` shared across calls | `def f(x, items=None): items = items or []` (ruff `B006`) |
| Missing context manager | manual `open()`/`close()`, `acquire()`/`release()` | `with open(...) as f:` / `with lock:` (resource leak risk) |
| God function | 100+ line function, deeply nested, many responsibilities | Extract Method; split by responsibility (pylint `R0915`/C901) |
| `*args/**kwargs` hiding a signature | public API typed as `(*args, **kwargs)` with no real contract | explicit named (esp. keyword-only) params; `TypedDict`/dataclass for options |
| Primitive obsession (dict-as-object) | passing/returning `dict[str, Any]` as a record | `@dataclass`, `NamedTuple`, `attrs`, or `pydantic` model |
| Import-time side effects | network/DB calls, file writes, mutation at module top level | guard under `if __name__ == "__main__":` or a function; lazy init |
| `type()` equality check | `if type(x) == int:` / `type(x) is Foo` | `isinstance(x, int)` or duck typing (EAFP) |
| Comprehension overuse | nested/multi-clause comprehension that's unreadable | a plain `for` loop, or split into named intermediate steps |
| Global mutable state | module-level `CACHE = {}` mutated across functions | pass state explicitly; encapsulate in a class/closure; `functools.lru_cache` |
| String-typed enums | `mode = "fast"` with scattered `== "fast"` checks | `enum.Enum` / `enum.StrEnum` |

## Idioms & style authorities

- PEP 8 — Style Guide for Python Code — https://peps.python.org/pep-0008/
- PEP 20 — The Zen of Python — https://peps.python.org/pep-0020/
- Google Python Style Guide — https://google.github.io/styleguide/pyguide.html
- Ruff rules reference — https://docs.astral.sh/ruff/rules/
- Pylint messages (refactoring R-codes) — https://pylint.readthedocs.io/en/stable/user_guide/messages/messages_overview.html
- Key conventions: prefer dataclasses/`attrs`/`pydantic` over dict-as-object;
  use context managers for resources; EAFP (try/except) over LBYL where
  idiomatic; type hints on public APIs; specific exceptions; PEP 8 naming
  (`snake_case` funcs/vars, `PascalCase` classes, `UPPER_SNAKE` constants).

## refactoring.guru mappings

| This-language smell | refactoring.guru smell | Idiomatic refactoring |
|---------------------|------------------------|-----------------------|
| dict-as-object / loose primitives | Primitive Obsession (`/smells/primitive-obsession`) | Replace with `@dataclass` / `NamedTuple` (Replace Data Value with Object) — not a hand-written getter/setter class |
| Many positional params (pylint R0913) | Long Parameter List (`/smells/long-parameter-list`) | A `@dataclass` *or* keyword-only args (`*,`); do **not** always introduce a Parameter Object class |
| God function (C901 / R0915) | Long Method (`/smells/long-method`) | Extract Method (`/refactoring/techniques/composing-methods`) — module-level functions, not a Method Object |
| Repeated blocks (pylint `duplicate-code`) | Duplicate Code (`/smells/duplicate-code`) | Extract Function; Substitute Algorithm |
| Unused defs (vulture) | Dead Code (`/smells/dead-code`) | Delete the code |
| `if/elif` chain on a string mode | Switch Statements (`/smells/switch-statements`) | A dict dispatch or `match`/`case` (3.10+); polymorphism only if behaviour is rich |

Note: Python favors functions, dataclasses, and `match`/dict-dispatch over the
OO catalog's class-heavy fixes. A Parameter Object is often just a dataclass or
a `*,` keyword-only signature, not a new behavioural class.

## Pragmatism notes (for the adversarial pass)

- Comprehensions are idiomatic Python — do **not** unroll a clear single-clause
  comprehension into a loop. Only flag deeply nested / multi-condition ones that
  genuinely hurt readability.
- Duck typing is idiomatic: not every `isinstance` is a smell, and EAFP
  (`try/except`) is often *preferred* over defensive `isinstance` checks. Flag
  `type(x) ==`, not reasonable `isinstance` guards.
- Small scripts and glue code don't need a dataclass for every dict — the
  dict-as-object smell applies to records that travel through real logic, not a
  throwaway config blob read once.
- A module-level constant or a `lru_cache` is fine; "global state" is a smell
  only when mutable module state is written from multiple call sites.
- `except Exception:` at a top-level boundary (a request handler, a worker loop)
  that logs and continues can be deliberate resilience — flag broad excepts that
  silently swallow in core logic, not the outermost guard.
- **`--extend-select` adds rules the team chose not to enable — handle the noise.**
  In a scoped/PR run, also run ruff once with project config only
  (`ruff check <files>`). Findings that appear ONLY under `--extend-select` are
  rules the project deliberately omitted: present them as **advisory/low, never
  as regressions** the change introduced. And **DROP `RUF100` "unused noqa"** hits
  whose referenced rule isn't in the project's own select — they're an artifact
  of widening the rule set, not a real unused suppression. (When the repo pins no
  `[tool.ruff]` config at all, `--extend-select` simply augments the E/F defaults
  — still use it, never `--select`.)
