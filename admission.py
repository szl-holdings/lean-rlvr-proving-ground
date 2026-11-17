"""Content-bound review-corpus staging, not automatic training authorization.

Only target-reported lake-lane observations matching a trusted statement
registry can be staged. The caller must supply the expected ledger head from
its trusted control plane. An unsigned hash chain is integrity evidence, not
proof of publisher identity or resistance to fabricated Lean output.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

import referee

CORPUS_DIR = Path(__file__).resolve().parent / "corpus-v2"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_ENTRIES = 100_000


def _digest(value):
    # Preserve the existing chains.record canonicalization exactly.
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _valid_digest(value):
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def admit(chain_entries, statements, *, expected_chain_head=None, output_dir=None):
    """Validate the entire input before writing a new immutable review generation.

    ``statements`` is a controller-owned {probe_id: exact_statement} mapping.
    Legacy receipts lacking target/source evidence fail closed and must be
    replayed; they are not silently upgraded. This function stages references,
    not proof bodies, model weights, runtime permissions or a training launch.
    """
    if not isinstance(chain_entries, list) or not 1 <= len(chain_entries) <= _MAX_ENTRIES:
        raise ValueError("a bounded, nonempty ledger is required")
    if not isinstance(statements, dict) or not statements:
        raise ValueError("a trusted statement registry is required")
    if any(not isinstance(k, str) or not k or not isinstance(v, str) or not v.strip()
           for k, v in statements.items()):
        raise ValueError("statement registry entries must be nonempty strings")
    if not _valid_digest(expected_chain_head):
        raise ValueError("an exact controller-supplied ledger head is required")
    previous = "GENESIS"
    seen = set()
    admitted = []
    for entry in chain_entries:
        if not isinstance(entry, dict):
            raise ValueError("ledger entry must be an object")
        entry_hash = entry.get("entry_sha256")
        if not _valid_digest(entry_hash) or entry_hash in seen:
            raise ValueError("ledger identity is invalid or duplicated")
        payload = {key: value for key, value in entry.items() if key != "entry_sha256"}
        if entry.get("prev_sha256") != previous or _digest(payload) != entry_hash:
            raise ValueError("ledger integrity mismatch")
        previous = entry_hash
        seen.add(entry_hash)
        if entry.get("verdict") != "PROOF_ACCEPTED":
            continue
        if entry.get("mode") != "lake":
            continue  # Fast lane is never admission-grade.
        pid = entry.get("probe_id")
        if not isinstance(pid, str) or pid not in statements:
            raise ValueError("accepted probe is not in the trusted registry")
        statement = statements[pid]
        expected_statement = hashlib.sha256(statement.encode("utf-8")).hexdigest()
        axioms = entry.get("axioms")
        if (entry.get("statement_sha256") != expected_statement
                or entry.get("statement_declaration") != referee._stmt_name(statement)
                or not entry.get("statement_declaration")
                or entry.get("toolchain") != referee._toolchain()
                or entry.get("validation_level") != referee.VALIDATION_LEVEL
                or entry.get("axiom_evidence") != "TARGET_BOUND_REPORT"
                or entry.get("independent_checker") != "NOT_RUN"
                or entry.get("training_authority") != "NONE"
                or type(entry.get("build_exit_code")) is not int
                or entry["build_exit_code"] != 0
                or entry.get("flags") != []
                or not isinstance(axioms, list)
                or any(not isinstance(a, str) for a in axioms)
                or len(set(axioms)) != len(axioms)
                or not set(axioms) <= referee.ALLOWED_AXIOMS):
            raise ValueError("accepted observation lacks the required bound evidence")
        for field in ("attempt_sha256", "spliced_source_sha256", "build_output_sha256",
                      "referee_source_sha256"):
            if not _valid_digest(entry.get(field)):
                raise ValueError("accepted observation has an invalid digest")
        if entry["referee_source_sha256"] != hashlib.sha256(Path(referee.__file__).read_bytes()).hexdigest():
            raise ValueError("referee identity differs; replay is required")
        if not isinstance(entry.get("recorded_at"), str) or not entry["recorded_at"]:
            raise ValueError("observation timestamp is missing")
        admitted.append({
            "schema": "szl.lutar.proof-review-reference/v1",
            "probe_id": pid, "statement": statement,
            "statement_sha256": expected_statement,
            "statement_declaration": entry["statement_declaration"],
            "attempt_receipt_ref": "chains/attempts.jsonl#" + entry_hash,
            "attempt_sha256": entry["attempt_sha256"],
            "spliced_source_sha256": entry["spliced_source_sha256"],
            "build_output_sha256": entry["build_output_sha256"],
            "referee_source_sha256": entry["referee_source_sha256"],
            "toolchain": entry["toolchain"], "axioms": axioms,
            "validation_level": referee.VALIDATION_LEVEL,
            "independent_checker": "NOT_RUN", "state": "REVIEW_REQUIRED",
            "training_authority": "NONE", "recorded_at": entry["recorded_at"],
            "entry_sha256": entry_hash,
        })
    if previous != expected_chain_head:
        raise ValueError("ledger does not match the controller-owned head")
    if not admitted:
        raise ValueError("no eligible lake-lane observations; coverage is unavailable")
    admitted.sort(key=lambda row: row["entry_sha256"])
    generation = _digest(admitted)
    manifest = {
        "schema": "szl.lutar.proof-review-corpus/v1",
        "corpus": "lean-rlvr-proving-ground/corpus-v2", "admitted": len(admitted),
        "content_sha256": generation, "ledger_head_sha256": previous,
        "statement_registry_sha256": _digest(statements),
        "rule": "kernel-referee/v2-target-bound-review",
        "state": "REVIEW_REQUIRED", "training_authority": "NONE",
        "independent_checker": "NOT_RUN", "proof_bodies_included": False,
    }
    destination = Path(output_dir) if output_dir is not None else CORPUS_DIR / generation
    if destination.exists():
        raise FileExistsError("review generation already exists; history is immutable")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Stage in a sibling directory; a manifest is published only with all rows.
    with tempfile.TemporaryDirectory(prefix=".lutar-review-", dir=destination.parent) as temp:
        staging = Path(temp) / "generation"
        staging.mkdir()
        for row in admitted:
            (staging / (row["entry_sha256"] + ".json")).write_text(
                json.dumps(row, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        (staging / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.rename(staging, destination)
    return manifest
