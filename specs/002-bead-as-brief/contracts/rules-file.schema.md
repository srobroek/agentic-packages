# Contract: Rules File Schema

Path convention: `<package>/.apm/rules/<agent>.rules.json`, deployed alongside
the agent definition. One file per contract-holding agent (T1/T2/T3).

```yaml
# Required
agent: <agent-name>                 # must match definition name
tier: T1|T2|T3                      # enforcement mode selector

# T1/T3 completion checklist — evaluated against the claimed bead at stop.
# T3: evaluated only when a claim is held. T2: section absent (per-transaction
# authority only + zero-claims-at-exit).
completion:
  - check: <slug>                   # stable id, appears in deny reports
    require: <predicate>
    when: <kind-or-list>            # optional: execution kind or wisp type

# Authority — violations reported at stop (and deniable at write time where a
# runtime intercepts; defense-in-depth only)
authority:
  deny_states: [<state>, ...]       # states this agent may never set
  deny_metadata: [<key>, ...]       # keys this agent may never write or change;
                                    # a value already present at claim time is
                                    # not a violation
  deny_labels: [<glob>, ...]        # label writes this agent may never do

# Unconditional exit — always allowed regardless of checklist
escape:
  state: failed
  require: comment.verb in [FAILED, BLOCKED]

# Valid non-terminal exits (pause states)
pause:
  - <condition>                     # e.g. open-escalation-wisp-linked

# Bounce
bounce:
  max_attempts: 3                   # force-allow + BOUNCE + unassign + reset
```

## Predicate grammar (closed vocabulary)

| Predicate | Form |
|---|---|
| metadata key exists | `metadata.<key>` |
| label matches | `label ~ "<regex>"` |
| comment verb exists | `comment.verb in [<VERB>, ...]` |
| linked comment verb exists | `linked.comment.verb in [<VERB>, ...]` |
| state in set | `state in [<state>, ...]` |
| wisp state | `wisp(<selector>).open` / `.closed` |

Anything not expressible here is a script check, not a rule. Adding a
predicate type is a schema version bump.

## Consumers

1. **Evaluator** (`packages/orchestrate/scripts/rules-eval.py`): stdin = hook
   payload JSON; loads the rules file for `agent_type`; resolves the stamped
   activation resource; emits the hook decision JSON.
2. **Compile-time generator** (build step): renders the "Your bead contract"
   section into the agent definition from the same file. Generated block is
   marked and never hand-edited (constitution II).

## Conformance

Fixture suite: for every predicate type and every shipped rules file, a
fixture bead state → expected verdict (allow / block-with-checks /
bounce / escape / pause). Runs in package tests and hooks-portability-ci.
