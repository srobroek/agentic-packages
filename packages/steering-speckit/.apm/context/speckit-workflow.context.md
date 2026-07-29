# SpecKit Workflow

EXECUTION
MUST Invoke SpecKit commands through their runtime-native skill interface.
MUST Use the project-local `speckit-feature` molecule as the phase DAG when
  `speckit-beads` is installed.
MUST Keep corrections with the same live agent through the runtime-native
  messaging operation until its assigned work passes review.
NOT Invoke deprecated `/speckit.implement`; use assign, validate, then execute.
NOT Proceed with open questions, unresolved gaps, or unapproved intent changes.

PHASE ORDER
| phase | required sequence |
|---|---|
| Specification | specify -> clarify -> checklist -> clarified-spec approval |
| Planning | plan -> plan approval -> critique + security plan review -> tasks -> analyze |
| Readiness | pre-implementation checkpoint -> implementation-readiness approval |
| Implementation | assign -> validate -> execute -> implementation-child completion |
| Quality | verify-tasks -> verify -> review -> QA -> code + security review -> cleanup |
| Closeout | drift + conflict checks -> retro -> docs -> closeout approval -> final checkpoint |

TASK STATE
MUST In Beads-enabled repositories, create tasks under the molecule's implement
  step and query task state by spec ID; never author or update tasks.md.
MUST Keep the implement parent open until every implementation child is closed.
DEFAULT Without `speckit-beads`, preserve upstream SpecKit artifact behavior.

GATES
MUST Keep clarify, checklist, and analyze interactions on the main thread.
MUST Resolve clarified-spec, plan, implementation-readiness, and closeout gates
  only after the named evidence is approved.
MUST Route runtime findings through bonded `mol-speckit-fix-findings` molecules.
MUST Route requirements or approach changes through bonded `mol-speckit-iterate`
  molecules and refresh the roadmap after applying the change.

DECISIONS
MUST Register a hard-to-reverse or boundary-crossing choice when it lands, not at
  closeout. The `adr` package owns the format, the path, and the gate; this section
  owns only which SpecKit phases produce one.
| phase | what earns a record |
|---|---|
| plan | a technology, contract, or boundary choice the plan depends on |
| critique + security plan review | a risk knowingly accepted rather than mitigated |
| analyze | a constraint discovered late that changes the approach |
| implement | a deviation from the approved plan, recorded before the deviation spreads |
| iterate | the reason an approved approach changed |
MUST Set `--spec-id <spec>` on the decision bead, which is the native field that
  binds a record to the spec that produced it. Without it the record survives and
  its provenance does not.
MUST Cite the record on the phase's bead before that phase closes. A phase that
  produced a choice and closed without a citation loses the alternatives.
NOT Defer recording to retro or closeout. By then the rejected options are gone, and
  the rejected option is the part worth keeping.
| observed condition | route |
|---|---|
| Approved intent is correct and implementation is incomplete | converge |
| Approved intent or approach changes | mol-speckit-iterate molecule |
| Implemented code has a defect | bugfix skill |
| Review, QA, or security finds actionable defects | mol-speckit-fix-findings molecule |
| Change fits one paragraph and needs no full lifecycle | tinyspec |

CLOSEOUT
MUST Close the feature root after its final step and follow the active Beads
  authority policy for the single terminal sync.
