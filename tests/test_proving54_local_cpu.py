"""Proof-ground CPU-only and no-false-green tests; no network, GPU or providers."""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest

from proving54 import engine as pg

AT = pg.approved_source.START


class RoleAndOracleTests(unittest.TestCase):
    def test_pinned_source_and_no_training_authority(self):
        x = pg.registry()
        self.assertEqual(x["hours"], 54)
        self.assertEqual(tuple(r["id"] for r in x["roles"]), pg.ROLE_NAMES)
        self.assertEqual(len(x["sources"]), 11)
        self.assertEqual(x["training_authority"], "NONE")
        self.assertFalse(x["five_physical_supercomputers_proved"])
        self.assertTrue(all(r["rights"] == "REVIEW_REQUIRED" for r in x["sources"]))

    def test_three_phase_windows(self):
        self.assertEqual(
            [pg.phase(n) for n in (0, 23, 24, 47, 48, 53)],
            ["FOUNDATION", "FOUNDATION", "SKILLS", "SKILLS", "PROOF", "PROOF"],
        )
        with self.assertRaises(pg.Hold):
            pg.phase(54)
        with self.assertRaises(pg.Hold):
            pg.phase(True)

    def test_egyptian_rationals(self):
        self.assertEqual(
            sum((Fraction(1, k) for k in (2, 4, 8, 16, 32, 64)), Fraction(0)),
            Fraction(63, 64),
        )
        self.assertEqual(Fraction(1, 3) + Fraction(1, 15), Fraction(2, 5))
        self.assertEqual(Fraction(1, 4) + Fraction(1, 28), Fraction(2, 7))
        self.assertEqual(
            Fraction(1, 8) + Fraction(1, 52) + Fraction(1, 104), Fraction(2, 13)
        )
        for k in (
            "EGYPT-HORUS",
            "EGYPT-RHIND-2-5",
            "EGYPT-RHIND-2-7",
            "EGYPT-RHIND-2-13",
        ):
            self.assertEqual(pg.oracle(k)[0], "VERIFIED_SYNTHETIC")

    def test_greek_lutar_counterexamples(self):
        self.assertEqual(3 * 3 + 4 * 4, 25)
        self.assertEqual(5 * 5 + 12 * 12, 169)
        for k in (
            "GREEK-345",
            "GREEK-51213",
            "GREEK-EQUALITY",
            "LUTAR-PERMUTATION",
            "LUTAR-COUNTEREXAMPLE",
        ):
            self.assertEqual(pg.oracle(k)[0], "VERIFIED_SYNTHETIC")
        self.assertNotEqual(
            pg.oracle("LUTAR-COUNTEREXAMPLE")[1]["lambda"],
            pg.oracle("LUTAR-COUNTEREXAMPLE")[1]["alternative_max"],
        )

    def test_no_false_scientific_solution(self):
        for k in (
            "SCIENCE-CUPRATE",
            "SCIENCE-INTERFACE",
            "SCIENCE-QUANTUM",
            "SCIENCE-DRIVEN",
            "SCIENCE-HEAT",
        ):
            self.assertEqual(pg.oracle(k)[0], "OPEN_EVIDENCE_REQUIRED")
        self.assertEqual(pg.oracle("CODICIES-UNRESOLVED")[0], "UNOBSERVED_SOURCE")
        self.assertEqual(pg.oracle("HATUN-UNSIGNED")[0], "EXPECTED_SAFETY_HOLD")
        self.assertEqual(pg.oracle("LAKE-NO-HEAD")[0], "EXPECTED_SAFETY_HOLD")

    def test_toy_sgd_not_llm_training(self):
        new, report = pg.micro_train([0.0] * 5, pg.phase_tasks(0))
        self.assertEqual(len(new), 5)
        self.assertNotEqual(new, [0.0] * 5)
        self.assertFalse(report["existing_llm_weights_touched"])
        self.assertEqual(report["third_party_benchmark_performance"], "UNOBSERVED")
        for bad in ([1.0] * 4, ["x"] * 5, [float("nan")] * 5, [True] * 5):
            with self.subTest(bad=bad), self.assertRaises(pg.Hold):
                pg.micro_train(bad, pg.phase_tasks(0))

    def test_all_five_roles_receipted_per_case(self):
        for h in (0, 24, 48):
            report = pg.episode(h, [0.0] * 5)
            self.assertEqual(
                len(report["role_messages"]), 5 * len(report["task_results"])
            )
            self.assertEqual(
                set(x["role"] for x in report["role_messages"]), set(pg.ROLE_NAMES)
            )
            self.assertFalse(report["experimental_release_authorized"])
            self.assertFalse(report["all_questions_answered"])
            self.assertFalse(report["gpu_training_started"])

    def test_malformed_input_clock_source_hold(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b"x" * 100001):
            with self.assertRaises(pg.Hold):
                pg.strict_load(raw)
        for val in ("bad-date", "2026-11-18T05:05:32", None):
            with self.assertRaises(pg.Hold):
                pg.utc(val)
        with self.assertRaises(pg.Hold):
            pg.oracle("INVENTED_PROOF")


