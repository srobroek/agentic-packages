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
MUST Record non-trivial hard-to-reverse decisions as MADR records under
  `docs/adr/NNNN-title.md` when the decision lands.
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
