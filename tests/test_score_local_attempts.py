"""Offline source-bound Putnam coverage counter tests. Synthetic rows only."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "research" / "hard_problems"
sys.path.insert(0, str(SRC))
spec = importlib.util.spec_from_file_location("local_selective_score", SRC / "score_local_attempts.py")
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)

MODEL = "fixture-model:untrained"
DIGEST = "b" * 64


def source_bytes(case: str) -> bytes:
    return ("import Mathlib\n"
            "theorem " + case + " : (2 : Nat) + 2 = 4 := by sorry\n").encode()


def entry_for(case: str, raw: bytes) -> dict:
    return {
        "id": case, "source": "putnambench",
        "path": "lean4/src/" + case + ".lean",
        "git_blob_sha1": score.source_api.git_blob_oid(raw),
        "bytes": len(raw),
        "truth_scope": "SOLVED_COMPETITION_PROBLEM",
        "evaluation_only": True, "training_authority": False,
    }


def mock_observation(catalog: dict, name: str, original: bytes,
                     answer: str = "-- ABSTAIN"):
    prompt, target_digest = score.inference.theorem_prompt(name, original)
    return {
        "schema": score.inference.SCHEMA,
        "origin": "REAL_LOCAL_INFERENCE_UNVERIFIED",
        "case_id": name,
        "source_repo": "trishullab/PutnamBench",
        "source_revision": score.catalog_api.PUTNAM_SHA,
        "catalog_sha256": score.catalog_api.sha256(score.canonical(catalog)),
        "source_blob_sha1": score.source_api.git_blob_oid(original),
        "source_sha256": score.catalog_api.sha256(original),
        "target_header_sha256": target_digest,
        "prompt_sha256": score.catalog_api.sha256(prompt.encode("utf-8")),
        "prompt": prompt,
        "model_alias": MODEL, "model_manifest_digest": DIGEST,
        "backend": "EXISTING_OLLAMA_LOOPBACK",
        "model_downloaded": False, "service_started": False,
        "options": dict(score.OPTS),
        "run_started_utc": datetime(2026, 11, 17, 10, 15, tzinfo=timezone.utc).isoformat(),
        "run_finished_utc": datetime(2026, 11, 17, 10, 16, tzinfo=timezone.utc).isoformat(),
        "response": answer,
        "response_sha256": score.catalog_api.sha256(answer.encode("utf-8")),
        "classification": score.inference.classify(answer),
        "metrics": {"prompt_eval_count": 120, "eval_count": 5, "total_duration": 34000},
        "independent_lean_checker": "NOT_RUN",
        "verified_proof": False,
        "statement_equivalence": "NOT_INDEPENDENTLY_REVIEWED",
        "benchmark_contamination_review": "NOT_RUN",
        "quality_score": "UNAVAILABLE",
        "model_retrained": False,
        "publication_authority": False,
        "training_authority": False,
        "provider_mutation_count": 0,
    }


class ScoreLocalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.sources = base / "source"
        self.receipts = base / "receipts"
        self.sources.mkdir()
        self.receipts.mkdir()
        contents = {name: source_bytes(name) for name in score.CASES}
        self.catalog = {"entries": [entry_for(name, raw)
                                    for name, raw in contents.items()]}
        self.paths = []
        for name, raw in contents.items():
            (self.sources / (name + ".lean")).write_bytes(raw)
            data = mock_observation(self.catalog, name, raw)
            path = self.receipts / (name + ".json")
            path.write_bytes(score.canonical(data))
            self.paths.append(path)

    def summary(self, paths=None, *, digest=DIGEST):
        with mock.patch.object(score.catalog_api, "validate") as validated:
            result = score.summarize(self.catalog, self.sources,
                                     list(self.paths if paths is None else paths),
                                     model=MODEL, digest=digest)
        validated.assert_called_once()
        return result

    def alter(self, case, **changes):
        path = self.receipts / (case + ".json")
        row = score.catalog_api.strict_json(path.read_bytes())
        row.update(changes)
        path.write_bytes(score.canonical(row))

    def test_all_six_abstentions_are_not_math_correctness(self):
        result = self.summary()
        self.assertEqual(result["observed_cases"], 6)
        self.assertEqual(result["abstentions"], 6)
        self.assertEqual(result["candidate_proof_text_count"], 0)
        self.assertEqual(result["answered_coverage"], 0.0)
        self.assertEqual(result["selective_risk"], "UNAVAILABLE")
        self.assertEqual(result["mathematical_correctness"], "UNAVAILABLE")
        self.assertFalse(result["calibrated_risk_coverage"])
        self.assertEqual(result["independently_validated_proofs"], 0)
        self.assertEqual(result["signature"], "UNSIGNED_SHA256_IS_INTEGRITY_NOT_AUTHORITY")

    def test_unverified_proof_text_is_not_mathematical_success(self):
        case = score.CASES[0]
        answer = "rfl"
        self.alter(case, response=answer,
                   response_sha256=score.catalog_api.sha256(answer.encode()),
                   classification="UNVERIFIED_PROOF_TEXT")
        result = self.summary()
        self.assertEqual(result["abstentions"], 5)
        self.assertEqual(result["candidate_proof_text_count"], 1)
        self.assertEqual(result["answered_coverage"], 1 / 6)
        self.assertEqual(result["selective_risk"], "UNAVAILABLE_UNGRADED")
        self.assertEqual(result["mathematical_correctness"], "UNAVAILABLE")
        self.assertEqual(result["independently_validated_proofs"], 0)

    def test_rejected_placeholder_is_not_answered_coverage(self):
        case = score.CASES[0]
        answer = "by sorry"
        self.alter(case, response=answer,
                   response_sha256=score.catalog_api.sha256(answer.encode()),
                   classification="REJECTED_UNSAFE_OR_PLACEHOLDER")
        result = self.summary()
        self.assertEqual(result["non_abstention_responses"], 1)
        self.assertEqual(result["candidate_proof_text_count"], 0)
        self.assertEqual(result["rejected_or_manual_count"], 1)
        self.assertEqual(result["answered_coverage"], 0.0)

    def test_missing_case_blocks_full_denominator(self):
        with self.assertRaises(score.catalog_api.Hold):
            self.summary(self.paths[:-1])

    def test_duplicate_file_blocks(self):
        with self.assertRaises(score.catalog_api.Hold):
            self.summary(self.paths[:-1] + [self.paths[0]])

    def test_different_file_same_case_blocks(self):
        spare = self.receipts / "duplicate.json"
        spare.write_bytes(self.paths[0].read_bytes())
        with self.assertRaises(score.catalog_api.Hold):
            self.summary(self.paths[:-1] + [spare])

    def test_forged_source_bytes_blocked(self):
        file = self.sources / (score.CASES[0] + ".lean")
        file.write_bytes(file.read_bytes() + b" ")
        with self.assertRaises(score.catalog_api.Hold):
            self.summary()

    def test_cannot_relabel_source_or_model(self):
        self.alter(score.CASES[0], model_alias="impersonated")
        with self.assertRaises(score.catalog_api.Hold):
            self.summary()

    def test_model_pin_cannot_be_mutable(self):
        with self.assertRaises(score.catalog_api.Hold):
            self.summary(digest="latest")

    def test_prompt_text_tamper_blocks_even_if_hash_updated(self):
        case = score.CASES[0]
        text = "theorem rewritten : True := by trivial"
        self.alter(case, prompt=text,
                   prompt_sha256=score.catalog_api.sha256(text.encode()))
        with self.assertRaises(score.catalog_api.Hold):
            self.summary()

    def test_response_hash_mismatch_blocks(self):
        self.alter(score.CASES[0], response="rfl")
        with self.assertRaises(score.catalog_api.Hold):
            self.summary()

    def test_classification_mismatch_blocks(self):
        self.alter(score.CASES[0], classification="UNVERIFIED_PROOF_TEXT")
        with self.assertRaises(score.catalog_api.Hold):
            self.summary()

    def test_private_source_checkpoint_cannot_claim_proof(self):
        self.alter(score.CASES[0], verified_proof=True)
        with self.assertRaises(score.catalog_api.Hold):
            self.summary()

    def test_training_authority_cannot_be_inferred(self):
        self.alter(score.CASES[0], training_authority=True)
        with self.assertRaises(score.catalog_api.Hold):
            self.summary()

    def test_runtime_changed_options_blocks(self):
        path = self.receipts / (score.CASES[0] + ".json")
        data = score.catalog_api.strict_json(path.read_bytes())
        data["options"]["temperature"] = 1
        path.write_bytes(score.canonical(data))
        with self.assertRaises(score.catalog_api.Hold):
            self.summary()

    def test_unnamed_backend_blocks(self):
        self.alter(score.CASES[0], backend="UNREVIEWED_PROVIDER")
        with self.assertRaises(score.catalog_api.Hold):
            self.summary()

    def test_local_network_interface_must_be_observed(self):
        self.alter(score.CASES[0], backend="EXISTING_ON_HOST_TAILSCALE_LISTENER",
                   on_host_interface_verified_externally=False)
        with self.assertRaises(score.catalog_api.Hold):
            self.summary()

    def test_timezone_naive_blocks(self):
        self.alter(score.CASES[0], run_started_utc="2026-11-17T10:00:00")
        with self.assertRaises(score.catalog_api.Hold):
            self.summary()

    def test_reversed_clock_blocks(self):
        self.alter(score.CASES[0], run_finished_utc="2026-11-17T00:00:00+00:00")
        with self.assertRaises(score.catalog_api.Hold):
            self.summary()

    def test_non_utf8_response_blocks(self):
        case = score.CASES[0]
        data = mock_observation(self.catalog, case,
                                (self.sources / (case + ".lean")).read_bytes())
        data["response"] = "\ud800"
        with self.assertRaises(score.catalog_api.Hold):
            score.check_row(self.catalog, (self.sources / (case + ".lean")).read_bytes(),
                            data, model=MODEL, digest=DIGEST)

    def test_symlinked_receipt_not_regular_when_supported(self):
        import os
        fake = self.receipts / "symlink.json"
        try:
            os.symlink(str(self.paths[0]), str(fake))
        except (OSError, NotImplementedError):
            self.skipTest("symlink unavailable on this runner")
        with self.assertRaises(score.catalog_api.Hold):
            score.read_regular(fake, score.MAX_RECEIPT)

    def test_no_network_calls_or_proof_execution_in_scorer(self):
        text = (SRC / "score_local_attempts.py").read_text(encoding="utf-8")
        for forbidden in ("http_json(", "local_json(", "urllib.request.urlopen(",
                          "subprocess.run(", "torch.load(", "pickle.load(",
                          "import referee", "chains.record(", "HfApi(", "trust_remote_code=True"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
