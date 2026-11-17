"""SZL Boundary Lab: bounded, offline theorem-to-runtime counterexample research.

This is NOT a Lean prover, trainer, production controller, or source-claim promoter.
All generated records are synthetic review candidates. No network calls occur.
"""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import platform
import re
from typing import Any

PRIME = 257
SOURCE_REVISION = "59d6b026b8418f59bd6535d532bdeb7551b398f0"
FORMULAS = {
    "F4": {
        "theorem": "f4_khipu_acyclic_irrefl",
        "statement": "Every Nat edge (src,dst) has dst < src; reachability decreases, hence no cycle.",
        "not_proved": "Acyclicity for an arbitrary mutable or concurrent runtime graph; Byzantine agreement.",
    },
    "F7": {
        "theorem": "f7_chaski_fifo_order",
        "statement": "Draining the encoded in-memory list queue returns messages in their enqueued order.",
        "not_proved": "Exactly-once delivery, durable recovery, or retry deduplication.",
    },
    "F18": {
        "theorem": "f18_erasure_tolerance",
        "statement": "For e : Nat with e <= 4, 6 <= 10 - e; also 10 - 6 = 4.",
        "not_proved": "An MDS encoder, decoder, or correctness of an erasure-recovery implementation.",
    },
    "F22": {
        "theorem": "f22_khipu_emit_monotone",
        "statement": "List.range n has strictly increasing values with increasing positions.",
        "not_proved": "Monotonicity of a restarted or multi-writer deployed sequence allocator.",
    },
}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode()


def digest(value: Any) -> str:
    return sha256(canonical(value)).hexdigest()


def strict_json(raw: bytes) -> Any:
    if len(raw) > 2_000_000:
        raise ValueError("INPUT_BYTE_BUDGET")
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError("DUPLICATE_KEY")
            obj[key] = value
        return obj
    def constant(_):
        raise ValueError("NONFINITE_JSON")
    # This experiment uses no floating-point inputs or JSON floating-point literals.
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant,
                      parse_float=constant)


def nat(value: Any) -> int:
    if type(value) is not int or value < 0 or value > 10000:
        raise ValueError("OUTSIDE_BOUNDED_NAT_DOMAIN")
    return value


def edges_checked(edges: Any) -> list[tuple[int, int]]:
    if type(edges) is not list or len(edges) > 100:
        raise ValueError("EDGE_BUDGET_OR_TYPE")
    result = []
    for edge in edges:
        if type(edge) not in (list, tuple) or len(edge) != 2:
            raise ValueError("EDGE_SHAPE")
        result.append((nat(edge[0]), nat(edge[1])))
    return result


def backward(edges: Any) -> bool:
    return all(dst < src for src, dst in edges_checked(edges))


def acyclic(edges: Any) -> bool:
    """Independent finite-graph oracle, not an execution of the Lean theorem."""
    rows = edges_checked(edges)
    graph: dict[int, list[int]] = {}
    degree: dict[int, int] = {}
    for src, dst in rows:
        graph.setdefault(src, []).append(dst)
        degree.setdefault(src, 0)
        degree[dst] = degree.get(dst, 0) + 1
    todo = deque(node for node, d in degree.items() if d == 0)
    removed = 0
    while todo:
        node = todo.popleft()
        removed += 1
        for dst in graph.get(node, []):
            degree[dst] -= 1
            if degree[dst] == 0:
                todo.append(dst)
    return removed == len(degree)


def fifo_trace(ops: list[str], message: int = 1) -> list[int]:
    """One-message toy queue. Retry re-enqueues without a deduplication layer."""
    nat(message)
    if type(ops) is not list or len(ops) > 20:
        raise ValueError("TRACE_BUDGET")
    queue, delivered, sent = [], [], False
    for op in ops:
        if op == "send" and not sent:
            sent = True
            queue.append(message)
        elif op == "retry" and sent:
            queue.append(message)
        elif op == "deliver" and queue:
            delivered.append(queue.pop(0))
        else:
            raise ValueError("INVALID_QUEUE_TRANSITION")
    return delivered


