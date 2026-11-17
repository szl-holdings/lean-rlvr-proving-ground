# Selective revalidation research — source-bound transition planner

This change is part of the existing Boundary Assurance read-only research workbench.
No new controller, scheduler, model, weight, paid training, private graph hydration,
live identity, or execution authority is created.

## Precise contract

The admitted full replay in `assurance_surface.states_for` is the independent
software reference. Under the same ledger snapshot, trusted clock, and original
withdrawal set, `impact_delta.delta_states` must produce **exactly the same
state for every node** after a hypothetical additional source withdrawal. The
ledger remains read-only. Requested objects must be sources, not conclusions.

An ordered dependent graph propagates changes only when an upstream **support
state** changes. The event-order DAG remains the source of topological authority.
Alternative OR paths survive appropriately; AND dependencies fail when a required
source loses support. Rights, expiry, and existing withdrawal have the same
precedence as the reference function. A previously expired source can move to
WITHDRAWN without causing an additional loss of supported claims.

The HTTP response schema remains `szl.assurance-surface/v0.3`; the existing
same-origin frontend continues consuming its server-calculated `scenario_state`
field. The additional UI text counts only visible unredacted state transitions
and separately counts objects moving from SUPPORTED to a non-supported state.
This is **hypothetical**, and counts do not constitute authorization to repair,
invalidate, train, promote, or execute.

## Verification and limits

The new differential tests use a fixed seed and 1,200 valid generated event DAGs,
five clock positions per graph: **6,000 scenarios** checked against complete
reference replay, plus targeted OR/AND, descendants, rights, expiry, malformed
inputs, and an end-to-end controller-supplied read-only scenario. The existing
offline Python, JavaScript and kernel checks must also pass on the exact PR head,
including after merge.

The generator and tests are author-supplied; they are repeatability evidence,
not independent formal verification. This is not a Lean/Python refinement proof,
a complete distributed authorization protocol, or independent witnessing.

No speedup is claimed. Reverse-index construction is itself O(E); in the current
128-node public graph cap, incremental replay can be slower than a second complete
pass. Any performance claim requires pinned same-host measurement, matching
outputs, fixed workloads, uncertainty and explicit baseline. The reason to
admit this algorithm first is **testable semantic precision** and the option to
reuse the inspected dependency frontier when a future owner controls a larger
incremental graph. Browser-rendered acceptance, live owner integration and
model-behavior evaluation remain separate gates.

## Preservation

Do not rewrite historical receipts or merge lexical association graphs into
logical support without explicit admission. No source identities are sent to the
UI unless the existing owner policy authorizes them. The exact original Lutar
formula registry, proof referee, corpus admission, and active jobs remain unchanged.
