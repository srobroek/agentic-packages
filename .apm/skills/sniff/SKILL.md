---
name: sniff
description: Use for a stability, hardening, and cleanup audit across a codebase.
---

# Sniff

Use this skill for codebase stabilization, hardening, and cleanup audits.

## Steps

1. **Detect project context**: Read project config for stack, conventions, architecture. Detect language(s), test framework, linter, project type.
2. **Explore codebase** (parallel agents where possible):
   - Error handling: panic/throw/unwrap patterns, unhandled errors, silent swallowing
   - Unsafe/FFI/native: raw pointers, missing safe wrappers
   - Code structure: god objects (>500 lines), long functions (>50 lines), duplication, dead code
   - Concurrency: shared state, locks, missing timeouts, blocking operations
   - Input boundaries: HTTP handlers, CLI parsers, file readers — validation and size limits
3. **Generate structured report** with findings per dimension, severity, file references, and recommendations.
## Language Adaptations

| Language | Panic patterns | Concurrency | Idioms |
|----------|---------------|-------------|--------|
| Rust | `unwrap()`, `expect()`, `panic!()` | Arc/Mutex, channels, catch_unwind | Builder, typestate, newtype, `?` |
| Python | bare `except:`, missing try/except | asyncio, threading, queue | Context managers, dataclasses |
| TypeScript | uncaught Promise, missing `.catch()` | Worker threads, async/await | Discriminated unions, zod |
| Go | `panic()`, unchecked err, `log.Fatal` | goroutines, channels, sync.Mutex | Error wrapping, context.Context |

## Rules

- ALWAYS explore the codebase before generating findings. Do not guess at issues.
- Use parallel agents for exploration when the codebase is large.
- Skip irrelevant dimensions (no threads = skip concurrency, no FFI = skip unsafe audit).
- "quick" mode: reduce to error handling, defensive coding, logging, and code smells only.
- Output: summary counts, per-dimension findings (file:line, severity, fix), priority actions by crash risk.