def sequence_trace(ops: list[str], initial: int = 0) -> list[int]:
    nat(initial)
    if type(ops) is not list or len(ops) > 20:
        raise ValueError("TRACE_BUDGET")
    counters, emitted = {"a": initial, "b": initial}, []
    for op in ops:
        if op == "reset":
            counters["a"] = initial
        elif op in ("emit_a", "emit_b"):
            owner = op[-1]
            emitted.append(counters[owner])
            counters[owner] += 1
        else:
            raise ValueError("INVALID_SEQUENCE_TRANSITION")
    return emitted


def strictly_increasing(values: list[int]) -> bool:
    for x in values:
        nat(x)
    return all(a < b for a, b in zip(values, values[1:]))


def rank_and_null(matrix: list[list[int]]) -> tuple[int, list[int] | None]:
    """Exact Gaussian elimination over fixed GF(257). A returned null vector is checked."""
    if type(matrix) is not list or not matrix or len(matrix) > 20:
        raise ValueError("MATRIX_ROW_BUDGET")
    if type(matrix[0]) is not list or not 1 <= len(matrix[0]) <= 10:
        raise ValueError("MATRIX_COLUMN_BUDGET")
    cols = len(matrix[0])
    if any(type(row) is not list or len(row) != cols for row in matrix):
        raise ValueError("RAGGED_MATRIX")
    for row in matrix:
        for x in row:
            nat(x)
    a = [[v % PRIME for v in row] for row in matrix]
    pivots, r = [], 0
    for c in range(cols):
        pivot = next((j for j in range(r, len(a)) if a[j][c]), None)
        if pivot is None:
            continue
        a[r], a[pivot] = a[pivot], a[r]
        inverse = pow(a[r][c], -1, PRIME)
        a[r] = [(v * inverse) % PRIME for v in a[r]]
        for j in range(len(a)):
            if j != r:
                factor = a[j][c]
                a[j] = [(x - factor * y) % PRIME for x, y in zip(a[j], a[r])]
        pivots.append(c)
        r += 1
        if r == len(a):
            break
    if r == cols:
        return r, None
    free = next(c for c in range(cols) if c not in pivots)
    vector = [0] * cols
    vector[free] = 1
    for row, pivot in enumerate(pivots):
        vector[pivot] = (-a[row][free]) % PRIME
    if not any(vector) or any(sum(x*y for x, y in zip(row, vector)) % PRIME for row in matrix):
        raise RuntimeError("INVALID_NULLSPACE_WITNESS")
    return r, vector


def vandermonde(start: int = 0) -> list[list[int]]:
    nat(start)
    if start > 200:
        raise ValueError("DISTINCT_POINT_DOMAIN")
    return [[pow(x, power, PRIME) for power in range(6)] for x in range(start, start + 10)]


def minimum_witnesses() -> dict:
    directed = [(s, d) for s in range(3) for d in range(3) if s != d]
    cycle = next(list(es) for k in range(1, 7) for es in combinations(directed, k)
                 if not acyclic(list(es)))
    retry = None
    checked = 0
    for length in range(1, 7):
        for trace in product(("send", "deliver", "retry"), repeat=length):
            checked += 1
            try:
                delivered = fifo_trace(list(trace))
            except ValueError:
                continue
            if len(delivered) > len(set(delivered)):
                retry = {"operations": list(trace), "delivered": delivered,
                         "searched_candidates": checked, "trace_length": length}
                break
        if retry:
            break
    reset = None
    for length in range(1, 6):
        for trace in product(("emit_a", "reset"), repeat=length):
            emitted = sequence_trace(list(trace))
            if not strictly_increasing(emitted):
                reset = {"operations": list(trace), "emitted": emitted, "trace_length": length}
                break
        if reset:
            break
    broken = vandermonde()[:6]
    for row in broken:
        row[-1] = 0
    rank, null = rank_and_null(broken)
    return {
        "F4": {"edges": cycle, "backward_hypothesis_holds": backward(cycle),
               "acyclic": acyclic(cycle), "minimal_in": "loop-free directed graphs on 3 named nodes; edge count"},
        "F7": {**retry, "minimal_in": "valid one-message send/deliver/retry traces; operation count"},
        "F18": {"erasures": 4, "survivors": 6, "rank": rank, "nonzero_null_vector": null,
                "survivor_matrix": broken, "minimality_claim": False},
        "F22": {**reset, "minimal_in": "one-writer emit/reset traces; operation count"},
        "locked_theorem_refuted": False,
        "interpretation": "Counterexamples to stronger runtime claims, not to the locked statements.",
    }


