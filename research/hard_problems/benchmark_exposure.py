"""Offline metadata-only exposure review; never grants benchmark or training admission."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import challenge_index as index

SCHEMA = "szl.benchmark-exposure-review/v1"
FIELDS = {"schema", "case_id", "source_sha256", "prompt_sha256", "answer_exposure",
          "training_overlap", "rights_review", "reviewer_evidence_sha256"}


def review(raw: bytes) -> dict:
    record = index.strict_json(raw, cap=16_384)
    index.require(type(record) is dict and set(record) == FIELDS, "REVIEW_FIELDS")
    index.require(record["schema"] == SCHEMA, "REVIEW_SCHEMA")
    index.require(type(record["case_id"]) is str and index.ID.fullmatch(record["case_id"]),
                  "CASE_ID")
    for key in ("source_sha256", "prompt_sha256"):
        index.require(type(record[key]) is str and index.HEX64.fullmatch(record[key]),
                      "SOURCE_OR_PROMPT_NOT_BOUND")
    enums = {
        "answer_exposure": {"EXPOSED", "NOT_OBSERVED", "UNKNOWN"},
        "training_overlap": {"FOUND", "NOT_OBSERVED", "UNKNOWN"},
        "rights_review": {"REVIEWED_FOR_EVALUATION", "NOT_REVIEWED", "PROHIBITED"},
    }
    for key, values in enums.items():
        index.require(type(record[key]) is str and record[key] in values, "REVIEW_STATE")
    evidence = record["reviewer_evidence_sha256"]
    index.require(evidence is None or (type(evidence) is str and index.HEX64.fullmatch(evidence)),
                  "REVIEW_EVIDENCE_DIGEST")
    reasons = []
    if record["answer_exposure"] == "EXPOSED":
        reasons.append("ANSWER_EXPOSED_NOT_HELD_OUT")
    elif record["answer_exposure"] == "UNKNOWN":
        reasons.append("ANSWER_EXPOSURE_UNKNOWN")
    if record["training_overlap"] == "FOUND":
        reasons.append("TRAINING_OVERLAP_FOUND")
    elif record["training_overlap"] == "UNKNOWN":
        reasons.append("TRAINING_OVERLAP_UNKNOWN")
    if record["rights_review"] != "REVIEWED_FOR_EVALUATION":
        reasons.append("EVALUATION_RIGHTS_" + record["rights_review"])
    if evidence is None:
        reasons.append("REVIEW_EVIDENCE_MISSING")
    return {
        "schema": SCHEMA, "case_id": record["case_id"],
        "input_sha256": index.sha256(raw),
        "source_sha256": record["source_sha256"],
        "prompt_sha256": record["prompt_sha256"],
        "reviewer_evidence_sha256": evidence,
        "state": "HOLD" if reasons else "REVIEW_CANDIDATE_ONLY",
        "hold_reasons": reasons,
        "evidence_verified": False,
        "heldout_admitted": False, "training_admitted": False,
        "model_evaluation": "NOT_RUN", "mathematical_correctness": "UNAVAILABLE",
        "signature": "UNSIGNED_HONEST",
        "scope": "Declared metadata only; hashes do not prove rights or absence of contamination",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    args = parser.parse_args()
    try:
        index.require(args.review.is_file() and not args.review.is_symlink(), "REVIEW_FILE")
        with args.review.open("rb") as handle:
            result = review(handle.read(16_385))
        print(json.dumps(result, sort_keys=True))
        return 2 if result["state"] == "HOLD" else 0
    except (index.Hold, OSError) as error:
        print(json.dumps({"state": "HOLD", "reason": str(error) if isinstance(error, index.Hold)
                          else "FILESYSTEM_UNAVAILABLE", "heldout_admitted": False,
                          "training_admitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
