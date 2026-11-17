"""Fail-closed source/statement preflight tests; no real Putnam text imported."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "research" / "hard_problems" / "putnam25_preflight.py"
CATALOG = ROOT / "research" / "hard_problems" / "catalog.v1.json"
sys.path.insert(0, str(SOURCE.parent))
spec = importlib.util.spec_from_file_location("putnam_preflight", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
index = module.index
NAME = "putnam_2025_a1"


def source_entry(raw: bytes, name: str = NAME):
    return {"id": name, "bytes": len(raw), "git_blob_sha1": module.git_blob_oid(raw),
            "evaluation_only": True, "training_authority": False,
            "truth_scope": "SOLVED_COMPETITION_PROBLEM",
            "path": "lean4/src/" + name + ".lean"}


def check(s: str, name: str = NAME):
    raw = s.encode("utf-8")
    return module.check_one(name, raw, source_entry(raw, name))


class PutnamSourceTests(unittest.TestCase):
    def test_source_ast_diagnostic_never_proves_math(self):
        row = check("theorem putnam_2025_a1 : 2 + 2 = 4 := by rfl\n")
        self.assertEqual(row["status"], "SOURCE_BYTES_ONLY")
        self.assertEqual(row["qualified_score"], "UNAVAILABLE")
        self.assertFalse(row["independent_proof_replayed"])
        self.assertFalse(row["student_attempt_supplied"])

    def test_true_target_flagged(self):
        row = check("theorem putnam_2025_a1 : True := by trivial\n")
        self.assertEqual(row["status"], "TRIVIAL_TARGET_HOLD")

    def test_sorry_detected_without_claiming_solution(self):
        row = check("theorem putnam_2025_a1 : Nat := by sorry\n")
        self.assertEqual(row["sorry_tokens_in_source"], 1)
        self.assertEqual(row["qualified_score"], "UNAVAILABLE")

    def test_mislabeled_theorem_rejected(self):
        with self.assertRaises(index.Hold):
            check("theorem putnam_2025_b1 : True := by trivial\n")

    def test_multiple_theorems_rejected(self):
        with self.assertRaises(index.Hold):
            check("theorem putnam_2025_a1 : True := by trivial\n"
                  "theorem second : True := by trivial\n")

    def test_no_theorem_rejected(self):
        with self.assertRaises(index.Hold):
            check("def helper := 3\n")

    def test_comment_spoofing_not_theorem(self):
        with self.assertRaises(index.Hold):
            check("/-- theorem putnam_2025_a1 : True := by sorry -/\n"
                  "-- theorem putnam_2025_a1 : True := by sorry\n")

    def test_multilevel_comments_and_string_literals_ignored(self):
        code = ('/- ignored /- theorem putnam_2025_a1 : True := sorry -/ -/\n'
                'def note := "sorry theorem fake"\n'
                'theorem putnam_2025_a1 : 1 = 1 := by rfl -- sorry\n')
        row = check(code)
        self.assertEqual(row["sorry_tokens_in_source"], 0)
        self.assertEqual(row["status"], "SOURCE_BYTES_ONLY")

    def test_auxiliary_solution_hole_counts(self):
        row = check("noncomputable abbrev putnam_2025_a1_solution : Nat := sorry\n"
                    "theorem putnam_2025_a1 : Nat := by sorry\n")
        self.assertEqual(row["solution_abbrev_declarations"], 1)
        self.assertEqual(row["sorry_tokens_in_source"], 2)

    def test_untrusted_axiom_marker_is_a_hold(self):
        row = check("axiom cheat : 3 = 3\ntheorem putnam_2025_a1 : 3 = 3 := by exact cheat\n")
        self.assertEqual(row["status"], "UNTRUSTED_AXIOM_OR_NATIVE_DECIDE_HOLD")
        self.assertEqual(row["unsafe_code_markers"], 1)

    def test_nested_comment_overflow_fails(self):
        text = "/-" * 65 + "-/" * 65
        with self.assertRaises(index.Hold):
            module.scrub_noncode(text)

    def test_unterminated_comment_fails(self):
        with self.assertRaises(index.Hold):
            module.scrub_noncode("/- unclosed")

    def test_unterminated_string_fails(self):
        with self.assertRaises(index.Hold):
            module.scrub_noncode('"not closed')

    def test_git_blob_hash_mismatch_fails(self):
        raw = b"theorem putnam_2025_a1 : True := by trivial\n"
        entry = source_entry(raw)
        entry["git_blob_sha1"] = "a" * 40
        with self.assertRaises(index.Hold):
            module.check_one(NAME, raw, entry)

    def test_changed_size_fails(self):
        raw = b"theorem putnam_2025_a1 : True := by trivial\n"
        entry = source_entry(raw)
        entry["bytes"] += 1
        with self.assertRaises(index.Hold):
            module.check_one(NAME, raw, entry)

    def test_crlf_not_accepted_as_canonical_source(self):
        raw = b"theorem putnam_2025_a1 : True := by trivial\r\n"
        with self.assertRaises(index.Hold):
            module.check_one(NAME, raw, source_entry(raw))

    def test_invalid_utf8_rejected(self):
        raw = b"theorem putnam_2025_a1 : \xff := by sorry\n"
        with self.assertRaises(index.Hold):
            module.check_one(NAME, raw, source_entry(raw))

    def test_training_authority_not_inferred(self):
        raw = b"theorem putnam_2025_a1 : True := by trivial\n"
        entry = source_entry(raw)
        entry["training_authority"] = True
        with self.assertRaises(index.Hold):
            module.check_one(NAME, raw, entry)

    def test_large_source_rejected(self):
        raw = b"x" * (module.MAX_LEAN_BYTES+1)
        with self.assertRaises(index.Hold):
            module.check_one(NAME, raw, source_entry(raw))

    def test_actual_catalog_has_all_twelve_case_ids(self):
        catalog = index.strict_json(CATALOG.read_bytes())
        result = index.validate(catalog)
        self.assertEqual(result["putnam_2025"], 12)
        observed = {r["id"] for r in catalog["entries"] if r["id"] in module.NAMES}
        self.assertEqual(observed, set(module.NAMES))

    def test_empty_directory_cannot_pass_as_twelve(self):
        catalog = index.strict_json(CATALOG.read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(index.Hold):
                module.evaluate(catalog, Path(temp))

    def test_extra_lean_file_detected(self):
        catalog = index.strict_json(CATALOG.read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "unexpected.lean").write_text("theorem x : True := by trivial\n")
            with self.assertRaises(index.Hold):
                module.evaluate(catalog, Path(temp))

    def test_no_untrusted_code_execution_or_cloud_control(self):
        text = SOURCE.read_text(encoding="utf-8")
        for unsafe in ("import subprocess", "import requests",
                       "import torch", "pickle.load(", "exec(", "eval(",
                       "HfApi(", "import referee", "chains.record(",
                       "api.create_", "trust_remote_code=True"):
            self.assertNotIn(unsafe, text)


if __name__ == "__main__":
    unittest.main()
