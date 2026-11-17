"""Synthetic metadata controls; no benchmark statements or answers."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "hard_problems"))
import benchmark_exposure as gate


def fixture():
    return {"schema": gate.SCHEMA, "case_id": "synthetic-case", "source_sha256": "a" * 64,
            "prompt_sha256": "b" * 64, "answer_exposure": "NOT_OBSERVED",
            "training_overlap": "NOT_OBSERVED", "rights_review": "REVIEWED_FOR_EVALUATION",
            "reviewer_evidence_sha256": "c" * 64}


def run(row):
    return gate.review(json.dumps(row).encode())


class ExposureReviewTests(unittest.TestCase):
    def test_candidate_never_grants_authority(self):
        r = run(fixture())
        self.assertEqual(r["state"], "REVIEW_CANDIDATE_ONLY")
        for key in ("evidence_verified", "heldout_admitted", "training_admitted"):
            self.assertIs(r[key], False)
        self.assertEqual(r["mathematical_correctness"], "UNAVAILABLE")

    def test_answer_visible_is_not_heldout(self):
        row = fixture(); row["answer_exposure"] = "EXPOSED"
        self.assertIn("ANSWER_EXPOSED_NOT_HELD_OUT", run(row)["hold_reasons"])

    def test_training_overlap_holds(self):
        row = fixture(); row["training_overlap"] = "FOUND"
        self.assertEqual(run(row)["state"], "HOLD")

    def test_unknowns_hold(self):
        for field in ("answer_exposure", "training_overlap"):
            with self.subTest(field=field):
                row = fixture(); row[field] = "UNKNOWN"
                self.assertEqual(run(row)["state"], "HOLD")

    def test_rights_not_inferred(self):
        for value in ("NOT_REVIEWED", "PROHIBITED"):
            row = fixture(); row["rights_review"] = value
            self.assertEqual(run(row)["state"], "HOLD")

    def test_missing_evidence_holds(self):
        row = fixture(); row["reviewer_evidence_sha256"] = None
        self.assertEqual(run(row)["state"], "HOLD")

    def test_bad_digests_rejected(self):
        for field in ("source_sha256", "prompt_sha256", "reviewer_evidence_sha256"):
            for value in (True, "abc", "A" * 64, {}, []):
                with self.subTest(field=field, value=value):
                    row = fixture(); row[field] = value
                    with self.assertRaises(gate.index.Hold): run(row)

    def test_unrecognized_states_rejected(self):
        for field in ("answer_exposure", "training_overlap", "rights_review"):
            for value in (True, "PASS", [], None):
                row = fixture(); row[field] = value
                with self.assertRaises(gate.index.Hold): run(row)

    def test_unknown_fields_rejected(self):
        row = fixture(); row["heldout_admitted"] = True
        with self.assertRaises(gate.index.Hold): run(row)

    def test_missing_fields_rejected(self):
        row = fixture(); del row["answer_exposure"]
        with self.assertRaises(gate.index.Hold): run(row)

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(gate.index.Hold):
            gate.review(b'{"schema": 1,"schema": 2}')

    def test_cap_and_nonfinite_rejected(self):
        for raw in (b" " * 16385, b'{"x":NaN}', b'\xff'):
            with self.assertRaises(gate.index.Hold): gate.review(raw)

    def test_digest_binds_original_bytes(self):
        raw = json.dumps(fixture()).encode()
        self.assertEqual(gate.review(raw)["input_sha256"], gate.index.sha256(raw))


if __name__ == "__main__":
    unittest.main()
