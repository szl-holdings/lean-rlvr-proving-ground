"""Source-pinned, mathematical negative-control tests for Lutar SFT candidates.

Numerical checks are deterministic fixture oracles, not machine-checked Lean
proofs, production claims, or independent model evaluation.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from curriculum import lutar_axioms as c


class LutarCurriculumTests(unittest.TestCase):
    def test_exact_geometric_mean_only_on_supported_domain(self):
        self.assertEqual(c.lambda2_exact((4, 9)), 6)
        self.assertEqual(c.lambda2_exact((0, 225)), 0)
        with self.assertRaises(ValueError):
            c.lambda2_exact((2, 3))
        with self.assertRaises(ValueError):
            c.lambda2_exact((-1, 4))
        with self.assertRaises(ValueError):
            c.lambda2_exact((4, True))

    def test_known_axiom_vectors_and_counterexamples(self):
        expectations = {
            "A1_MONOTONE": {"verdict": "YES", "axiom": "A1",
                            "lambda_x": 6, "lambda_y": 20},
            "A2_HOMOGENEOUS": {"verdict": "EQUAL", "axiom": "A2",
                               "left": 96, "right": 96},
            "A3_DIAGONAL": {"verdict": "EQUAL_TO_INPUT", "axiom": "A3",
                            "lambda": 2},
            "A4_BOUNDED": {"verdict": "BOUNDED", "axiom": "A4",
                           "lambda": 6, "maximum": 9},
            "A5_PERMUTATION": {"verdict": "INVARIANT", "axiom": "A5",
                               "left": 6, "right": 6},
            "UNIQUENESS_COUNTEREXAMPLE": {
                "verdict": "REFUTED", "claim": "UNCONDITIONAL_UNIQUENESS",
                "max_x": 4, "lambda_x": 2, "needs": "ADDITIONAL_ASSUMPTIONS",
            },
            "WEIGHTED_A5_COUNTEREXAMPLE": {
                "verdict": "NOT_INVARIANT",
                "axiom": "A5_REQUIRES_WEIGHT_PERMUTATION",
                "original": 24, "axes_swapped": 54,
            },
            "GATE_DENY": {
                "verdict": "HOLD", "failed_gate": c.GATES[2],
                "effective_lambda": 0, "production": "NOT_PROVEN",
            },
            "GATE_CONDITIONAL_ALLOW": {
                "verdict": "CONDITIONAL_ONLY", "effective_lambda": 6,
                "production": "NOT_PROVEN",
            },
            "ZERO_AXIS": {
                "verdict": "ZERO", "lambda": 0, "production": "NOT_PROVEN",
            },
        }
        self.assertEqual(set(expectations), set(c.FAMILIES))
        for family, expected in expectations.items():
            with self.subTest(family=family):
                prompt, actual, evidence = c.case(2, family)
                self.assertEqual(actual, expected)
                self.assertTrue(prompt.strip())
                self.assertEqual(evidence["n"], 2)

    def test_source_and_axiom_version_cannot_implicitly_roll(self):
        self.assertEqual(c.SOURCE["repository"], "szl-holdings/lutar-lean")
        self.assertEqual(c.SOURCE["commit"],
                         "c2ca813fca00ecf58bcc5f505f2aa4237fbf2481")
        for key in ("axioms_blob", "invariant_blob", "commit"):
            self.assertRegex(c.SOURCE[key], r"^[0-9a-f]{40}$")
        self.assertEqual(c.SOURCE["toolchain"], "leanprover/lean4:v4.35.0")
        self.assertNotIn("A5 implies uniqueness", c.SYSTEM)

    def test_distinct_training_inputs_and_holdout(self):
        train, held = c.records("train"), c.records("holdout")
        self.assertEqual(len(train), 160)
        self.assertEqual(len(held), 80)
        seen = set()
        for split, rows in (("train", train), ("holdout", held)):
            for row in rows:
                messages = row["messages"]
                self.assertEqual([m["role"] for m in messages],
                                 ["system", "user", "assistant"])
                key = c.canonical(messages[:2])
                self.assertNotIn(key, seen, "train/holdout leakage or duplicate input")
                seen.add(key)
                answer = json.loads(messages[2]["content"])
                self.assertIsInstance(answer, dict)
                self.assertTrue(answer["verdict"])
                md = row["metadata"]
                self.assertEqual(md["split"], split)
                self.assertEqual(md["source"], c.SOURCE)
                self.assertEqual(md["training_authority"], "NONE")
                self.assertEqual(md["proof_status"], "NOT_LEAN_VERIFIED_AS_DATASET")
        self.assertFalse(set(range(2, 18)).intersection(range(20, 28)))

    def test_exact_byte_reproducibility_and_manifest_digest(self):
        first, second = c.rendered(), c.rendered()
        self.assertEqual(first, second)
        manifest = json.loads(first["manifest.json"])
        self.assertEqual(manifest["review_state"], "REVIEW_REQUIRED")
        self.assertEqual(manifest["training_authority"], "NONE")
        self.assertFalse(manifest["lean_proof_of_dataset"])
        self.assertFalse(manifest["independent_holdout"])
        for split in ("train", "holdout"):
            name = split + ".jsonl"
            raw = first[name]
            self.assertEqual(manifest[split]["sha256"],
                             hashlib.sha256(raw).hexdigest())
            self.assertEqual(manifest[split]["rows"],
                             len(raw.splitlines()))

    def test_checked_in_artifacts_reproduce_exactly(self):
        for name, raw in c.rendered().items():
            with self.subTest(name=name):
                self.assertEqual((c.ROOT / name).read_bytes(), raw)

    def test_invalid_input_and_tamper_fail_closed(self):
        for bad in ("unknown", "", "Train"):
            with self.assertRaises(ValueError):
                c.records(bad)
        for bad in ("A6", "", "A1"):
            with self.assertRaises(ValueError):
                c.case(3, bad)
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            for name, raw in c.rendered().items():
                (folder / name).write_bytes(raw)
            (folder / "train.jsonl").write_bytes(b"mutated\n")
            with patch.object(c, "ROOT", folder), patch.object(
                    sys, "argv", ["lutar_axioms.py", "--check"]):
                self.assertEqual(c.main(), 1)

    def test_numeric_reward_is_exact_and_does_not_elevate_proof_status(self):
        row = c.records("train")[0]
        expected = row["messages"][2]["content"]
        self.assertEqual(c.exact_numeric_reward(row, expected), 1.0)
        self.assertEqual(c.exact_numeric_reward(row, "not json"), 0.0)
        self.assertEqual(c.exact_numeric_reward(row, "{}"), 0.0)
        self.assertEqual(c.exact_numeric_reward(row, '{"verdict":"PROOF_ACCEPTED"}'), 0.0)
        self.assertEqual(c.exact_numeric_reward(row, expected[:-1] + ',"verdict":"YES"}'), 0.0)
        self.assertEqual(c.exact_numeric_reward(row, '{"verdict":NaN}'), 0.0)
        self.assertEqual(c.exact_numeric_reward({}, expected), 0.0)
        bad = dict(row)
        bad["metadata"] = dict(row["metadata"], source=dict(c.SOURCE, commit="a" * 40))
        self.assertEqual(c.exact_numeric_reward(bad, expected), 0.0)

    def test_only_review_candidates_are_generated(self):
        for row in c.records("train") + c.records("holdout"):
            self.assertNotEqual(row["metadata"]["review_state"], "APPROVED")
            self.assertNotEqual(row["metadata"]["training_authority"], "ALLOW")
            self.assertNotIn("PROOF_ACCEPTED", row["messages"][2]["content"])


if __name__ == "__main__":
    unittest.main()
