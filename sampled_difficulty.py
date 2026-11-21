"""Measure one completed sampling window; never execute Lean or select current gradients."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import referee
from grpo_adapter import MAX_BATCH_SIZE, PROBE_CLASSES


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _hex(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def _label(value):
    return isinstance(value, str) and 0 < len(value) <= 256 and bool(value.strip())


def _outcome(entry):
    """True/False is a provisional accepted/not-accepted observation; None is unknown."""
    verdict = entry.get("verdict")
    code = entry.get("build_exit_code")
    flags, evidence, axioms = (entry.get(k) for k in ("flags", "axiom_evidence", "axioms"))
    if ("build_exit_code" not in entry or not isinstance(flags, list)
            or not all(isinstance(f, str) for f in flags)
            or not isinstance(axioms, list) or not all(isinstance(a, str) for a in axioms)):
        return None
    if verdict == referee.V.PROOF_ACCEPTED:
        if (type(code) is int and code == 0 and not flags and evidence == "TARGET_BOUND_REPORT"
                and len(set(axioms)) == len(axioms) and set(axioms) <= referee.ALLOWED_AXIOMS):
            return True
    elif verdict == referee.V.BUILD_ERROR:
        # The runner does not distinguish all causes of exit 1. Count it as
        # not accepted, not as evidence the theorem or attempt is impossible.
        if type(code) is int and code == 1 and not flags and evidence == "NOT_OBSERVED" and not axioms:
            return False
    elif verdict in (referee.V.ABSTAIN, referee.V.SORRY_PRESENT, referee.V.NATIVE_DECIDE,
                     referee.V.AXIOM_SMUGGLED):
        lexical_flags = {
            referee.V.ABSTAIN: {"abstain-marker:" + m for m in referee.ABSTAIN_MARKERS},
            referee.V.SORRY_PRESENT: {"sorry"}, referee.V.NATIVE_DECIDE: {"native_decide"},
            referee.V.AXIOM_SMUGGLED: {"axiom-declaration"},
        }
        if (code is None and len(flags) == 1 and flags[0] in lexical_flags[verdict]
                and evidence == "NOT_OBSERVED" and not axioms):
            return False
        unexpected = sorted(set(axioms) - referee.ALLOWED_AXIOMS)
        if (verdict == referee.V.AXIOM_SMUGGLED and type(code) is int and code == 0
                and unexpected and flags == ["new-axioms:" + ",".join(unexpected)]
                and evidence == "TARGET_BOUND_REPORT"):
            return False
    return None


def assess_window(*, window_id, probe_id, statement, probe_class, split, mode, k, slots, entries):
    """Report whether to sample this training probe again, without writing or executing.

    The controller supplies the trusted context and a complete list of
    (sample_id, recorded_entry_sha256) pairs for THIS window. Inputs are
    in-memory JSON data, not an untrusted file parser. Source entries are
    ordinary chains.record results, in any order. IDs are not proof bodies.
    """
    if not (_label(window_id) and _label(probe_id) and isinstance(statement, str)
            and 0 < len(statement.encode("utf-8")) <= referee.MAX_INPUT_BYTES
            and referee._stmt_name(statement) and isinstance(probe_class, str)
            and probe_class in PROBE_CLASSES and split in ("train", "holdout", "test")
            and mode in ("fast", "lake") and type(k) is int and 2 <= k <= MAX_BATCH_SIZE):
        raise ValueError("invalid controller context or sample budget")

    statement_hash = _sha(statement.encode("utf-8"))
    fingerprint = None

    def report(state, reason, count=None):
        return {"window_id": window_id, "probe_id": probe_id, "mode": mode, "state": state,
                "statement_sha256": statement_hash, "slots_sha256": fingerprint,
                "split": split, "probe_class": probe_class, "reason": reason, "planned_k": k, "accepted": count,
                "observed_pass_rate": None if count is None else count / k,
                "recommend_next": state == "ELIGIBLE", "training_authority": "NONE"}

    if split != "train" or probe_class == "CONJECTURE":
        return report("EXCLUDED", "not_a_formalizable_training_window")
    if not all(isinstance(seq, (list, tuple)) and len(seq) == k for seq in (slots, entries)):
        return report("UNAVAILABLE", "incomplete_or_oversized_window")

    sample_ids, expected = set(), set()
    for slot in slots:
        if not isinstance(slot, (list, tuple)) or len(slot) != 2:
            return report("UNAVAILABLE", "invalid_slot")
        sid, digest = slot
        if not _label(sid) or not _hex(digest) or sid in sample_ids or digest in expected:
            return report("UNAVAILABLE", "invalid_or_repeated_slot")
        sample_ids.add(sid)
        expected.add(digest)

    fingerprint = _sha(json.dumps(sorted((sid, digest) for sid, digest in slots)).encode())
    bindings = {"probe_id": probe_id, "probe_class": probe_class, "mode": mode,
                "statement_sha256": statement_hash,
                "statement_declaration": referee._stmt_name(statement),
                "toolchain": referee._toolchain(),
                "referee_source_sha256": _sha(Path(referee.__file__).read_bytes()),
                "validation_level": referee.VALIDATION_LEVEL, "independent_checker": "NOT_RUN",
                "training_authority": "NONE"}
    accepted = 0
    for entry in entries:
        if not isinstance(entry, dict):
            return report("UNAVAILABLE", "invalid_observation")
        digest = entry.get("entry_sha256")
        if not _hex(digest) or digest not in expected:
            return report("UNAVAILABLE", "unknown_or_repeated_observation")
        # Match the existing chains.record wire bytes, not a new hash scheme.
        try:
            payload = {key: value for key, value in entry.items() if key != "entry_sha256"}
            computed = _sha(json.dumps(payload, sort_keys=True, allow_nan=False).encode())
        except (TypeError, ValueError, RecursionError):
            return report("UNAVAILABLE", "invalid_observation")
        if (digest != computed or any(entry.get(key) != value for key, value in bindings.items())
                or not all(_hex(entry.get(key)) for key in
                           ("attempt_sha256", "spliced_source_sha256", "build_output_sha256"))):
            return report("UNAVAILABLE", "observation_binding_mismatch")
        outcome = _outcome(entry)
        if outcome is None:
            return report("UNAVAILABLE", "unusable_referee_observation")
        accepted += int(outcome)
        expected.remove(digest)

    if 0 < accepted < k:
        return report("ELIGIBLE", "mixed_observed_outcomes", accepted)
    return report("INELIGIBLE", "all_accepted" if accepted == k else "none_accepted", accepted)
