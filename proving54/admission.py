#!/usr/bin/env python3
"""54h five-role proving-ground policy + deterministic CPU seed, NOT a GPU runner.

This tool checks a reviewed manifest and five first-party exact arithmetic
fixtures. It never loads, trains or publishes a model, reads credentials,
opens sockets, launches subprocesses, dispatches Salad jobs, manages Massed
instances, or runs untrusted Lean. Real proof requires independent kernel
and reviewer evidence from the already canonical RLVR referee.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re

SCHEMA = "szl.proving-ground.54h/v1"
REPORT_SCHEMA = "szl.proving54-source-gate/v1"
ROLE_IDS = ("YACHAY", "KHIPU", "LUTAR", "HATUN", "CODEX")
EXPECTED_SOURCE = {
    "lean-rlvr-proving-ground": ("996146229ebcf78e37413e64a05f0245bbd194c3", "probes/Probes.lean", "2cbaf334328ada8ef6f57252176873136d3119c3"),
    "szl-gpu-bridge": ("5d8f6034a84fe37a4116ff9d7cb4a35f7dcbe667", "docs/OUROBOROS_CURRICULUM.md", "517ddea3cf52428f3d64a30d4a30d4e07645e9b2"),
    "szl-papers": ("39c228dc3a29c6cfd831d43be6a8531e718692ac", "PAPERS_INDEX.md", "fc10712a26657f7d68333aaddc4414296d678be0"),
    "lutar-lean": ("80e35f859801d80fce7cf81e4d9b0c8bdf91cfea", "Lutar/Uniqueness/TheoremU.lean", "e9af0175cbd68c633902676b97aea193040fa725"),
    "hatun-mcp": ("1cec84742e07c151a34c329ae2fb50dd5f87c7ab", "docs/HATUN_SURFACE_CONTRACT.md", "8635de832d7f7006fca846b93fe417785a63704b"),
    "szl-lake": ("7e19e7f0d56d98fb78c7af6b9369819edaf37262", "README.md", "455d5c65949bb6f317e3a7ed2b42118b00373550"),
    "szl-khipu": ("5a6a3843008906051e7b3289767078cd04d26ac3", "README.md", "24e0a668ca7577a44a5b054e05191055adcbd513"),
    "szl-formulas": ("9c74b29de9c061ac599a7349c079599a3c298af5", "README.md", "26afc2c8e728749e8fa2a4e68c3432c2706dff93"),
    "szl-forge": ("249e37a74f26e3bae41323f106be9de8f814cc44", "training/README.md", "be14acb08f2f246b1c312684951de67187f23b08"),
    "szl-router": ("26a0bcd568f302d663d0678b5bf5b4dea24a66ae", "docs/SALAD_MASSED_FRONTIER_20261118.md", "e86804c3389cc398c26df359cef04fd9cb9122ff"),
    "a11oy": ("5ac8033b0caa8f630f1fe7e68d6b9383fc9c2972", "docs/GOVERNED_ADMISSION_FLOW.md", "3c5e1e79013f6d6d0103f2034d8f0885425c0c17"),
}
EXPECTED_TOP = frozenset({
    "schema", "name", "window", "phase_boundaries", "logical_roles",
    "source_registry", "external_references", "unresolved_source_aliases",
    "scientific_open_challenges", "output_policy", "physical_capacity",
    "source_governance", "all_answered_gate", "release_status",
    "citations_or_proofs_cannot_be_inferred_from_green_ci",
})
EXPECTED_PHASES = (
    ("FOUNDATION", 0, 24),
    ("SKILLS", 24, 48),
    ("PROOF", 48, 54),
)
START = datetime(2026, 11, 18, 5, 5, 32, tzinfo=timezone.utc)
MAX_INPUT_BYTES = 100_000


class Hold(ValueError):
    """Stable refusal, without leaking input content or credentials."""


def require(value: bool, reason: str) -> None:
    if not value:
        raise Hold(reason)


def _strict_pairs(pairs):
    record = {}
    for key, value in pairs:
        if key in record:
            raise Hold("DUPLICATE_JSON_FIELD")
        record[key] = value
    return record


def parse(raw: bytes) -> dict:
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_INPUT_BYTES, "MANIFEST_BYTE_LIMIT")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_strict_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(Hold("NONFINITE_INPUT")),
        )
    except (UnicodeError, ValueError) as exc:
        if isinstance(exc, Hold):
            raise
        raise Hold("INVALID_JSON") from None
    require(isinstance(value, dict), "MANIFEST_OBJECT_REQUIRED")
    return value


def _utc(value: str | datetime) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise Hold("INVALID_TIMESTAMP") from None
    require(isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() is not None, "UTC_CLOCK_REQUIRED")
    return value.astimezone(timezone.utc)


def validate(manifest: dict) -> None:
    require(set(manifest) == EXPECTED_TOP and manifest.get("schema") == SCHEMA,
            "EXACT_SOURCE_POLICY_FIELDS_REQUIRED")
    window = manifest["window"]
    require(isinstance(window, dict) and set(window) ==
            {"start_utc", "end_utc", "duration_hours"}, "WINDOW_FIELDS_REQUIRED")
    start = _utc(window["start_utc"])
    end = _utc(window["end_utc"])
    require(start == START and type(window["duration_hours"]) is int
            and window["duration_hours"] == 54
            and end - start == timedelta(hours=54), "EXACT_54H_WINDOW_REQUIRED")
    phases = manifest["phase_boundaries"]
    require(isinstance(phases, list) and len(phases) == 3, "THREE_PHASES_REQUIRED")
    for row, (name, lower, upper) in zip(phases, EXPECTED_PHASES):
        require(isinstance(row, dict) and row.get("id") == name
                and type(row.get("start_hour")) is int
                and type(row.get("end_hour")) is int
                and row["start_hour"] == lower and row["end_hour"] == upper,
                "PHASE_COVERAGE_MISMATCH")
    roles = manifest["logical_roles"]
    require(isinstance(roles, list) and len(roles) == 5
            and tuple(r.get("id") if isinstance(r, dict) else None for r in roles)
            == ROLE_IDS, "FIVE_DISTINCT_LOGICAL_ROLES_REQUIRED")
    sources = manifest["source_registry"]
    require(isinstance(sources, list) and len(sources) == len(EXPECTED_SOURCE),
            "SOURCE_POPULATION_MISMATCH")
    seen = set()
    for row in sources:
        require(isinstance(row, dict) and set(row) ==
                {"repo", "commit", "path", "git_blob", "role", "allowed_use", "rights"},
                "SOURCE_RECORD_FIELDS_REQUIRED")
        name = row["repo"]
        require(isinstance(name, str) and name.startswith("szl-holdings/"),
                "SOURCE_REPO_NOT_CANONICAL")
        name = name.split("/", 1)[1]
        require(name not in seen and name in EXPECTED_SOURCE,
                "UNKNOWN_OR_DUPLICATE_SOURCE")
        seen.add(name)
        require((row["commit"], row["path"], row["git_blob"]) ==
                EXPECTED_SOURCE[name], "SOURCE_PIN_CHANGED")
        require(row["allowed_use"] == "POINTER_ONLY_NO_GRADIENTS" and
                row["rights"] == "REVIEW_REQUIRED", "NO_TRAINING_RIGHTS_ASSUMED")
    require(manifest["unresolved_source_aliases"] == ["codicies"],
            "UNKNOWN_CODEX_SOURCE_NOT_RESOLVED")
    science = manifest["scientific_open_challenges"]
    require(isinstance(science, list) and len(science) == 5
            and len(set(science)) == 5, "FIVE_UNSOLVED_SCIENCE_DOMAINS_REQUIRED")
    physical = manifest["physical_capacity"]
    require(isinstance(physical, dict) and
            physical.get("five_unique_host_liveness_proved") is False and
            physical.get("new_gpu_replicas_allowed") == 0 and
            physical.get("paid_compute_authorized") is False,
            "COMPUTE_BUDGET_OR_FIVE_NODE_CLAIM_UNSUPPORTED")
    governance = manifest["source_governance"]
    require(isinstance(governance, dict) and
            governance.get("sensitive_data_admitted") is False and
            governance.get("official_benchmark_items_in_training") is False and
            governance.get("model_outputs_promoted_to_training") is False,
            "REVIEWED_DATA_NOT_ADMITTED")
    outputs = manifest["output_policy"]
    require(isinstance(outputs, dict) and outputs.get("signed_receipts") is False and
            outputs.get("hash_chain_is_signature") is False and
            outputs.get("automatic_gradient_admission") is False,
            "UNSIGNED_RECEIPT_MUST_NOT_GRANT_AUTHORITY")
    require(manifest["release_status"] == "HOLD_SOURCE_PROPOSAL"
            and manifest["citations_or_proofs_cannot_be_inferred_from_green_ci"] is True,
            "SOURCE_NOT_PRODUCTION_PASS")
    final = manifest["all_answered_gate"]
    require(isinstance(final, dict) and
            all(value is True for value in final.values()) and
            len(final) >= 9, "FULL_CLOSURE_MUST_REQUIRE_ALL_OBLIGATIONS")


def exact_toy_math() -> list[dict]:
    """Original concrete integer/rational witnesses, NOT ancient texts or physics."""
    cases = [
        ("EGYPT-HORUS", sum((Fraction(1, n) for n in (2, 4, 8, 16, 32, 64)),
                            Fraction(0)) == Fraction(63, 64)),
        ("EGYPT-2-5", Fraction(2, 5) == Fraction(1, 3) + Fraction(1, 15)),
        ("EGYPT-2-7", Fraction(2, 7) == Fraction(1, 4) + Fraction(1, 28)),
        ("EGYPT-2-13", Fraction(2, 13) ==
         Fraction(1, 8) + Fraction(1, 52) + Fraction(1, 104)),
        ("GREEK-3-4-5", 3*3 + 4*4 == 5*5),
        ("GREEK-5-12-13", 5*5 + 12*12 == 13*13),
        ("LUTAR-MAX-COUNTEREXAMPLE", math.isqrt(1*4) == 2 and max(1, 4) != 2),
    ]
    return [{"id": key, "verified_concrete_arithmetic": result,
             "historical_manuscript_proof": False,
             "independent_scientific_evaluation": False} for key, result in cases]


def five_role_rehearsal(toys: list[dict]) -> dict:
    """Structured local communications, not five real supercomputers or LLMs."""
    messages = []
    for row in toys:
        for role, state in (
            ("YACHAY", "ASSIGN_EXACT_SYNTHETIC_QUESTION"),
            ("KHIPU", "RATIONAL_OR_INTEGER_ORACLE"),
            ("LUTAR", "CORE_ARITHMETIC_ONLY_NO_NEW_AXIOM"),
            ("HATUN", "REFUSE_EXTERNAL_SCIENCE_CLAIM"),
            ("CODEX", "RECORD_NO_SIDE_EFFECTS"),
        ):
            messages.append({"role": role, "task": row["id"], "state": state,
                             "actual_model_agent_executed": False})
    return {"role_messages": len(messages), "distinct_roles": list(ROLE_IDS),
            "five_physical_computers_running": False,
            "gpu_training_started": False,
            "cloud_writes": 0}


def assess(manifest: dict, *, now: datetime) -> dict:
    """Truthful source-only assessment. No receipt input is trusted as a signer."""
    validate(manifest)
    observed = _utc(now)
    start = _utc(manifest["window"]["start_utc"])
    deadline = _utc(manifest["window"]["end_utc"])
    elapsed = max(0.0, (observed - start).total_seconds()/3600)
    toys = exact_toy_math()
    require(len(toys) == 7 and all(x["verified_concrete_arithmetic"] for x in toys),
            "NUMERICAL_ORACLE_MISMATCH")
    flow = five_role_rehearsal(toys)
    reasons = [
        "FIVE_INDEPENDENT_PHYSICAL_COMPUTE_NODES_NOT_VERIFIED",
        "UNADMITTED_GPU_BUDGET_AND_DATA_RIGHTS",
        "CODICIES_SOURCE_IDENTITY_UNRESOLVED",
        "FIVE_GRAND_CHALLENGES_REQUIRE_EXTERNAL_SCIENTIFIC_PROOF",
        "NO_INDEPENDENT_LEAN_PROOF_REPLAY_OR_SIGNED_OWNER_RECEIPT",
        "NO_INDEPENDENT_HOLDOUT_OR_PRODUCTION_TRAINING_RECEIPTS",
    ]
    if observed < deadline:
        reasons.insert(0, "54_HOUR_WINDOW_NOT_ELAPSED")
    return {
        "schema": REPORT_SCHEMA,
        "observed_at_utc": observed.isoformat(),
        "window_started_at_utc": start.isoformat(),
        "deadline_utc": deadline.isoformat(),
        "elapsed_hours_capped": round(min(elapsed, 54), 3),
        "logical_role_count": 5,
        "reviewed_public_source_pointers": len(manifest["source_registry"]),
        "first_party_toy_examples_verified": len(toys),
        "toy_examples": toys,
        "message_exchange": flow,
        "source_manifest_sha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "unresolved": reasons,
        "all_answers_verified": False,
        "provider_mutations": 0,
        "salad_replica_changes": 0,
        "massed_service_changes": 0,
        "model_weights_trained": False,
        "lean_replayed_independently": False,
        "qualified_five_node_mesh": False,
        "hash_receipt_is_signature": False,
        "release_status": "HOLD",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    args = parser.parse_args(argv)
    try:
        with args.manifest.open("rb") as source:
            raw = source.read(MAX_INPUT_BYTES + 1)
        result = assess(parse(raw), now=datetime.now(timezone.utc))
    except (OSError, Hold) as exc:
        reason = str(exc) if isinstance(exc, Hold) else type(exc).__name__
        print(json.dumps({"release_status": "HOLD", "reason": reason}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
