"""Corpus-v2 admission gate — the kernel-referee rule.

Only PROOF_ACCEPTED attempts checked in the 'lake' lane (project-context
kernel build) are admitted into corpus v2. Fast-lane (single-file) accepts
are recorded in the chain but are NOT admission-grade: the corpus grows
exclusively from lake-build-accepted proofs, per szl-forge PR #746.

Emit format: corpus-v2/<probe_id>.json + corpus-v2/manifest.json with a
total-content sha256, so the corpus revision is measurable.
"""
import hashlib
import json
from pathlib import Path

import chains

CORPUS_DIR = Path(__file__).resolve().parent / "corpus-v2"


def admit(chain_entries, statements):
    """chain_entries: parsed chain lines. statements: {probe_id: statement}."""
    accepted = [e for e in chain_entries
                if e["verdict"] == "PROOF_ACCEPTED" and e["mode"] == "lake"]
    CORPUS_DIR.mkdir(exist_ok=True)
    admitted = []
    for e in accepted:
        pid = e["probe_id"]
        doc = {
            "admission_rule": "kernel-referee/v1 (lake-build-accepted, sorry-free, allowed-axioms-only)",
            "probe_id": pid,
            "statement": statements.get(pid, ""),
            "proof_verbatim_ref": "chains/attempts.jsonl#" + e["entry_sha256"],
            "toolchain": e["toolchain"],
            "axioms": e["axioms"],
            "attempt_sha256": e["attempt_sha256"],
            "recorded_at": e["recorded_at"],
        }
        out = CORPUS_DIR / (pid + ".json")
        out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        admitted.append(doc)
    digest = hashlib.sha256("".join(
        json.dumps(a, sort_keys=True) for a in admitted).encode()).hexdigest()
    manifest = {
        "corpus": "lean-rlvr-proving-ground/corpus-v2",
        "admitted": len(admitted),
        "content_sha256": digest,
        "rule": "kernel-referee/v1",
    }
    (CORPUS_DIR / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return manifest
