# Changelog

## 0.1.0 (2026-07-17)

### Features

* PreToolUse:Agent deny gate that blocks model-less spawns of inherit-type subagents (`general-purpose`, `Explore`, `Plan`, `claude`, `fork`, or `subagent_type` omitted) and returns a routing table (haiku/sonnet/opus) so the caller's retry succeeds. Deny reason also notes that reasoning effort is not enforceable per-call and points to pinning `effort:` in reusable agent definitions instead. Inherit-type list overridable via `SUBAGENT_MODEL_GUARD_INHERIT_TYPES`. Fails open on malformed input. Claude-only.