class TimeboxTests(unittest.TestCase):
    def test_no_duplicate_or_skipped_hour(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            first = pg.init_run(root, AT)
            self.assertEqual(first["state"], "LOCAL_REVIEW_WINDOW_STARTED")
            r = pg.tick(root, AT + timedelta(minutes=12))
            self.assertEqual(r["hour"], 0)
            self.assertEqual(r["role_messages"], 5 * r["verified_toy_count"])
            with self.assertRaisesRegex(pg.Hold, "SKIPPED_OR_DUPLICATE_HOUR"):
                pg.tick(root, AT + timedelta(minutes=20))
            with self.assertRaisesRegex(pg.Hold, "SKIPPED_OR_DUPLICATE_HOUR"):
                pg.tick(root, AT + timedelta(hours=2))
            r2 = pg.tick(root, AT + timedelta(hours=1, minutes=2))
            self.assertEqual(r2["hour"], 1)
            self.assertEqual(
                pg.status(root, AT + timedelta(hours=1))["hours_recorded"], 2
            )

    def test_exact_chain_tamper_and_missing_gates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            pg.tick(root, AT + timedelta(minutes=2))
            p = root / "hours" / "hour-00.json"
            blob = p.read_bytes().replace(b"FOUNDATION", b"UNTRUSTED!")
            p.write_bytes(blob)
            with self.assertRaisesRegex(pg.Hold, "TRUSTED_SESSION_HEAD_MISMATCH"):
                pg.tick(root, AT + timedelta(hours=1))
            self.assertEqual(len(list((root / "hours").glob("*.json"))), 1)

    def test_all_54_cpu_hours_still_cannot_claim_science(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            for h in range(54):
                pg.tick(root, AT + timedelta(hours=h, seconds=3))
            result = pg.status(root, AT + timedelta(hours=54))
            self.assertEqual(result["hours_recorded"], 54)
            self.assertEqual(result["release_status"], "HOLD")
            self.assertFalse(result["all_required_fully_answered"])
            self.assertFalse(result["physical_supercomputers_verified"])
            self.assertFalse(result["model_training_executed"])
            self.assertTrue(result["five_roles_messaged_per_case"])
            self.assertIn("CODICIES-UNRESOLVED", result["known_unresolved_tasks"])

    def test_existing_private_run_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "old"
            root.mkdir()
            sentinel = root / "important.txt"
            sentinel.write_text("never delete")
            with self.assertRaises(pg.Hold):
                pg.init_run(root, AT)
            self.assertEqual(sentinel.read_text(), "never delete")

    def test_init_only_during_source_hour_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            late = Path(temp) / "late"
            for when in (
                AT - timedelta(seconds=1),
                AT + timedelta(hours=1),
                AT + timedelta(hours=27),
            ):
                with self.subTest(when=when.isoformat()):
                    with self.assertRaisesRegex(
                        pg.Hold, "INITIALIZATION_OUTSIDE_SOURCE_HOUR_ZERO"
                    ):
                        pg.init_run(late, when)
                    self.assertFalse(late.exists())
            edge = Path(temp) / "edge"
            first = pg.init_run(edge, AT + timedelta(minutes=59, seconds=59))
            self.assertEqual(first["window_start"], AT.isoformat())
            self.assertEqual(
                first["window_end"], (AT + timedelta(hours=54)).isoformat()
            )

    def test_session_clock_cannot_be_rebased(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT + timedelta(minutes=5))
            state_path = root / "state.json"
            original = state_path.read_bytes()
            later = AT + timedelta(hours=27)
            cases = (
                ("started_at_utc", later.isoformat(),
                 "SESSION_WINDOW_NOT_BOUND_TO_SOURCE"),
                ("expires_at_utc", (later + timedelta(hours=54)).isoformat(),
                 "SESSION_WINDOW_NOT_BOUND_TO_SOURCE"),
                ("bootstrapped_at_utc", later.isoformat(),
                 "SESSION_BOOTSTRAP_NOT_IN_FIRST_CLOCK_HOUR"),
                ("bootstrapped_at_utc", None, "TIMESTAMP_TYPE"),
            )
            for field, value, reason in cases:
                with self.subTest(field=field, value=value):
                    state = pg.strict_load(original)
                    state[field] = value
                    state_path.write_bytes(pg.packed(state))
                    with self.assertRaisesRegex(pg.Hold, reason):
                        pg.tick(root, later + timedelta(minutes=10))
                    self.assertEqual(list((root / "hours").glob("*.json")), [])
                    self.assertFalse((root / ".single-writer.lock").exists())
            state_path.write_bytes(original)
            self.assertEqual(pg.tick(root, AT + timedelta(minutes=10))["hour"], 0)

    def test_no_tick_outside_source_window(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            for when in (AT - timedelta(seconds=1), AT + timedelta(hours=54)):
                with self.subTest(when=when.isoformat()):
                    with self.assertRaisesRegex(pg.Hold, "OUTSIDE_54H_WINDOW"):
                        pg.tick(root, when)
            self.assertEqual(list((root / "hours").glob("*.json")), [])

    def test_one_missed_hour_ends_the_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            pg.tick(root, AT + timedelta(minutes=20))
            for h in range(2, 6):
                with self.subTest(hour=h):
                    with self.assertRaisesRegex(pg.Hold, "SKIPPED_OR_DUPLICATE_HOUR"):
                        pg.tick(root, AT + timedelta(hours=h, minutes=20))
            self.assertEqual(
                pg.status(root, AT + timedelta(hours=6))["hours_recorded"], 1
            )


if __name__ == "__main__":
    unittest.main()