def finite_validation() -> dict:
    edges = [(s, d) for s in range(4) for d in range(4) if s != d]
    admitted, failures = 0, 0
    for mask in range(1 << len(edges)):
        chosen = [e for bit, e in enumerate(edges) if (mask >> bit) & 1]
        if backward(chosen):
            admitted += 1
            failures += not acyclic(chosen)
    matrix = vandermonde()
    ranks = [rank_and_null([matrix[i] for i in survivors])[0]
             for survivors in combinations(range(10), 6)]
    return {"directed_graphs_on_four_nodes": 4096, "backward_graphs": admitted,
            "within_domain_cycle_failures": failures,
            "vandermonde_survivor_subsets": len(ranks), "full_rank_subsets": ranks.count(6),
            "field_modulus": PRIME, "lean_kernel_executed": False,
            "scope": "Exact finite checks of this prototype; neither universal proof nor model evaluation."}


def make_cases() -> list[dict]:
    rows = []
    for formula in FORMULAS:
        for family in range(2):
            for parameter in (1, 2):
                for mutate in (False, True):
                    if formula == "F4":
                        n = family + 2
                        es = [(i + parameter + 1, i + parameter) for i in range(n - 1)]
                        if mutate:
                            es.append((parameter, parameter + n - 1))
                        scenario = {"edges": es}
                        holds, hypothesis = acyclic(es), backward(es)
                    elif formula == "F7":
                        ops = ["send", "deliver"]
                        if mutate:
                            ops = (["send", "deliver", "retry", "deliver"] if family == 0
                                   else ["send", "retry", "deliver", "deliver"])
                        observed = fifo_trace(ops, parameter)
                        scenario = {"operations": ops, "message": parameter, "delivered": observed}
                        holds, hypothesis = len(observed) == len(set(observed)), True  # FIFO does not imply uniqueness.
                    elif formula == "F18":
                        full = vandermonde(parameter + 10 * family)
                        survivors = full[:6]
                        if mutate:
                            if family == 0:
                                survivors = [row[:-1] + [0] for row in survivors]
                            else:
                                survivors = [survivors[0][:] for _ in range(6)]
                        rank, null = rank_and_null(survivors)
                        scenario = {"erasures": 4, "survivors": 6, "matrix": survivors,
                                    "rank": rank, "nonzero_null_vector": null, "field_modulus": PRIME}
                        holds, hypothesis = rank == 6, True  # Numerical F18 hypothesis holds in BOTH cases.
                    else:
                        ops = ["emit_a"] * (parameter + 1)
                        if mutate:
                            ops += (["reset", "emit_a"] if family == 0 else ["emit_b"])
                        observed = sequence_trace(ops)
                        scenario = {"operations": ops, "emitted": observed}
                        holds, hypothesis = strictly_increasing(observed), not mutate
                    content = {"formula": formula, "scenario": scenario}
                    family_id = f"{formula}/mechanism-{family}"
                    rows.append({
                        "schema": "szl.boundary-fixture/v0.1",
                        "id": digest({**content, "family": family_id}),
                        "task_fingerprint": digest(content), "formula_id": formula,
                        "source_revision": SOURCE_REVISION,
                        "source_path": "claims/locked-formulas.v1.json",
                        "theorem": FORMULAS[formula]["theorem"],
                        "source_statement_summary": FORMULAS[formula]["statement"],
                        "runtime_claim_not_proved_by_source": FORMULAS[formula]["not_proved"],
                        "relationship": {"F4": "CHECK_SOURCE_HYPOTHESIS",
                                         "F7": "FIFO_DOES_NOT_ENTAIL_UNIQUENESS",
                                         "F18": "COUNT_DOES_NOT_ENTAIL_RECOVERY",
                                         "F22": "RUNTIME_ENCODING_REQUIRES_REFINEMENT"}[formula],
                        "generator_family": family_id,
                        "split": "development" if family == 0 else "diagnostic_holdout",
                        "scenario": scenario, "synthetic": True,
                        "source_hypotheses_apply_to_original_encoding": hypothesis,
                        "runtime_property_holds_in_this_finite_scenario": holds,
                        "label": "FINITE_CONTROL_PASS" if holds else "RUNTIME_COUNTEREXAMPLE",
                        "kernel_proof": "NOT_RUN", "training_admission": "REVIEW_REQUIRED",
                        "locked_status_changed": False, "model_evaluation": False,
                    })
    # A shared positive control must not cross the split. Remove holdout duplicates,
    # retain the first occurrence in canonical generation order, and report the count.
    seen, unique = set(), []
    for row in rows:
        if row["task_fingerprint"] not in seen:
            unique.append(row)
            seen.add(row["task_fingerprint"])
    return unique


