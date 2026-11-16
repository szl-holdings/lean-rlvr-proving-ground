"""Frozen diagnostic contracts. Missing/invalid attempts never disappear from coverage.

A self-hash binds bytes, not authorship or independence. Pin contract and grader
outside a candidate writer's authority before use. This is not a process sandbox.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import re

ARMS = ("A", "B", "C", "D")
DECISIONS = ("SUPPORTED", "UNSUPPORTED", "UNKNOWN")


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n").encode()


def digest(value):
    return sha256(canonical(value)).hexdigest()


def count(value, *, positive=False):
    if type(value) is not int or not (1 if positive else 0) <= value <= 10**9:
        raise ValueError("INVALID_COUNT")
    return value


def frozen_plan(cases, *, model_digest, tokenizer_digest, grader_digest, max_input_tokens=2048,
                max_output_tokens=64, seeds=(749,)):
    for value in (model_digest, tokenizer_digest, grader_digest):
        if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None:
            raise ValueError("IMMUTABLE_DIGEST_REQUIRED")
    if type(cases) is not list or not 1 <= len(cases) <= 2000:
        raise ValueError("CASE_BUDGET")
    for case in cases:
        if set(case) != {"id", "family", "expected", "task_sha256"} or case["expected"] not in DECISIONS[:2]:
            raise ValueError("CASE_SCHEMA")
        if any(type(case[k]) is not str or not case[k] for k in ("id", "family")):
            raise ValueError("CASE_IDENTITY")
        if type(case["task_sha256"]) is not str or re.fullmatch(r"[a-f0-9]{64}", case["task_sha256"]) is None:
            raise ValueError("TASK_DIGEST")
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("DUPLICATE_CASE")
    if not 1 <= len(seeds) <= 3 or any(type(s) is not int or not 0 <= s < 2**31 for s in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("SEED_CONTRACT")
    count(max_input_tokens, positive=True)
    count(max_output_tokens, positive=True)
    return {"schema": "szl.boundary-experiment/v0.2", "cases": deepcopy(cases), "arms": list(ARMS),
            "seeds": list(seeds), "model_digest": model_digest, "tokenizer_digest": tokenizer_digest,
            "grader_digest": grader_digest, "max_input_tokens": max_input_tokens,
            "max_output_tokens": max_output_tokens, "independent_holdout": False,
            "training_authority": False, "production_qualification": False}


def score(plan, rows, *, expected_plan_sha256):
    if digest(plan) != expected_plan_sha256:
        raise ValueError("CONTRACT_CHANGED")
    rebuilt = frozen_plan(plan["cases"], model_digest=plan["model_digest"], tokenizer_digest=plan["tokenizer_digest"],
                          grader_digest=plan["grader_digest"], max_input_tokens=plan["max_input_tokens"],
                          max_output_tokens=plan["max_output_tokens"], seeds=plan["seeds"])
    if plan != rebuilt:
        raise ValueError("UNSUPPORTED_PLAN_MODIFICATION")
    expected = {(a, c["id"], s) for a in ARMS for c in plan["cases"] for s in plan["seeds"]}
    observed = {}
    for row in rows:
        fields = {"arm", "case_id", "seed", "status", "decision", "input_tokens", "output_tokens", "model_digest", "task_sha256"}
        if type(row) is not dict or set(row) != fields or type(row["seed"]) is not int:
            raise ValueError("ROW_SCHEMA")
        key = (row["arm"], row["case_id"], row["seed"])
        if key not in expected or key in observed:
            raise ValueError("UNEXPECTED_OR_DUPLICATE_ATTEMPT")
        case = next(c for c in plan["cases"] if c["id"] == row["case_id"])
        if row["model_digest"] != plan["model_digest"] or row["task_sha256"] != case["task_sha256"]:
            raise ValueError("ATTEMPT_BINDING_CHANGED")
        if row["status"] not in {"OK", "ERROR", "TRUNCATED", "INVALID_OUTPUT"}:
            raise ValueError("ATTEMPT_STATUS")
        if row["status"] == "OK":
            if row["decision"] not in DECISIONS:
                raise ValueError("DECISION")
            if count(row["input_tokens"]) > plan["max_input_tokens"] or count(row["output_tokens"]) > plan["max_output_tokens"]:
                raise ValueError("BUDGET_EXCEEDED")
        elif row["decision"] is not None:
            raise ValueError("FAILED_ATTEMPT_CANNOT_BECOME_ANSWER")
        observed[key] = row
    results = {}
    for arm in ARMS:
        supported = [c for c in plan["cases"] if c["expected"] == "SUPPORTED"]
        unsupported = [c for c in plan["cases"] if c["expected"] == "UNSUPPORTED"]
        n_s, n_u = len(supported) * len(plan["seeds"]), len(unsupported) * len(plan["seeds"])
        ok = [r for k, r in observed.items() if k[0] == arm and r["status"] == "OK"]
        s_ids = {c["id"] for c in supported}
        false_accepts = sum(r["case_id"] not in s_ids and r["decision"] == "SUPPORTED" for r in ok)
        correct_supported = sum(r["case_id"] in s_ids and r["decision"] == "SUPPORTED" for r in ok)
        supported_unknown = sum(r["case_id"] in s_ids and r["decision"] == "UNKNOWN" for r in ok)
        attempted = sum(k[0] == arm for k in observed)
        total = n_s + n_u
        complete = len(ok) == total
        results[arm] = {"expected_attempts": total, "attempted": attempted, "valid_responses": len(ok),
                       "missing_attempts": total-attempted, "invalid_or_failed": attempted-len(ok),
                       "unsupported_cases": n_u, "supported_cases": n_s,
                       "unsupported_acceptance_count": false_accepts,
                       "correct_supported_count": correct_supported,
                       "unnecessary_refusal_count": supported_unknown,
                       "unsupported_acceptance_rate": false_accepts/n_u if complete and n_u else None,
                       "supported_answer_accuracy": correct_supported/n_s if complete and n_s else None,
                       "status": "DIAGNOSTIC_COMPLETE" if complete else "INCOMPLETE_NO_RATE_CLAIM"}
    return {"schema": "szl.boundary-evaluation/v0.2", "plan_sha256": expected_plan_sha256,
            "arms": results, "model_improvement_established": False,
            "independent_holdout": False, "production_qualification": False,
            "inference": "Descriptive developer diagnostics; no independent holdout or confidence-based promotion."}
