#!/usr/bin/env python3
"""Deterministic SZL Lutar A1-A5 synthetic *training candidates*.

No model weights, Lean proof, reviewer approval, independent holdout, or live
runtime evidence is created here. The fixed sources are immutable protected-main
GitHub blobs; do not silently rebind to a different source or theorem statement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from math import isqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = {
    "repository": "szl-holdings/lutar-lean",
    "commit": "c2ca813fca00ecf58bcc5f505f2aa4237fbf2481",
    "axioms_path": "Lutar/Axioms.lean",
    "axioms_blob": "fc922178ca30d588dbb330dc834428bcfca36367",
    "invariant_path": "Lutar/Invariant.lean",
    "invariant_blob": "4a418c631d9556d418e6aaa47611014855050d2c",
    "toolchain": "leanprover/lean4:v4.35.0",
}
SCHEMA = "szl.lutar.numeric-curriculum/v1"
SYSTEM = (
    "You are an SZL Lutar mathematics assistant. Answer this numerical question "
    "using the pinned A1-A5 definitions. Return one valid JSON object. "
    "Distinguish mathematical counterexamples from Lean proofs, and never "
    "infer production readiness from a score or a green CI result."
)
FAMILIES = (
    "A1_MONOTONE", "A2_HOMOGENEOUS", "A3_DIAGONAL", "A4_BOUNDED",
    "A5_PERMUTATION", "UNIQUENESS_COUNTEREXAMPLE", "WEIGHTED_A5_COUNTEREXAMPLE",
    "GATE_DENY", "GATE_CONDITIONAL_ALLOW", "ZERO_AXIS",
)
GATES = (
    "current_required_ci", "checked_source_sha", "publisher_source_sha",
    "runtime_source_sha", "verified_signature", "fresh_evidence",
    "healthy_runtime", "owner_approval", "maintenance_window",
)
TRAIN_VALUES = range(2, 18)
EVAL_VALUES = range(20, 28)


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":"))


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def lambda2_exact(x: tuple[int, int]) -> int:
    """Exact equal-weight geometric mean on perfect-square-product inputs only."""
    if len(x) != 2 or any(type(v) is not int or v < 0 for v in x):
        raise ValueError("nonnegative integer axes are required")
    root = isqrt(x[0] * x[1])
    if root * root != x[0] * x[1]:
        raise ValueError("fixture product is not an exact square")
    return root


def case(n: int, family: str) -> tuple[str, dict, dict]:
    if type(n) is not int or n < 2 or family not in FAMILIES:
        raise ValueError("unsupported deterministic curriculum case")
    x = (n * n, (n + 1) * (n + 1))
    base = lambda2_exact(x)
    detail = {"n": n, "axes": list(x), "lambda_2": base}
    if family == "A1_MONOTONE":
        y = ((n + 2)**2, (n + 3)**2)
        larger = lambda2_exact(y)
        assert y[0] >= x[0] and y[1] >= x[1] and larger >= base
        prompt = f"A1: x={list(x)}, y={list(y)}, and x_i<=y_i. Is Lambda_2(x)<=Lambda_2(y)? Give both exact values."
        answer = {"verdict": "YES", "axiom": "A1", "lambda_x": base, "lambda_y": larger}
        detail["y"] = list(y)
    elif family == "A2_HOMOGENEOUS":
        c = (n + 2)**2
        cx = (c * x[0], c * x[1])
        scaled = lambda2_exact(cx)
        assert scaled == c * base
        prompt = f"A2: x={list(x)} and c={c}. Compute Lambda_2(c*x) and c*Lambda_2(x)."
        answer = {"verdict": "EQUAL", "axiom": "A2", "left": scaled, "right": c * base}
        detail["scale"] = c
    elif family == "A3_DIAGONAL":
        x = (n, n)
        assert lambda2_exact(x) == n
        prompt = f"A3: every axis equals {n}. What does the equal-weight Lambda_2 return?"
        answer = {"verdict": "EQUAL_TO_INPUT", "axiom": "A3", "lambda": n}
        detail["axes"] = list(x)
    elif family == "A4_BOUNDED":
        hi = max(x)
        assert base <= hi
        prompt = f"A4: x={list(x)}. Check Lambda_2(x)<=max(x); report the exact bound."
        answer = {"verdict": "BOUNDED", "axiom": "A4", "lambda": base, "maximum": hi}
    elif family == "A5_PERMUTATION":
        swapped = (x[1], x[0])
        assert lambda2_exact(swapped) == base
        prompt = f"A5: compare equal-weight Lambda_2({list(x)}) and Lambda_2({list(swapped)})."
        answer = {"verdict": "INVARIANT", "axiom": "A5", "left": base, "right": base}
    elif family == "UNIQUENESS_COUNTEREXAMPLE":
        witness = (1, n*n)
        geo = lambda2_exact(witness)
        maximum = max(witness)
        assert maximum != geo
        prompt = (f"Claim: A1-A5 uniquely force the geometric mean. For x={list(witness)}, "
                  "compare max(x) with Lambda_2(x), remembering max also satisfies A1-A5.")
        answer = {"verdict": "REFUTED", "claim": "UNCONDITIONAL_UNIQUENESS",
                  "max_x": maximum, "lambda_x": geo, "needs": "ADDITIONAL_ASSUMPTIONS"}
        detail["counterexample"] = list(witness)
    elif family == "WEIGHTED_A5_COUNTEREXAMPLE":
        a, b = n, n+1
        fwd, reverse = a**3 * b, b**3 * a
        assert fwd != reverse
        prompt = (f"Fixed unequal weights (3/4,1/4): x={[a**4,b**4]}. "
                  "Check whether swapping ONLY the axes keeps the weighted product unchanged.")
        answer = {"verdict": "NOT_INVARIANT", "axiom": "A5_REQUIRES_WEIGHT_PERMUTATION",
                  "original": fwd, "axes_swapped": reverse}
        detail["weighted_axes"] = [a**4, b**4]
    elif family == "GATE_DENY":
        missing = GATES[n % len(GATES)]
        prompt = (f"Lutar release gate: all mandatory facts true EXCEPT {missing}=false; "
                  f"Lambda_2({list(x)})={base}. What is the effective score? "
                  "Do not claim a production release.")
        answer = {"verdict": "HOLD", "failed_gate": missing, "effective_lambda": 0,
                  "production": "NOT_PROVEN"}
        detail["missing_gate"] = missing
    elif family == "GATE_CONDITIONAL_ALLOW":
        prompt = (f"Assume all nine independently authenticated release premises hold, "
                  f"and Lambda_2({list(x)})={base}. What score follows *conditionally*? "
                  "Does this calculation itself prove deployment?")
        answer = {"verdict": "CONDITIONAL_ONLY", "effective_lambda": base,
                  "production": "NOT_PROVEN"}
    else:
        assert family == "ZERO_AXIS"
        x = (0, n*n)
        assert lambda2_exact(x) == 0
        prompt = f"Equal-weight Lambda_2({list(x)}): compute the exact value; do not treat it as evidence of a running system."
        answer = {"verdict": "ZERO", "lambda": 0, "production": "NOT_PROVEN"}
        detail["axes"] = list(x)
    return prompt, answer, detail


def records(split: str) -> list[dict]:
    if split not in {"train", "holdout"}:
        raise ValueError("unknown split")
    values = TRAIN_VALUES if split == "train" else EVAL_VALUES
    rows = []
    for family in FAMILIES:
        for n in values:
            prompt, answer, witness = case(n, family)
            messages = [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": canonical(answer)},
            ]
            ident = sha256(canonical({"family": family, "n": n, "prompt": prompt}).encode())
            rows.append({
                "messages": messages,
                "metadata": {
                    "case_id": ident, "schema": SCHEMA, "split": split,
                    "family": family, "source": SOURCE,
                    "oracle": "EXACT_INTEGER_SYNTHETIC",
                    "evidence": witness,
                    "review_state": "CANDIDATE_ONLY",
                    "training_authority": "NONE",
                    "proof_status": "NOT_LEAN_VERIFIED_AS_DATASET",
                },
            })
    return rows


def exact_numeric_reward(reference: dict, proposed_json: str) -> float:
    """Bounded, exact SFT/RLVR label reward; NOT a Lean referee reward.

    The caller must supply a trusted, source-bound reference row. This is only
    a numerical/structural oracle for the synthetic task distribution and
    cannot certify an arbitrary theorem, model, or live release.
    """
    if not isinstance(reference, dict) or not isinstance(proposed_json, str):
        return 0.0
    md = reference.get("metadata")
    messages = reference.get("messages")
    if (not isinstance(md, dict) or md.get("schema") != SCHEMA
            or md.get("source") != SOURCE
            or not isinstance(messages, list) or len(messages) != 3
            or len(proposed_json.encode("utf-8")) > 4096):
        return 0.0
    def unique_pairs(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate JSON key")
            out[key] = value
        return out

    def reject_constant(_):
        raise ValueError("non-finite JSON value")

    try:
        target = json.loads(messages[2]["content"])
        proposed = json.loads(proposed_json, object_pairs_hook=unique_pairs,
                              parse_constant=reject_constant)
    except (ValueError, TypeError, KeyError, IndexError):
        return 0.0
    if not isinstance(proposed, dict) or any(type(v) is bool for v in proposed.values()):
        return 0.0
    return 1.0 if type(target) is dict and proposed == target else 0.0


def rendered() -> dict[str, bytes]:
    result = {}
    for split in ("train", "holdout"):
        result[f"{split}.jsonl"] = (
            "".join(canonical(row) + "\n" for row in records(split))
        ).encode("utf-8")
    manifest = {
        "schema": "szl.lutar.numeric-curriculum-manifest/v1",
        "source": SOURCE,
        "train": {"rows": len(records("train")),
                  "sha256": sha256(result["train.jsonl"])},
        "holdout": {"rows": len(records("holdout")),
                    "sha256": sha256(result["holdout.jsonl"])},
        "generator": "curriculum/lutar_axioms.py",
        "data_origin": "FIRST_PARTY_DETERMINISTIC_SYNTHETIC",
        "model_weights": "NONE",
        "independent_holdout": False,
        "review_state": "REVIEW_REQUIRED",
        "training_authority": "NONE",
        "lean_proof_of_dataset": False,
        "runtime_qualification": False,
        "license": "Apache-2.0",
    }
    result["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True)
                               + "\n").encode("utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = rendered()
    if args.check:
        for name, blob in files.items():
            path = ROOT / name
            if not path.is_file() or path.read_bytes() != blob:
                print(f"FAIL_CLOSED: generated artifact differs: {name}")
                return 1
        print("PASS: exact source-bound Lutar numeric curriculum is reproducible")
        return 0
    for name, blob in files.items():
        (ROOT / name).write_bytes(blob)
        print(f"wrote {name}: {len(blob)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
