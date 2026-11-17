# SPDX-License-Identifier: Apache-2.0
"""Incremental hypothetical source withdrawal over an already validated support DAG.

The caller MUST supply v0.3's full baseline states derived from the same
immutable ledger snapshot and trusted clock. This module performs no authority
resolution, makes no persistent changes, and does not certify source truth.

Changes only propagate when an actual parent SUPPORT STATE changes. All
calculations retain the original WITHDRAWN > RIGHTS_UNAVAILABLE > EXPIRED
precedence and OR-of-AND claim semantics. This is a research implementation,
not an unmeasured speedup claim or a distributed invalidation protocol.
"""
from __future__ import annotations

from heapq import heappop, heappush

STATES = frozenset({
    "SUPPORTED", "UNSUPPORTED", "WITHDRAWN", "EXPIRED", "RIGHTS_UNAVAILABLE"
})
MAX_NODES = 128


def delta_states(
    nodes: dict,
    previously_withdrawn: set,
    now: int,
    requested_sources: set,
    baseline: dict,
) -> dict:
    """Return exact counterfactual states without recomputing unaffected descendants.

    Nodes must be a validated, insertion-topological, single-tenant _reduce
    projection. The entire baseline and the requested action share one pinned
    transaction. This function must not accept client-provided statuses.
    """
    if type(nodes) is not dict or len(nodes) > MAX_NODES:
        raise ValueError("GRAPH_BUDGET")
    if type(previously_withdrawn) is not set or type(requested_sources) is not set:
        raise ValueError("SET_REQUIRED")
    if type(now) is not int or not 0 <= now <= 2**53:
        raise ValueError("CLOCK_DOMAIN")
    if type(baseline) is not dict or set(baseline) != set(nodes):
        raise ValueError("BASELINE_COVERAGE")
    if any(state not in STATES for state in baseline.values()):
        raise ValueError("BASELINE_STATE")
    if any(type(k) is not str or k not in nodes or
           nodes[k]["op"] != "source" for k in requested_sources):
        raise ValueError("SOURCE_ONLY")
    if not requested_sources:
        return baseline.copy()

    order = {k: i for i, k in enumerate(nodes)}
    dependents: dict[str, set[str]] = {k: set() for k in nodes}
    for key, node in nodes.items():
        if node["op"] != "claim":
            continue
        for term in node["supports"]:
            for parent in term:
                if parent not in order or order[parent] >= order[key]:
                    raise ValueError("NOT_A_VALID_FORWARD_DAG")
                dependents[parent].add(key)

    after = baseline.copy()
    pending: list[tuple[int, str]] = []
    queued: set[str] = set()

    def schedule(parent: str) -> None:
        for child in dependents[parent]:
            if child not in queued:
                queued.add(child)
                heappush(pending, (order[child], child))

    for key in sorted(requested_sources, key=order.__getitem__):
        if after[key] != "WITHDRAWN":
            after[key] = "WITHDRAWN"
            schedule(key)

    while pending:
        _, key = heappop(pending)
        queued.remove(key)
        node = nodes[key]
        if key in previously_withdrawn:
            state = "WITHDRAWN"
        elif node["read_allowed"] is not True:
            state = "RIGHTS_UNAVAILABLE"
        elif now >= node["expires_at"]:
            state = "EXPIRED"
        else:
            state = (
                "SUPPORTED"
                if any(
                    all(after[parent] == "SUPPORTED" for parent in term)
                    for term in node["supports"]
                ) else "UNSUPPORTED"
            )
        if state != after[key]:
            after[key] = state
            schedule(key)
    return after
