"""Synthetic sampling windows. Only fixture construction writes, inside a temp directory."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chains
import referee
from sampled_difficulty import assess_window


class SampledDifficultyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "chain" / "attempts.jsonl"
        redirect = patch.object(chains, "CHAINS_PATH", self.path)
        redirect.start()
        self.addCleanup(redirect.stop)
        self.context = dict(window_id="round-7", probe_id="example", statement="theorem target : True",
                            probe_class="SYMBOLIC", split="train", mode="fast")

    def row(self, attempt):
        # Exercise the actual referee shape, rewards, and existing ledger hash
        # format, without executing a compiler, model, or proposed Lean term.
        runner = (1, "type mismatch") if attempt == "bad" else (0, "'target' does not depend on any axioms")
        with patch.object(referee, "_run_fast", return_value=runner):
            receipt = referee.classify("example", self.context["statement"], attempt)
        return chains.record(receipt, "SYMBOLIC")

    def inputs(self, *attempts):
        rows = [self.row(attempt) for attempt in attempts]
        return dict(self.context, k=len(rows), entries=rows,
                    slots=[(f"sample-{i}", row["entry_sha256"]) for i, row in enumerate(rows)])

    def assert_unknown(self, args):
        report = assess_window(**args)
        self.assertEqual(report["state"], "UNAVAILABLE")
        self.assertFalse(report["recommend_next"])
        self.assertIsNone(report["accepted"])
        self.assertIsNone(report["observed_pass_rate"])

    def test_strict_mixed_window_not_shaped_reward(self):
        for attempts, count, eligible in [
            (("bad", "--ABSTAIN"), 0, False), (("trivial", "trivial"), 2, False),
            (("trivial", "--ABSTAIN"), 1, True), (("trivial", "bad", "trivial"), 2, True),
            (("sorry", "native_decide", "axiom bad : False", "trivial"), 1, True),
        ]:
            with self.subTest(attempts=attempts):
                args = self.inputs(*attempts)
                if "--ABSTAIN" in attempts:
                    self.assertEqual(args["entries"][attempts.index("--ABSTAIN")]["reward"], 0.1)
                report = assess_window(**args)
                self.assertEqual(report["accepted"], count)
                self.assertEqual(report["observed_pass_rate"], count / len(attempts))
                self.assertEqual(report["recommend_next"], eligible)
                self.assertEqual(report["state"], "ELIGIBLE" if eligible else "INELIGIBLE")
                self.assertEqual(report["training_authority"], "NONE")

    def test_conjectures_and_holdouts_have_no_observed_rate(self):
        args = self.inputs("trivial", "--ABSTAIN")
        for change in ({"split": "holdout"}, {"split": "test"}, {"probe_class": "CONJECTURE"}):
            report = assess_window(**(args | change))
            self.assertEqual(report["state"], "EXCLUDED")
            self.assertIsNone(report["accepted"])
            self.assertIsNone(report["observed_pass_rate"])
            self.assertFalse(report["recommend_next"])

    def test_sample_budget_validation_and_exact_window_size(self):
        args = self.inputs("trivial", "bad")
        for k in (0, 1, True, 2.0, 257):
            with self.subTest(k=k), self.assertRaises(ValueError):
                assess_window(**(args | {"k": k}))
        for k in (3, 256):
            self.assert_unknown(args | {"k": k})
        for name in ("slots", "entries"):
            self.assert_unknown(args | {name: args[name][:1]})
            self.assert_unknown(args | {name: args[name] * 2})
            self.assert_unknown(args | {name: iter(args[name])})

    def test_full_upper_boundary_counts_separately_recorded_identical_attempts(self):
        args = self.inputs(*(["trivial"] * 255 + ["bad"]))
        report = assess_window(**args)
        self.assertEqual((report["state"], report["accepted"], report["planned_k"]),
                         ("ELIGIBLE", 255, 256))

    def test_duplicate_or_unbound_observations_are_not_samples(self):
        args = self.inputs("trivial", "bad")
        first, second = args["slots"]
        for slots in ([first, first], [first, (first[0], second[1])], [first, (second[0], first[1])],
                      [first, (second[0], "a" * 64)], [first, ("", second[1])]):
            self.assert_unknown(args | {"slots": slots})
        self.assert_unknown(args | {"entries": [args["entries"][0]] * 2})
        self.assert_unknown(args | {"entries": [args["entries"][0], self.row("trivial")]})

    def modify(self, args, reroot=True, **fields):
        changed = copy.deepcopy(args)
        row = changed["entries"][0]
        row.update(fields)
        if reroot:  # model a content-intact but incompatible observation
            row.pop("entry_sha256")
            digest = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
            row["entry_sha256"] = digest
            changed["slots"][0] = ("sample-0", digest)
        return changed

    def test_exact_context_and_observation_content_are_required(self):
        args = self.inputs("trivial", "bad")
        for change in ({"mode": "lake"}, {"probe_class": "EMPIRICAL"}, {"probe_id": "other"},
                       {"statement_sha256": "b" * 64}, {"statement_declaration": "other"},
                       {"toolchain": "old"}, {"referee_source_sha256": "c" * 64},
                       {"attempt_sha256": None}, {"spliced_source_sha256": ""},
                       {"build_output_sha256": "absent"}, {"training_authority": "AUTHORIZED"},
                       {"validation_level": "NONE"}, {"independent_checker": "CHECKED"}):
            with self.subTest(change=change):
                self.assert_unknown(self.modify(args, **change))
        self.assert_unknown(self.modify(args, reroot=False, elapsed_s=999))
        self.assert_unknown(args | {"statement": "theorem target : False"})

    def test_known_infrastructure_gaps_do_not_become_negative_examples(self):
        args = self.inputs("trivial", "bad")
        for change in ({"build_exit_code": False}, {"axiom_evidence": "NOT_OBSERVED"},
                       {"axioms": ["sorryAx"]}, {"flags": ["unexpected"]},
                       {"verdict": "UNKNOWN"}, {"verdict": "BUILD_ERROR", "build_exit_code": -9},
                       {"verdict": "BUILD_ERROR", "build_exit_code": None, "flags": ["build-timeout"]},
                       {"verdict": "BUILD_ERROR", "build_exit_code": None,
                        "flags": ["build-infrastructure-unavailable"]},
                       {"verdict": "ABSTAIN", "build_exit_code": None,
                        "flags": ["build-timeout"], "axiom_evidence": "NOT_OBSERVED"},
                       {"verdict": "BUILD_ERROR", "build_exit_code": 0,
                        "flags": ["target-axiom-evidence-unavailable"]}):
            with self.subTest(change=change):
                self.assert_unknown(self.modify(args, **change))

    def test_reported_disallowed_axiom_is_observed_failure_not_missing_coverage(self):
        args = self.inputs("trivial", "trivial")
        changed = self.modify(args, verdict="AXIOM_SMUGGLED", flags=["new-axioms:Bad"],
                              axioms=["Bad", "propext"])
        self.assertEqual(assess_window(**changed)["accepted"], 1)

    def test_lake_window_is_separate_from_fast_and_remains_advisory(self):
        args = self.inputs("trivial", "bad")
        with patch.object(referee, "_run_lake", return_value=(0, "'target' does not depend on any axioms")):
            entry = chains.record(referee.classify("example", self.context["statement"], "trivial", mode="lake"),
                                  "SYMBOLIC")
        args["entries"][0] = entry
        args["slots"][0] = ("sample-0", entry["entry_sha256"])
        self.assert_unknown(args)  # mixed lanes
        args["mode"] = "lake"
        self.assert_unknown(args)
        rejected = chains.record(referee.classify("example", self.context["statement"], "sorry", mode="lake"),
                                 "SYMBOLIC")
        args["entries"][1] = rejected
        args["slots"][1] = ("sample-1", rejected["entry_sha256"])
        self.assertTrue(assess_window(**args)["recommend_next"])

    def test_report_is_order_independent_and_does_not_execute_or_record(self):
        args = self.inputs("trivial", "bad")
        saved, before = copy.deepcopy(args), self.path.read_bytes()
        with patch.object(chains, "record", side_effect=AssertionError), \
             patch.object(referee, "classify", side_effect=AssertionError):
            first = assess_window(**args)
            self.assertEqual(first, assess_window(**(args | {"entries": list(reversed(args["entries"]))})))
            self.assertEqual(first, assess_window(**(args | {"slots": list(reversed(args["slots"]))})))
        self.assertEqual(args, saved)
        self.assertEqual(self.path.read_bytes(), before)