def validate_split(rows: list[dict]) -> dict:
    families: dict[str, set] = {}
    fingerprints: dict[str, set] = {}
    ids = set()
    for row in rows:
        if row["id"] in ids:
            raise ValueError("DUPLICATE_CASE_ID")
        ids.add(row["id"])
        split = row["split"]
        if split not in ("development", "diagnostic_holdout"):
            raise ValueError("UNKNOWN_SPLIT")
        families.setdefault(split, set()).add(row["generator_family"])
        fingerprints.setdefault(split, set()).add(row["task_fingerprint"])
    if len(families) != 2:
        raise ValueError("BOTH_SPLITS_REQUIRED")
    if families["development"] & families["diagnostic_holdout"]:
        raise ValueError("GENERATOR_FAMILY_LEAKAGE")
    if fingerprints["development"] & fingerprints["diagnostic_holdout"]:
        raise ValueError("EXACT_TASK_LEAKAGE")
    return {"records": len(rows),
            "development": sum(r["split"] == "development" for r in rows),
            "diagnostic_holdout": sum(r["split"] == "diagnostic_holdout" for r in rows),
            "generator_family_overlap": 0, "exact_task_overlap": 0,
            "independently_sealed_holdout": False,
            "semantic_leakage_eliminated": False,
            "note": "Family-disjoint diagnostic split only. Developer knows both sets; not a blind evaluation."}


def validate_sources(source: dict) -> None:
    if source.get("schema") != "szl.boundary-sources/v0.1":
        raise ValueError("SOURCE_SCHEMA")
    if source.get("formula_revision") != SOURCE_REVISION:
        raise ValueError("FORMULA_REVISION_CHANGED")
    for item in source.get("datasets", []):
        if not re.fullmatch("[0-9a-f]{40}", item.get("revision", "")):
            raise ValueError("MUTABLE_DATASET_REVISION")
        if not re.fullmatch("[0-9a-f]{64}", item.get("sha256", "")):
            raise ValueError("DATASET_HASH_REQUIRED")
        if item.get("use") != "inspection_only_not_training_admission":
            raise ValueError("DATASET_AUTHORITY_ESCALATION")
    if len(source.get("datasets", [])) != 4:
        raise ValueError("DATASET_SCOPE_CHANGED")


def run(out: Path, source_path: Path) -> dict:
    source_bytes = source_path.read_bytes()
    source = strict_json(source_bytes)
    validate_sources(source)
    rows = make_cases()
    split = validate_split(rows)
    checks = finite_validation()
    witnesses = minimum_witnesses()
    out.mkdir(parents=True, exist_ok=False)
    payloads = {"candidates.jsonl": b"".join(canonical(r) for r in rows),
                "witnesses.json": canonical(witnesses),
                "finite-validation.json": canonical(checks),
                "split-audit.json": canonical(split)}
    for name, raw in payloads.items():
        with (out / name).open("xb") as f:
            f.write(raw)
    record = {"schema": "szl.boundary-run/v0.1",
              "observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "platform": platform.platform(), "python": platform.python_version(),
              "source_manifest_sha256": sha256(source_bytes).hexdigest(),
              "code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "outputs": {n: {"sha256": sha256(b).hexdigest(), "bytes": len(b)}
                          for n, b in payloads.items()},
              "split": split, "finite_validation": checks,
              "status": "OFFLINE_RESEARCH_PROTOTYPE_EXECUTED",
              "model_inference_calls": 0, "training_runs_started": 0,
              "production_mutations": 0, "novelty_established": False,
              "new_general_theorem_proved": False, "kernel_proof_execution": False,
              "publications": 0, "signatures_or_independent_attestations": False}
    (out / "run-receipt.json").write_bytes(canonical(record))
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path(__file__).with_name("sources.json"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.out, args.sources), indent=2))


if __name__ == "__main__":
    main()
