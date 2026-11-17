"""Reconcile six real local Putnam source-bound model responses, offline.

No network access, Lean/model execution, model rights or training promotion.
A 0% answering coverage is NOT 0% selective risk, not 0% math accuracy.
Full raw responses and questions remain owner-private outside this Git checkout.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

import challenge_index as catalog_api
import local_model_probe as inference
import putnam25_preflight as source_api

SCHEMA = "szl.putnam2025.local-model-selective/v1"
CASES = tuple(sorted(inference.SELECTED))
MAX_RECEIPT = 256 * 1024
MAX_CASE_SOURCE = source_api.MAX_LEAN_BYTES
STATUS = frozenset({
    "ABSTAIN_RECORDED",
    "NO_RESPONSE",
    "REJECTED_UNSAFE_OR_PLACEHOLDER",
    "MANUAL_EXTRACTION_REQUIRED",
    "UNVERIFIED_PROOF_TEXT",
})
OPTS = {"temperature": 0, "seed": 749, "num_predict": 384, "num_ctx": 4096}
BACKENDS = frozenset({
    "EXISTING_OLLAMA_LOOPBACK", "EXISTING_ON_HOST_TAILSCALE_LISTENER"
})


def require(test: object, reason: str) -> None:
    if not test:
        raise catalog_api.Hold(reason)


def canonical(data: dict) -> bytes:
    return catalog_api.encoded(data)


def read_regular(path: Path, limit: int) -> bytes:
    require(path.is_absolute() and path.is_file() and not path.is_symlink()
            and not (hasattr(path, "is_junction") and path.is_junction()),
            "INPUT_NOT_REGULAR")
    with path.open("rb") as f:
        raw = f.read(limit + 1)
    require(0 < len(raw) <= limit, "INPUT_BYTE_BUDGET")
    return raw


def utc(value: str):
    require(isinstance(value, str), "OBSERVATION_TIME")
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        raise catalog_api.Hold("OBSERVATION_TIME") from None
    require(stamp.tzinfo is not None and stamp.utcoffset() is not None,
            "OBSERVATION_TIME_UNZONED")
    return stamp.astimezone(timezone.utc)


def check_row(catalog: dict, original: bytes, observation: dict, *,
              model: str, digest: str) -> dict:
    """Recompute source, prompt and answer hashes; never execute proof text."""
    require(isinstance(observation, dict)
            and observation.get("schema") == inference.SCHEMA
            and observation.get("origin") == "REAL_LOCAL_INFERENCE_UNVERIFIED",
            "RESPONSE_NOT_A_LOCAL_OBSERVATION")
    name = observation.get("case_id")
    require(isinstance(name, str) and name in CASES, "CASE_OUTSIDE_BOUNDED_SET")
    require(observation.get("model_alias") == model
            and observation.get("model_manifest_digest") == digest,
            "MODEL_BINDING_MISMATCH")
    require(observation.get("source_repo") == "trishullab/PutnamBench"
            and observation.get("source_revision") == catalog_api.PUTNAM_SHA
            and observation.get("catalog_sha256") == catalog_api.sha256(canonical(catalog)),
            "CATALOG_OR_SOURCE_MISMATCH")
    entries = {x["id"]: x for x in catalog["entries"]
               if x["source"] == "putnambench" and x["id"] in CASES}
    require(name in entries, "CASE_NOT_IN_CATALOG")
    checked = source_api.check_one(name, original, entries[name])
    require(checked["status"] == "SOURCE_BYTES_ONLY"
            and checked["unsafe_code_markers"] == 0
            and observation.get("source_blob_sha1") == checked["git_blob_sha1"]
            and observation.get("source_sha256") == checked["source_sha256"],
            "ORIGINAL_SOURCE_INTEGRITY")
    prompt, theorem_sha = inference.theorem_prompt(name, original)
    require(observation.get("target_header_sha256") == theorem_sha
            and observation.get("prompt_sha256") == catalog_api.sha256(prompt.encode("utf-8"))
            and observation.get("prompt") == prompt,
            "SOURCE_BOUND_PROMPT_MISMATCH")
    require(observation.get("backend") in BACKENDS
            and observation.get("model_downloaded") is False
            and observation.get("service_started") is False,
            "UNAPPROVED_INFERENCE_BACKEND")
    if observation["backend"] == "EXISTING_ON_HOST_TAILSCALE_LISTENER":
        require(observation.get("on_host_interface_verified_externally") is True,
                "UNOBSERVED_ON_HOST_INTERFACE")
    require(observation.get("options") == OPTS
            and all(type(observation["options"][k]) is type(v)
                    for k, v in OPTS.items()),
            "SAMPLING_OPTIONS_DRIFT")
    response = observation.get("response")
    require(isinstance(response, str), "RESPONSE_TEXT_MISSING")
    try:
        response_bytes = response.encode("utf-8")
    except UnicodeError:
        raise catalog_api.Hold("RESPONSE_NOT_UTF8") from None
    label = inference.classify(response)
    require(observation.get("response_sha256") ==
            catalog_api.sha256(response_bytes)
            and observation.get("classification") == label
            and label in STATUS, "RESPONSE_VERDICT_OR_HASH_DRIFT")
    metrics = observation.get("metrics")
    require(isinstance(metrics, dict)
            and set(metrics) == {"prompt_eval_count", "eval_count", "total_duration"},
            "METRIC_CONTRACT_CHANGED")
    for value in metrics.values():
        require(value is None or (type(value) is int and value >= 0),
                "METRIC_VALUE_INVALID")
    before, after = utc(observation.get("run_started_utc")), utc(observation.get("run_finished_utc"))
    require(before <= after, "OBSERVATION_CLOCK_ORDER")
    require(observation.get("independent_lean_checker") == "NOT_RUN"
            and observation.get("verified_proof") is False
            and observation.get("statement_equivalence") == "NOT_INDEPENDENTLY_REVIEWED"
            and observation.get("benchmark_contamination_review") == "NOT_RUN"
            and observation.get("quality_score") == "UNAVAILABLE"
            and observation.get("model_retrained") is False
            and observation.get("publication_authority") is False
            and observation.get("training_authority") is False
            and observation.get("provider_mutation_count") == 0,
            "FALSE_QUALIFICATION_OR_AUTHORITY")
    return {
        "case_id": name, "classification": label,
        "source_git_blob_sha1": checked["git_blob_sha1"],
        "source_sha256": checked["source_sha256"],
        "prompt_sha256": observation["prompt_sha256"],
        "response_sha256": observation["response_sha256"],
        "response_bytes": len(response_bytes),
        "completion_tokens": metrics["eval_count"],
        "observed_start_utc": before.isoformat(),
        "observed_finish_utc": after.isoformat(),
        "qualified_proof": False,
    }


def summarize(catalog: dict, source_dir: Path,
              receipt_paths: list[Path], *, model: str, digest: str) -> dict:
    catalog_api.validate(catalog)
    require(isinstance(model, str) and 0 < len(model) <= 160
            and isinstance(digest, str) and catalog_api.HEX64.fullmatch(digest),
            "MODEL_PIN_REQUIRED")
    require(source_dir.is_absolute() and source_dir.is_dir()
            and not source_dir.is_symlink(), "SOURCE_DIRECTORY_INVALID")
    require(isinstance(receipt_paths, list) and len(receipt_paths) == len(CASES),
            "FULL_SIX_CASE_COVERAGE_REQUIRED")
    require(len({str(x.resolve()).casefold() for x in receipt_paths}) == len(CASES),
            "DUPLICATE_RECEIPT_FILE")
    observed = []
    for path in receipt_paths:
        raw = read_regular(path, MAX_RECEIPT)
        item = catalog_api.strict_json(raw, cap=MAX_RECEIPT)
        require(isinstance(item, dict), "BAD_OBSERVATION_TYPE")
        case = item.get("case_id")
        require(isinstance(case, str) and case in CASES, "INVALID_CASE_ID")
        original_file = source_dir / (case + ".lean")
        original = read_regular(original_file, MAX_CASE_SOURCE)
        result = check_row(catalog, original, item, model=model, digest=digest)
        result["receipt_sha256"] = catalog_api.sha256(raw)
        observed.append(result)
    observed.sort(key=lambda row: row["case_id"])
    require(tuple(row["case_id"] for row in observed) == CASES,
            "DUPLICATE_OR_MISSING_CASE")
    labels = Counter(row["classification"] for row in observed)
    count = len(observed)
    abstentions = labels["ABSTAIN_RECORDED"]
    non_abstaining = count - abstentions - labels["NO_RESPONSE"]
    candidates = labels["UNVERIFIED_PROOF_TEXT"]
    responses = count - labels["NO_RESPONSE"]
    return {
        "schema": SCHEMA, "state": "LOCAL_RESPONSE_BYTES_RECONCILED_NOT_PROOF",
        "source_repository": "trishullab/PutnamBench",
        "source_revision": catalog_api.PUTNAM_SHA,
        "source_catalog_sha256": catalog_api.sha256(canonical(catalog)),
        "model_alias": model, "model_digest_sha256": digest,
        "model_tag_checks": "REPORTED_BY_SINGLE_EXECUTOR_NOT_INDEPENDENTLY_WITNESSED",
        "model": "EXISTING_LOCAL_BASELINE_NOT_FLAGSHIP55",
        "expected_cases": list(CASES), "observed_cases": count,
        "source_verified_replays": count, "model_responses_observed": responses,
        "receipt_coverage": count / len(CASES),
        "abstentions": abstentions, "no_response": labels["NO_RESPONSE"],
        "non_abstention_responses": non_abstaining,
        "candidate_proof_text_count": candidates,
        "rejected_or_manual_count": (labels["REJECTED_UNSAFE_OR_PLACEHOLDER"]
                                      + labels["MANUAL_EXTRACTION_REQUIRED"]),
        "behavioural_response_coverage": responses / len(CASES),
        "answered_coverage": candidates / count,
        "abstention_fraction": abstentions / count,
        "selective_risk": "UNAVAILABLE" if candidates == 0 else "UNAVAILABLE_UNGRADED",
        "mathematical_correctness": "UNAVAILABLE",
        "independently_validated_proofs": 0,
        "independent_lean_checker": "NOT_RUN",
        "exact_formal_informal_equivalence": "NOT_INDEPENDENTLY_REVIEWED",
        "sealed_holdout_decontamination": "NOT_RUN",
        "calibrated_risk_coverage": False,
        "training_qualified": False, "publication_authority": False,
        "production_qualified": False,
        "signature": "UNSIGNED_SHA256_IS_INTEGRITY_NOT_AUTHORITY",
        "counts_by_classification": {key: labels[key] for key in sorted(STATUS)},
        "case_readbacks": observed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path, action="append")
    parser.add_argument("--model", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        inference.private_output(args.out)
        catalog = catalog_api.strict_json(read_regular(args.catalog, 2_000_000))
        result = summarize(catalog, args.source_dir, args.receipt,
                           model=args.model, digest=args.digest)
        payload = canonical(result)
        catalog_api.write_once(args.out, payload)
        print(json.dumps({
            "state": result["state"], "observed": result["observed_cases"],
            "abstentions": result["abstentions"],
            "answered_coverage": result["answered_coverage"],
            "selective_risk": result["selective_risk"],
            "math_accuracy": result["mathematical_correctness"],
            "private_receipt_sha256": catalog_api.sha256(payload),
        }, sort_keys=True))
    except (catalog_api.Hold, OSError) as exc:
        reason = str(exc) if isinstance(exc, catalog_api.Hold) else "FILESYSTEM_UNAVAILABLE"
        print(json.dumps({"state": "HOLD", "reason": reason,
                          "no_improvement_claim": True}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

