"""Finite trusted-candidate search with a frozen oracle; no arbitrary code loader.

All candidates below are reviewed, static functions. This does not sandbox an
untrusted candidate, establish universal equivalence, or authorize deployment.
"""
from hashlib import sha256
from pathlib import Path
from statistics import median
from time import perf_counter_ns
import boundary_lab as base


def dfs_acyclic(edges):
    rows = base.edges_checked(edges)
    graph = {}
    for s, d in rows:
        graph.setdefault(s, []).append(d)
        graph.setdefault(d, [])
    colors = {}
    for start in graph:
        if colors.get(start, 0):
            continue
        colors[start] = 1
        stack = [(start, iter(graph[start]))]
        while stack:
            node, neighbors = stack[-1]
            nxt = next(neighbors, None)
            if nxt is None:
                colors[node] = 2
                stack.pop()
            elif colors.get(nxt, 0) == 1:
                return False
            elif colors.get(nxt, 0) == 0:
                colors[nxt] = 1
                stack.append((nxt, iter(graph[nxt])))
    return True


def _unsound_backward_only(edges):
    return base.backward(edges)


def _unsound_always_true(edges):
    return True


def run_search():
    source = Path(__file__)
    baseline_file = Path(base.__file__)
    before = {"candidate_module": sha256(source.read_bytes()).hexdigest(),
              "oracle_module": sha256(baseline_file.read_bytes()).hexdigest()}
    edge_types = [(s, d) for s in range(4) for d in range(4) if s != d]
    cases = [[e for bit, e in enumerate(edge_types) if (mask >> bit) & 1]
             for mask in range(1 << len(edge_types))]
    cases += [[(0, 0)], [(1, 1)], [(1, 0), (1, 0)], [(0, 1)], [(9, 8), (8, 7)]]
    expected = [base.acyclic(case) for case in cases]
    contract = {"schema": "szl.finite-verifier-contract/v0.2", "inputs_sha256": base.digest(cases),
                "oracle_outputs_sha256": base.digest(expected), "oracle_sha256": before["oracle_module"],
                "cases": len(cases), "domain": "4096 loop-free four-node directed graphs plus 5 explicit edge controls"}
    candidates = {"kahn_reference": base.acyclic, "dfs_candidate": dfs_acyclic,
                  "negative_control_backward_only": _unsound_backward_only,
                  "negative_control_always_true": _unsound_always_true}
    results = []
    for name, fn in candidates.items():
        found = [fn(case) for case in cases]
        mismatch = [i for i, (a, b) in enumerate(zip(found, expected)) if type(a) is not bool or a != b]
        entry = {"candidate": name, "contract_sha256": base.digest(contract), "cases": len(cases),
                 "mismatches": len(mismatch), "first_witness": cases[mismatch[0]] if mismatch else None,
                 "finite_equivalence": not mismatch, "median_full_sweep_ns": None}
        if not mismatch:
            times = []
            for _ in range(5):
                start = perf_counter_ns()
                got = [fn(case) for case in cases]
                times.append(perf_counter_ns() - start)
                if got != expected:
                    raise ValueError("CANDIDATE_CHANGED_DURING_MEASUREMENT")
            entry.update(timing_sweeps_ns=times, median_full_sweep_ns=int(median(times)))
        results.append(entry)
    after = {"candidate_module": sha256(source.read_bytes()).hexdigest(),
             "oracle_module": sha256(baseline_file.read_bytes()).hexdigest()}
    if before != after:
        raise ValueError("VERIFIER_OR_CANDIDATE_BYTES_CHANGED")
    winner = min((r for r in results if r["finite_equivalence"]), key=lambda r:r["median_full_sweep_ns"])
    return {"schema": "szl.verifier-search-result/v0.2", "contract": contract,
            "source_sha256": before, "candidates": results, "local_diagnostic_winner": winner["candidate"],
            "production_promotion": False, "universal_equivalence_proved": False,
            "gpu_benchmark": False, "energy_measured": False, "untrusted_code_sandboxed": False,
            "timing_limitations": "Five serial sweeps in one process, fixed order, shared host; not an independent performance benchmark."}
