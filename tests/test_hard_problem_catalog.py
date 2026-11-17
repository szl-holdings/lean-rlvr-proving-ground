"""Exact-source challenge index and fail-closed observation regression tests."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "research" / "hard_problems" / "challenge_index.py"
CATALOG = ROOT / "research" / "hard_problems" / "catalog.v1.json"
spec = importlib.util.spec_from_file_location("challenge_index", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fake_tree(source, *, replace=None):
    if source == "putnam":
        rows = [{"path": "lean4/src/putnam_2025_a5.lean",
                 "type": "blob", "mode": "100644", "sha": "a" * 40, "size": 133}]
    else:
        rows = [{"path": "FormalConjectures/Arxiv/Example/Problem.lean",
                 "type": "blob", "mode": "100644", "sha": "b" * 40, "size": 211}]
    if replace is not None:
        rows = replace
    return module.encoded({"sha": ("c" if source == "putnam" else "d") * 40,
                           "truncated": False, "tree": rows})


def toy_extract(source, *, replace=None, truncated=False):
    """Unit-test only: pass explicit synthetic trust pins, never bypass production pins."""
    raw = fake_tree(source, replace=replace)
    if truncated:
        tree = module.strict_json(raw)
        tree["truncated"] = True
        raw = module.encoded(tree)
    config = module.SOURCES[0 if source == "putnam" else 1]
    toy_sha = ("c" if source == "putnam" else "d") * 40
    toy_config = (config[0], config[1], toy_sha, config[3],
                  config[4], config[5], module.sha256(raw))
    return module.extract_tree(raw, toy_config)


class ChallengeIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = module.strict_json(CATALOG.read_bytes())

    def test_full_source_catalog_and_2025(self):
        result = module.validate(self.catalog)
        self.assertEqual(result["putnambench_lean"], 672)
        self.assertEqual(result["formal_conjectures_statement_files"], 1861)
        self.assertEqual(result["total_file_pointers"], 2533)
        self.assertEqual(result["putnam_2025"], 12)
        self.assertEqual(result["model_training"], "NOT_RUN")

    def test_no_problem_text_or_training_admission(self):
        self.assertTrue(all(x["problem_text_included"] is False
                            and x["evaluation_only"] is True
                            and x["training_authority"] is False
                            for x in self.catalog["entries"]))
        self.assertFalse(any(self.catalog["holds"].values()))

    def test_inputs_only_metadata(self):
        p_source, p_rows = toy_extract("putnam")
        c_source, c_rows = toy_extract("conjecture")
        self.assertEqual(len(p_rows) + len(c_rows), 2)
        self.assertEqual(p_rows[0]["id"], "putnam_2025_a5")
        self.assertFalse(p_rows[0]["problem_text_included"])
        self.assertFalse(c_rows[0]["training_authority"])
        self.assertEqual(p_source["indexed_count"], 1)
        self.assertEqual(c_source["indexed_count"], 1)

    def test_source_blob_change_preserved_as_identity(self):
        x = copy.deepcopy(self.catalog)
        x["entries"][0]["git_blob_sha1"] = "a" * 40
        x["entries_sha256"] = module.sha256(module.encoded(x["entries"]))
        with self.assertRaises(module.Hold):
            module.validate(x)

    def test_digest_recomputation_not_a_signature(self):
        value = self.catalog
        self.assertEqual(value["entries_sha256"], module.EXPECTED_ENTRIES_SHA256)
        self.assertEqual(value["entries_sha256"], module.sha256(module.encoded(value["entries"])))
        self.assertEqual(value["status"], "INDEX_ONLY_NOT_A_MODEL_TEST")

    def test_bom_and_duplicate_member_rejected(self):
        with self.assertRaises(module.Hold):
            module.strict_json(b'{"x": 1,"x": 2}')
        with self.assertRaises(module.Hold):
            module.strict_json(b'{"x": NaN}')
        self.assertEqual(module.strict_json(b'\xef\xbb\xbf{"x":1}')["x"], 1)

    def test_truncated_tree_fails_before_indexing(self):
        with self.assertRaises(module.Hold):
            toy_extract("putnam", truncated=True)

    def test_bad_path_and_symlink_disallowed(self):
        for path, mode in (("lean4/src/putnam_2025_a5.lean", "120000"),
                           ("lean4/src/putnam_2025_a5.lean", "100755"),
                           ("lean4/src/putnam_2025_a5.lean", "040000")):
            item = {"path": path, "type": "blob", "mode": mode,
                    "sha": "a" * 40, "size": 10}
            with self.subTest(mode=mode), self.assertRaises(module.Hold):
                toy_extract("putnam", replace=[item])

    def test_duplicate_path_rejected(self):
        item = {"path": "lean4/src/putnam_2025_a5.lean", "type": "blob",
                "mode": "100644", "sha": "a" * 40, "size": 10}
        with self.assertRaises(module.Hold):
            toy_extract("putnam", replace=[item, item])

    def test_no_relabeling_conjecture_as_proven(self):
        catalog = copy.deepcopy(self.catalog)
        catalog["entries"][0]["truth_scope"] = "PROVED"
        catalog["entries_sha256"] = module.sha256(module.encoded(catalog["entries"]))
        with self.assertRaises(module.Hold):
            module.validate(catalog)

    def test_curated_open_board_no_auto_proof(self):
        cat = copy.deepcopy(self.catalog)
        cat["research_target_board"][0]["model_solved"] = True
        with self.assertRaises(module.Hold):
            module.validate(cat)

    def test_no_claim_all_open_or_rights_granted(self):
        cat = copy.deepcopy(self.catalog)
        cat["source_revisions"][0]["rights_clearance"] = "APPROVED"
        with self.assertRaises(module.Hold):
            module.validate(cat)

    def fixture(self, entries, origin="SYNTHETIC_CONTROL", revision=None):
        return module.encoded({"schema": "szl.proving-ground.challenge-submissions/v1",
                               "origin": origin, "model_revision": revision,
                               "submissions": entries})

    def test_abstention_does_not_prove_theorem(self):
        r = module.observe(self.catalog, self.fixture([
            {"id": "putnam_2025_a5", "action": "ABSTAIN", "text": ""}]))
        self.assertEqual(r["attempts"], 1)
        self.assertEqual(r["qualified_proofs"], 0)
        self.assertEqual(r["qualified_success_rate"], "UNAVAILABLE")
        self.assertEqual(r["observations"][0]["status"], "ABSTENTION_RECORDED_NOT_SOLUTION")

    def test_claimed_proof_not_verified_even_if_plausible(self):
        r = module.observe(self.catalog, self.fixture([
            {"id": "putnam_2025_b6", "action": "CLAIM_PROOF", "text": "by ring"}]))
        self.assertEqual(r["observations"][0]["status"], "UNVERIFIED_PROOF_CLAIM")
        self.assertEqual(r["independent_correctness"], "UNAVAILABLE")

    def test_lean_sorry_rejected_without_execution(self):
        r = module.observe(self.catalog, self.fixture([
            {"id": "putnam_2025_b6", "action": "CLAIM_PROOF", "text": "by sorry"}]))
        self.assertEqual(r["observations"][0]["status"], "REJECTED_PLACEHOLDER_NOT_PROOF")
        self.assertEqual(r["qualified_proofs"], 0)

    def test_unknown_and_duplicate_id_fail_before_receipts(self):
        for entries in (
            [{"id": "not-from-catalog", "action": "ABSTAIN", "text": ""}],
            [{"id": "putnam_2025_a5", "action": "ABSTAIN", "text": ""}] * 2,
        ):
            with self.assertRaises(module.Hold):
                module.observe(self.catalog, self.fixture(entries))

    def test_nonstring_action_rejected_without_crash(self):
        with self.assertRaises(module.Hold):
            module.observe(self.catalog, self.fixture([
                {"id": "putnam_2025_a5", "action": [], "text": ""}]))

    def test_abstain_with_embedded_proof_rejected(self):
        with self.assertRaises(module.Hold):
            module.observe(self.catalog, self.fixture([
                {"id": "putnam_2025_a5", "action": "ABSTAIN", "text": "some answer"}]))

    def test_model_runs_require_pinned_revision(self):
        with self.assertRaises(module.Hold):
            module.observe(self.catalog, self.fixture([
                {"id": "putnam_2025_a5", "action": "ABSTAIN", "text": ""}],
                origin="MODEL_RESPONSES_UNVERIFIED", revision="main"))

    def test_source_division_and_honest_denominators(self):
        fc = next(x["id"] for x in self.catalog["entries"]
                  if x["source"] == "formal_conjectures")
        r = module.observe(self.catalog, self.fixture([
            {"id": "putnam_2025_a5", "action": "ABSTAIN", "text": ""},
            {"id": fc, "action": "CLAIM_PROOF", "text": "by simp"}]))
        self.assertEqual(r["attempts"], 2)
        self.assertEqual(r["source_counts"]["formal_conjectures"], 1)
        self.assertEqual(r["source_counts"]["putnambench"], 1)
        self.assertEqual(r["reported_abstention_fraction"], .5)
        self.assertEqual(r["qualified_success_rate"], "UNAVAILABLE")

    def test_no_execution_or_secondary_controller(self):
        text = MODULE.read_text(encoding="utf-8")
        for forbidden in ("torch.load(", "pickle.load(", "eval(", "exec(",
                          "trust_remote_code=True", "HfApi(", "subprocess.",
                          "requests.", "requests.get(", "import referee",
                          "chains.record("):
            self.assertNotIn(forbidden, text)

    def test_single_writer_output_refuses_overwrite(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "one.json"
            module.write_once(path, b'{"status":"TEST"}\n')
            with self.assertRaises(module.Hold):
                module.write_once(path, b'{"status":"CONFLICT"}\n')
            self.assertEqual(path.read_bytes(), b'{"status":"TEST"}\n')


if __name__ == "__main__":
    unittest.main()
