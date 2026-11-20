"""Synthetic observation fixtures test evidence handling, not proof correctness."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import admission
import referee

STATEMENT = "theorem target : 1 = 1"
GOOD = "'target' does not depend on any axioms\n"


def observation(output=GOOD, code=0, mode="lake"):
    with patch.object(referee, "_run_" + mode, return_value=(code, output)):
        return referee.classify("fixture", STATEMENT, "rfl", mode=mode)


def chained(receipt):
    value = dict(receipt, prev_sha256="GENESIS", recorded_at="2026-11-16T00:00:00Z")
    value["entry_sha256"] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    return value


class RefereeBoundaryTests(unittest.TestCase):
    def test_explicit_empty_target_report_is_observed(self):
        self.assertEqual(referee._parse_axioms(GOOD, "target"), set())

    def test_core_axioms(self):
        out = "'target' depends on axioms:\n [propext, Classical.choice, Quot.sound]"
        self.assertEqual(referee._parse_axioms(out, "target"), referee.ALLOWED_AXIOMS)

    def test_missing_unrelated_duplicate_and_malformed_reports_fail(self):
        for output in ("", "build completed", "'other' does not depend on any axioms",
                       GOOD + GOOD, "'target' depends on axioms: [propext,]",
                       "'target' depends on axioms: [propext, propext]"):
            with self.subTest(output=output):
                self.assertEqual(observation(output)["verdict"], referee.V.BUILD_ERROR)

    def test_target_not_first_report(self):
        out = "'other' does not depend on any axioms\n" + "'target' depends on axioms: [sorryAx]"
        self.assertEqual(observation(out)["verdict"], referee.V.AXIOM_SMUGGLED)

    def test_success_binds_statement_and_source(self):
        row = observation()
        self.assertEqual(row["verdict"], referee.V.PROOF_ACCEPTED)
        self.assertEqual(row["statement_sha256"], hashlib.sha256(STATEMENT.encode()).hexdigest())
        self.assertEqual(row["independent_checker"], "NOT_RUN")
        self.assertEqual(row["training_authority"], "NONE")
        self.assertEqual(row["axiom_evidence"], "TARGET_BOUND_REPORT")

    def test_nonzero_build_cannot_be_accepted(self):
        self.assertEqual(observation(code=1)["verdict"], referee.V.BUILD_ERROR)

    def test_timeout_and_missing_executable_are_receipted(self):
        for error in (subprocess.TimeoutExpired("lean", 1), FileNotFoundError("fixture")):
            with patch.object(referee, "_run_fast", side_effect=error):
                self.assertEqual(referee.classify("fixture", STATEMENT, "rfl")["verdict"], referee.V.BUILD_ERROR)

    def test_only_whole_response_abstain_marker_earns_abstention(self):
        for marker in referee.ABSTAIN_MARKERS:
            with self.subTest(marker=marker):
                row = referee.classify(
                    "fixture", STATEMENT, "  \n" + marker + "\n  ", mode="fast"
                )
                self.assertEqual(row["verdict"], referee.V.ABSTAIN)
                self.assertEqual(row["flags"], ["abstain-marker:" + marker])

    def test_embedded_abstain_marker_cannot_mask_rejected_attempts(self):
        cases = (
            ("sorry\n-- ABSTAIN", referee.V.SORRY_PRESENT),
            ("axiom injected : False\n--ABSTAIN", referee.V.AXIOM_SMUGGLED),
            ("native_decide\n-- ABSTAIN", referee.V.NATIVE_DECIDE),
        )
        for attempt, expected in cases:
            with self.subTest(attempt=attempt):
                row = referee.classify("fixture", STATEMENT, attempt, mode="fast")
                self.assertEqual(row["verdict"], expected)
                self.assertNotEqual(row["verdict"], referee.V.ABSTAIN)

    def test_abstain_comment_inside_attempt_does_not_skip_referee(self):
        with patch.object(referee, "_run_fast", return_value=(0, GOOD)) as compiler:
            row = referee.classify(
                "fixture", STATEMENT, "rfl\n-- ABSTAIN", mode="fast"
            )
        compiler.assert_called_once()
        self.assertEqual(row["verdict"], referee.V.PROOF_ACCEPTED)

    def test_bad_mode_cannot_hide_behind_abstention(self):
        with self.assertRaises(ValueError):
            referee.classify("fixture", STATEMENT, "--ABSTAIN", mode="invalid")

    def test_input_bound(self):
        with self.assertRaises(ValueError):
            referee.classify("fixture", STATEMENT, "x" * (referee.MAX_INPUT_BYTES + 1))

    def test_probe_identifier_cannot_close_header_comment(self):
        self.assertNotIn("-/\naxiom", referee.splice("-/\naxiom", STATEMENT, "rfl"))


class AdmissionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dest = Path(self.temp.name) / "generation"
        self.row = chained(observation())

    def stage(self, row=None, statements=None, head=None):
        row = self.row if row is None else row
        return admission.admit([row], statements or {"fixture": STATEMENT},
                               expected_chain_head=head or row["entry_sha256"], output_dir=self.dest)

    def test_valid_reference_has_no_training_or_independent_proof_authority(self):
        result = self.stage()
        self.assertEqual(result["admitted"], 1)
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        self.assertEqual(result["training_authority"], "NONE")
        self.assertFalse(result["proof_bodies_included"])
        self.assertTrue((self.dest / "manifest.json").is_file())

    def test_mutated_required_evidence_fails_before_writing(self):
        mutations = {
            "statement_sha256": "0" * 64, "statement_declaration": "wrong",
            "build_exit_code": True, "axiom_evidence": "NOT_OBSERVED",
            "axioms": ["sorryAx"], "flags": ["warning"],
            "toolchain": "leanprover/lean4:v0.0.0", "training_authority": "ALLOW",
            "independent_checker": "PASSED", "referee_source_sha256": "0" * 64,
            "attempt_sha256": "main", "validation_level": "SELF_ASSERTED",
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                mutated = dict(self.row, **{field: value})
                mutated.pop("entry_sha256")
                mutated = chained(mutated)
                with self.assertRaises(ValueError):
                    self.stage(mutated)
                self.assertFalse(self.dest.exists())

    def test_ledger_tampering_and_wrong_anchor_fail(self):
        row = dict(self.row, attempt_sha256="a" * 64)
        with self.assertRaises(ValueError):
            self.stage(row)
        with self.assertRaises(ValueError):
            self.stage(head="b" * 64)

    def test_missing_anchor_registry_or_empty_input_fail(self):
        for entries, registry, head in (([self.row], {"fixture": STATEMENT}, None),
                                       ([], {"fixture": STATEMENT}, self.row["entry_sha256"]),
                                       ([self.row], {}, self.row["entry_sha256"])):
            with self.assertRaises(ValueError):
                admission.admit(entries, registry, expected_chain_head=head, output_dir=self.dest)

    def test_unknown_and_changed_statements_fail(self):
        for registry in ({"other": STATEMENT}, {"fixture": "theorem target : True"}):
            with self.assertRaises(ValueError):
                self.stage(statements=registry)

    def test_fast_lane_never_enters_review_corpus(self):
        with self.assertRaises(ValueError):
            self.stage(chained(observation(mode="fast")))

    def test_legacy_unbound_receipts_fail(self):
        row = copy.deepcopy(self.row)
        row.pop("statement_sha256")
        row.pop("entry_sha256")
        with self.assertRaises(ValueError):
            self.stage(chained(row))

    def test_immutable_generation(self):
        self.stage()
        with self.assertRaises(FileExistsError):
            self.stage()

    def test_probe_identifiers_never_become_paths(self):
        row = chained(dict(observation(), probe_id="../outside"))
        self.stage(row, {"../outside": STATEMENT})
        self.assertFalse((Path(self.temp.name) / "outside.json").exists())
        self.assertEqual(len(list(self.dest.glob("*.json"))), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
