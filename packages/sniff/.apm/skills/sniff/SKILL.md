---
name: sniff
description: Audit a codebase for stability, hardening, and cleanup opportunities across error handling, unsafe code, structure, concurrency, and input boundaries. Use when the user asks to audit codebase stability, harden the code, find latent issues, plan a cleanup pass, or sniff the codebase.
---

# Sniff

Audit the codebase across stability dimensions and report prioritized findings.

## Steps

1. **Detect project context**: Read project config for stack, conventions, architecture. Detect language(s), test framework, linter, project type.
2. **Explore codebase** (parallel subagents where the runtime supports them):
   - Error handling: panic/throw/unwrap patterns, unhandled errors, silent swallowing
   - Unsafe/FFI/native: raw pointers, missing safe wrappers
   - Code structure: god objects (>500 lines), long functions (>50 lines), duplication, dead code
   - Concurrency: shared state, locks, missing timeouts, blocking operations
   - Input boundaries: HTTP handlers, CLI parsers, file readers -- validation and size limits
3. **Generate structured report** with findings per dimension, severity, file references, and recommendations.

## Language Adaptations

| Language | Panic patterns | Concurrency | Idioms |
|----------|---------------|-------------|--------|
| Rust | `unwrap()`, `expect()`, `panic!()` | Arc/Mutex, channels, catch_unwind | Builder, typestate, newtype, `?` |
| Python | bare `except:`, missing try/except | asyncio, threading, queue | Context managers, dataclasses |
| TypeScript | uncaught Promise, missing `.catch()` | Worker threads, async/await | Discriminated unions, zod |
| Go | `panic()`, unchecked err, `log.Fatal` | goroutines, channels, sync.Mutex | Error wrapping, context.Context |

## Rules

- Always explore the codebase before generating findings. Do not guess at issues.
- When the codebase is large and the runtime supports subagents, explore with parallel agents; otherwise sweep the dimensions sequentially.
- Skip irrelevant dimensions (no threads = skip concurrency, no FFI = skip unsafe audit).
- "quick" mode: reduce to error handling, defensive coding, logging, and code smells only.
- Output: summary counts, per-dimension findings (file:line, severity, fix), priority actions by crash risk.
