"""Proof-ground CPU-only and no-false-green tests; no network, GPU or providers."""

from __future__ import annotations
import contextlib
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

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
                    with pg._single_writer(root):
                        pass
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

    def test_consistent_rebase_is_refused(self):
        shift = timedelta(hours=27)
        for fields in (
            ("started_at_utc", "expires_at_utc"),
            ("started_at_utc", "expires_at_utc", "bootstrapped_at_utc"),
        ):
            with self.subTest(fields=fields), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "new"
                pg.init_run(root, AT + timedelta(minutes=5))
                state_path = root / "state.json"
                state = pg.strict_load(state_path.read_bytes())
                for field in fields:
                    state[field] = (pg.utc(state[field]) + shift).isoformat()
                state_path.write_bytes(pg.packed(state))
                with self.assertRaisesRegex(pg.Hold, "SESSION_WINDOW_NOT_BOUND_TO_SOURCE"):
                    pg.tick(root, AT + shift + timedelta(minutes=10))
                self.assertEqual(list((root / "hours").glob("*.json")), [])

    def test_late_bootstrap_does_not_shift_slots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT + timedelta(minutes=50))
            with self.assertRaisesRegex(pg.Hold, "SKIPPED_OR_DUPLICATE_HOUR"):
                pg.tick(root, AT + timedelta(hours=1, minutes=20))
            self.assertEqual(list((root / "hours").glob("*.json")), [])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT + timedelta(minutes=50))
            self.assertEqual(pg.tick(root, AT + timedelta(minutes=55))["hour"], 0)
            self.assertEqual(
                pg.tick(root, AT + timedelta(hours=1, minutes=10))["hour"], 1
            )

    def test_tampered_middle_hour_breaks_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            pg.tick(root, AT + timedelta(minutes=2))
            pg.tick(root, AT + timedelta(hours=1, minutes=2))
            p = root / "hours" / "hour-00.json"
            p.write_bytes(p.read_bytes().replace(b"FOUNDATION", b"UNTRUSTED!"))
            with self.assertRaisesRegex(pg.Hold, "LEDGER_PARENT_OR_HOUR_MISMATCH"):
                pg.status(root, AT + timedelta(hours=1, minutes=30))
            with self.assertRaisesRegex(pg.Hold, "LEDGER_PARENT_OR_HOUR_MISMATCH"):
                pg.tick(root, AT + timedelta(hours=2, minutes=2))
            self.assertEqual(
                sorted(x.name for x in (root / "hours").glob("*.json")),
                ["hour-00.json", "hour-01.json"],
            )

    def test_slot_is_floor_of_source_hours(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            self.assertEqual(
                pg.tick(root, AT + timedelta(minutes=14, seconds=28))["hour"], 0
            )
            with self.assertRaisesRegex(pg.Hold, "SKIPPED_OR_DUPLICATE_HOUR"):
                pg.tick(root, AT + timedelta(minutes=44, seconds=28))
            self.assertEqual(
                pg.tick(root, AT + timedelta(hours=1, minutes=59, seconds=59))["hour"],
                1,
            )
            self.assertEqual(pg.tick(root, AT + timedelta(hours=2))["hour"], 2)

    def test_observed_times_are_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            seen = AT + timedelta(minutes=37, seconds=5)
            first = pg.init_run(root, seen)
            self.assertEqual(first["time"], seen.isoformat())
            self.assertEqual(first["bootstrap_observed_at_utc"], seen.isoformat())
            self.assertEqual(first["window_start"], AT.isoformat())
            self.assertEqual(pg.strict_load((root / "bootstrap.json").read_bytes()), first)
            ticked = AT + timedelta(minutes=41, seconds=9)
            pg.tick(root, ticked)
            record = pg.strict_load((root / "hours" / "hour-00.json").read_bytes())
            self.assertEqual(record["at_utc"], ticked.isoformat())
            st = pg.status(root, ticked)
            self.assertEqual(st["bootstrap_observed_at_utc"], seen.isoformat())
            self.assertEqual(st["source_window_start_utc"], AT.isoformat())
            self.assertEqual(
                st["elapsed_hours"], round((ticked - AT).total_seconds() / 3600, 2)
            )

    def test_cli_uses_actual_utc_clock(self):
        from proving54 import cli

        seen = AT + timedelta(minutes=7, seconds=3)

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return seen if tz is not None else seen.replace(tzinfo=None)

        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            cli, "datetime", Clock
        ):
            root = Path(temp) / "new"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cli.main(["init", "--run", str(root)])
            self.assertEqual(rc, 0, out.getvalue())
            self.assertEqual(
                json.loads(out.getvalue())["bootstrap_observed_at_utc"], seen.isoformat()
            )


@contextlib.contextmanager
def _failing_saves():
    """Every os.replace in the engine fails, as when a file holder never lets go."""
    with mock.patch(
        "proving54.engine.os.replace", side_effect=PermissionError("held")
    ), mock.patch("proving54.engine.time.sleep"):
        yield


class CrashSafetyTests(unittest.TestCase):
    def test_leftover_state_temp_is_quarantined_not_trusted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            (root / "state.json.temporary").write_bytes(b"left by a killed save")
            self.assertEqual(pg.tick(root, AT + timedelta(minutes=10))["hour"], 0)
            self.assertFalse((root / "state.json.temporary").exists())
            moved = [x.name for x in (root / "quarantine").glob("*")]
            self.assertEqual(len(moved), 1)
            self.assertTrue(moved[0].startswith("state.json.temporary."))
            st = pg.status(root, AT + timedelta(minutes=11))
            self.assertEqual(st["hours_recorded"], 1)
            self.assertEqual(st["quarantined_files"], moved)

    def test_transient_replace_failure_is_retried(self):
        real = os.replace
        calls = {"n": 0}

        def flaky(a, b):
            calls["n"] += 1
            if calls["n"] == 1:
                raise PermissionError("held by another process")
            return real(a, b)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            with mock.patch("proving54.engine.os.replace", side_effect=flaky), mock.patch(
                "proving54.engine.time.sleep"
            ):
                self.assertEqual(pg.tick(root, AT + timedelta(minutes=10))["hour"], 0)
            self.assertEqual(calls["n"], 2)
            self.assertEqual(pg.status(root, AT + timedelta(minutes=11))["hours_recorded"], 1)

    def test_failed_state_save_is_adopted_by_the_next_tick(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            pg.tick(root, AT + timedelta(minutes=5))
            with mock.patch(
                "proving54.engine.os.replace", side_effect=PermissionError("held")
            ), mock.patch("proving54.engine.time.sleep"):
                with self.assertRaisesRegex(pg.Hold, "HOUR_WRITTEN_STATE_NOT_COMMITTED"):
                    pg.tick(root, AT + timedelta(hours=1, minutes=5))
            self.assertTrue((root / "hours" / "hour-01.json").exists())
            self.assertFalse((root / "state.json.temporary").exists())
            st = pg.status(root, AT + timedelta(hours=1, minutes=6))
            self.assertEqual(st["hours_recorded"], 1)
            self.assertTrue(st["uncommitted_hour_pending"])
            # Same slot: hour 1 is adopted, then this call is a duplicate.
            with self.assertRaisesRegex(pg.Hold, "SKIPPED_OR_DUPLICATE_HOUR"):
                pg.tick(root, AT + timedelta(hours=1, minutes=35))
            st = pg.status(root, AT + timedelta(hours=1, minutes=36))
            self.assertEqual(st["hours_recorded"], 2)
            self.assertEqual(st["recovered_hours"], [1])
            self.assertFalse(st["uncommitted_hour_pending"])
            self.assertEqual(pg.tick(root, AT + timedelta(hours=2, minutes=5))["hour"], 2)
            self.assertEqual(pg.status(root, AT + timedelta(hours=2, minutes=6))["hours_recorded"], 3)

    def test_untrusted_uncommitted_hour_is_quarantined_and_the_slot_still_records(self):
        def forge(root, case):
            h0 = (root / "hours" / "hour-00.json").read_bytes()
            fake = dict(pg.strict_load(h0), hour=1, phase=pg.phase(1))
            fake["previous_sha256"] = pg.digest(h0)
            fake["at_utc"] = (AT + timedelta(hours=1, minutes=1)).isoformat()
            ep = dict(fake["episode"])
            if case == "not_json":
                return b"{not json"
            if case == "not_object":
                return b"[]\n"
            if case == "wrong_parent":
                fake["previous_sha256"] = "0" * 64
            elif case == "after_its_slot":
                fake["at_utc"] = (AT + timedelta(hours=2, minutes=1)).isoformat()
            elif case == "before_its_slot":
                fake["at_utc"] = (AT + timedelta(minutes=30)).isoformat()
            elif case == "wrong_schema":
                fake["schema"] = "szl.proving54-hour-record/v0"
            elif case == "wrong_hour":
                fake["hour"] = 2
            elif case == "wrong_phase":
                fake["phase"] = "SKILLS"
            elif case == "wrong_source":
                fake["source_registry_sha256"] = "f" * 64
            elif case == "weights_len4":
                ep["next_toy_cpu_policy_weights"] = [0.0] * 4
            elif case == "weights_out_of_range":
                ep["next_toy_cpu_policy_weights"] = [100.0] + [0.0] * 4
            elif case == "weights_bool":
                ep["next_toy_cpu_policy_weights"] = [True] + [0.0] * 4
            elif case == "weights_int":
                ep["next_toy_cpu_policy_weights"] = [0] + [0.0] * 4
            elif case == "missing_episode":
                del fake["episode"]
                return pg.packed(fake)
            elif case == "episode_not_object":
                fake["episode"] = []
                return pg.packed(fake)
            fake["episode"] = ep
            return pg.packed(fake)

        for case in ("wrong_parent", "after_its_slot", "before_its_slot", "not_json",
                     "not_object", "wrong_schema", "wrong_hour", "wrong_phase", "wrong_source",
                     "weights_len4", "weights_out_of_range", "weights_bool", "weights_int",
                     "missing_episode", "episode_not_object"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "new"
                pg.init_run(root, AT)
                pg.tick(root, AT + timedelta(minutes=5))
                raw = forge(root, case)
                (root / "hours" / "hour-01.json").write_bytes(raw)
                out = pg.tick(root, AT + timedelta(hours=1, minutes=5))
                self.assertEqual((out["hour"], out["uncommitted_hour"]), (1, "QUARANTINED"))
                kept = list((root / "quarantine").glob("hour-01.json.*"))
                self.assertEqual([x.read_bytes() for x in kept], [raw])
                self.assertNotEqual((root / "hours" / "hour-01.json").read_bytes(), raw)
                st = pg.status(root, AT + timedelta(hours=1, minutes=6))
                self.assertEqual((st["hours_recorded"], st["recovered_hours"]), (2, []))
                self.assertFalse(st["uncommitted_hour_pending"])

    def test_untrusted_hour_from_a_closed_slot_still_ends_the_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            pg.tick(root, AT + timedelta(minutes=5))
            (root / "hours" / "hour-01.json").write_bytes(b"{torn")
            with self.assertRaisesRegex(pg.Hold, "SKIPPED_OR_DUPLICATE_HOUR"):
                pg.tick(root, AT + timedelta(hours=2, minutes=5))
            self.assertEqual(len(list((root / "quarantine").glob("hour-01.json.*"))), 1)
            self.assertEqual(pg.status(root, AT + timedelta(hours=2, minutes=6))["hours_recorded"], 1)

    def test_noncanonical_hour_file_holds_without_moving_anything(self):
        for name in ("hour-01 - Copy.json", "hour-1.json", "hour-01 (1).json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "new"
                pg.init_run(root, AT)
                pg.tick(root, AT + timedelta(minutes=5))
                pg.tick(root, AT + timedelta(hours=1, minutes=5))
                committed = (root / "state.json").read_bytes()
                stray = root / "hours" / name
                stray.write_bytes((root / "hours" / "hour-01.json").read_bytes())
                before = sorted(x.name for x in (root / "hours").iterdir())
                with self.assertRaisesRegex(pg.Hold, "NONCANONICAL_HOUR_FILE"):
                    pg.tick(root, AT + timedelta(hours=2, minutes=5))
                with self.assertRaisesRegex(pg.Hold, "NONCANONICAL_HOUR_FILE"):
                    pg.status(root, AT + timedelta(hours=2, minutes=6))
                self.assertEqual(sorted(x.name for x in (root / "hours").iterdir()), before)
                self.assertEqual((root / "state.json").read_bytes(), committed)
                self.assertFalse((root / "quarantine").exists())

    def test_next_slot_adopts_then_records(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            pg.tick(root, AT + timedelta(minutes=5))
            with _failing_saves():
                with self.assertRaisesRegex(pg.Hold, "HOUR_WRITTEN_STATE_NOT_COMMITTED"):
                    pg.tick(root, AT + timedelta(hours=1, minutes=50))
            out = pg.tick(root, AT + timedelta(hours=2, minutes=20))
            self.assertEqual((out["hour"], out["uncommitted_hour"]), (2, "ADOPTED"))
            st = pg.status(root, AT + timedelta(hours=2, minutes=21))
            self.assertEqual((st["hours_recorded"], st["recovered_hours"]), (3, [1]))

    def test_adopted_state_matches_an_uninterrupted_commit(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            ra, rb = Path(a) / "new", Path(b) / "new"
            for r in (ra, rb):
                pg.init_run(r, AT)
                pg.tick(r, AT + timedelta(minutes=5))
            pg.tick(ra, AT + timedelta(hours=1, minutes=5))
            with _failing_saves(), self.assertRaisesRegex(pg.Hold, "HOUR_WRITTEN_STATE_NOT_COMMITTED"):
                pg.tick(rb, AT + timedelta(hours=1, minutes=5))
            with self.assertRaisesRegex(pg.Hold, "SKIPPED_OR_DUPLICATE_HOUR"):
                pg.tick(rb, AT + timedelta(hours=1, minutes=35))
            sa = pg.strict_load((ra / "state.json").read_bytes())
            sb = pg.strict_load((rb / "state.json").read_bytes())
            self.assertEqual(sb.pop("recovered_hours"), [1])
            self.assertEqual(sa, sb)
            for r in (ra, rb):
                pg.tick(r, AT + timedelta(hours=2, minutes=5))
            self.assertEqual(
                (ra / "hours" / "hour-02.json").read_bytes(),
                (rb / "hours" / "hour-02.json").read_bytes(),
            )

    def test_failed_adoption_commit_is_a_stable_hold(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            pg.tick(root, AT + timedelta(minutes=5))
            with _failing_saves(), self.assertRaises(pg.Hold):
                pg.tick(root, AT + timedelta(hours=1, minutes=5))
            committed = (root / "state.json").read_bytes()
            with _failing_saves(), self.assertRaisesRegex(pg.Hold, "ADOPTED_HOUR_NOT_COMMITTED"):
                pg.tick(root, AT + timedelta(hours=1, minutes=35))
            self.assertEqual((root / "state.json").read_bytes(), committed)
            self.assertFalse((root / "state.json.temporary").exists())
            self.assertTrue(pg.status(root, AT + timedelta(hours=1, minutes=36))["uncommitted_hour_pending"])
            self.assertEqual(pg.tick(root, AT + timedelta(hours=2, minutes=5))["uncommitted_hour"], "ADOPTED")

    def test_broken_committed_prefix_is_not_rolled_forward(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            pg.tick(root, AT + timedelta(minutes=5))
            with _failing_saves(), self.assertRaises(pg.Hold):
                pg.tick(root, AT + timedelta(hours=1, minutes=5))
            committed = (root / "state.json").read_bytes()
            h0 = root / "hours" / "hour-00.json"
            h0.write_bytes(h0.read_bytes().replace(b"FOUNDATION", b"UNTRUSTED!"))
            with self.assertRaisesRegex(
                pg.Hold, "TRUSTED_SESSION_HEAD_MISMATCH|LEDGER_PARENT_OR_HOUR_MISMATCH"
            ):
                pg.tick(root, AT + timedelta(hours=1, minutes=35))
            self.assertEqual((root / "state.json").read_bytes(), committed)
            self.assertTrue((root / "hours" / "hour-01.json").exists())
            self.assertFalse((root / "quarantine").exists())

    def test_two_extra_hour_files_hold_without_moving_anything(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            pg.tick(root, AT + timedelta(minutes=5))
            with _failing_saves(), self.assertRaises(pg.Hold):
                pg.tick(root, AT + timedelta(hours=1, minutes=5))
            (root / "hours" / "hour-02.json").write_bytes(b"{}\n")
            with self.assertRaisesRegex(pg.Hold, "HOUR_FILE_COUNT_MISMATCH"):
                pg.tick(root, AT + timedelta(hours=1, minutes=35))
            self.assertFalse((root / "quarantine").exists())

    def test_two_recoveries_are_both_listed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            pg.tick(root, AT + timedelta(minutes=5))
            for h in (1, 3):
                if h == 3:
                    pg.tick(root, AT + timedelta(hours=2, minutes=5))
                with _failing_saves(), self.assertRaises(pg.Hold):
                    pg.tick(root, AT + timedelta(hours=h, minutes=5))
                with self.assertRaisesRegex(pg.Hold, "SKIPPED_OR_DUPLICATE_HOUR"):
                    pg.tick(root, AT + timedelta(hours=h, minutes=35))
            st = pg.status(root, AT + timedelta(hours=3, minutes=40))
            self.assertEqual(st["recovered_hours"], [1, 3])

    def test_two_different_leftover_temps_are_both_kept(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            (root / "state.json.temporary").write_bytes(b"first killed save")
            pg.tick(root, AT + timedelta(minutes=5))
            (root / "state.json.temporary").write_bytes(b"second killed save")
            pg.tick(root, AT + timedelta(hours=1, minutes=5))
            kept = sorted(x.read_bytes() for x in (root / "quarantine").glob("state.json.temporary.*"))
            self.assertEqual(kept, [b"first killed save", b"second killed save"])

    def test_nothing_on_disk_changes_after_the_window(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            pg.tick(root, AT + timedelta(minutes=5))
            with _failing_saves(), self.assertRaises(pg.Hold):
                pg.tick(root, AT + timedelta(hours=1, minutes=5))
            (root / "state.json.temporary").write_bytes(b"left by a killed save")
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with self.assertRaisesRegex(pg.Hold, "OUTSIDE_54H_WINDOW"):
                pg.tick(root, AT + timedelta(hours=54, minutes=1))
            after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(after, before)
            st = pg.status(root, AT + timedelta(hours=54, minutes=2))
            self.assertEqual((st["hours_recorded"], st["uncommitted_hour_pending"]), (1, True))

    def test_any_state_save_oserror_maps_to_not_committed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            with mock.patch(
                "proving54.engine.os.replace", side_effect=OSError(28, "No space left on device")
            ), self.assertRaisesRegex(pg.Hold, "HOUR_WRITTEN_STATE_NOT_COMMITTED"):
                pg.tick(root, AT + timedelta(minutes=5))

    def test_atomic_write_never_deletes_a_temp_it_did_not_create(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            other = Path(temp) / "state.json.temporary"
            other.write_bytes(b"someone else")
            with self.assertRaisesRegex(pg.Hold, "ATOMIC_WRITE_CONFLICT"):
                pg._atomic_write(path, b"new")
            self.assertEqual(other.read_bytes(), b"someone else")

    def test_atomic_write_fsyncs_before_replace(self):
        seen = []
        real_fsync, real_replace = os.fsync, os.replace
        with tempfile.TemporaryDirectory() as temp, mock.patch(
            "proving54.engine.os.fsync", side_effect=lambda fd: (seen.append("fsync"), real_fsync(fd))
        ), mock.patch(
            "proving54.engine.os.replace",
            side_effect=lambda a, b: (seen.append("replace"), real_replace(a, b)),
        ):
            pg._atomic_write(Path(temp) / "state.json", b"x")
        self.assertEqual(seen, ["fsync", "replace"])

    def test_init_retries_a_held_staging_rename(self):
        real = os.replace
        calls = {"n": 0}

        def flaky(a, b):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise PermissionError("a scanner holds a file in staging")
            return real(a, b)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            with mock.patch("proving54.engine.os.replace", side_effect=flaky), mock.patch(
                "proving54.engine.time.sleep"
            ):
                pg.init_run(root, AT)
            self.assertEqual(calls["n"], 3)
            self.assertTrue((root / "state.json").is_file())
            self.assertEqual(
                [x.name for x in Path(temp).iterdir() if x.name.startswith(".szl-proving54-")], []
            )
            self.assertEqual(pg.tick(root, AT + timedelta(minutes=5))["hour"], 0)

    def test_init_that_cannot_rename_leaves_no_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            with mock.patch(
                "proving54.engine.os.replace", side_effect=PermissionError("held")
            ), mock.patch("proving54.engine.time.sleep"), self.assertRaises(PermissionError):
                pg.init_run(root, AT)
            self.assertEqual(list(Path(temp).iterdir()), [])
            pg.init_run(root, AT + timedelta(minutes=1))
            self.assertTrue((root / "state.json").is_file())

    def test_stale_lock_file_does_not_block_but_a_live_lock_does(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            pg.init_run(root, AT)
            (root / ".single-writer.lock").write_bytes(b"left by a killed worker")
            self.assertEqual(pg.tick(root, AT + timedelta(minutes=5))["hour"], 0)
            with pg._single_writer(root):
                with self.assertRaisesRegex(pg.Hold, "ANOTHER_WORKER_OWNS_THIS_RUN"):
                    pg.tick(root, AT + timedelta(hours=1, minutes=5))
            self.assertEqual(pg.tick(root, AT + timedelta(hours=1, minutes=6))["hour"], 1)


class OperatorRunnerTests(unittest.TestCase):
    RUNNER = Path(__file__).resolve().parents[1] / "proving54" / "operator" / "tick54.ps1"

    def test_runner_is_bounded_and_reads_the_window_from_the_manifest(self):
        raw = self.RUNNER.read_bytes()
        self.assertTrue(all(b < 128 for b in raw), "runner must be ASCII for PowerShell 5.1")
        self.assertNotIn(b"\r", raw)
        text = raw.decode("ascii")
        self.assertEqual(text.count("Invoke-Cli 'init'"), 1)
        self.assertEqual(text.count("Invoke-Cli 'tick'"), 1)
        self.assertIn("Get-Field $manifest 'window'", text)
        self.assertNotRegex(text, r"20\d\d-\d\d-\d\dT\d\d:\d\d")
        lowered = text.lower()
        for forbidden in ("remove-item", "stop-process", "set-itemproperty", "schtasks",
                          "register-scheduledtask", "set-executionpolicy", "invoke-webrequest",
                          "start-process", "restart-computer", "shutil", " del ", "rmdir"):
            self.assertNotIn(forbidden, lowered)

    def test_runner_retries_only_reasons_the_engine_can_emit(self):
        import re

        text = self.RUNNER.read_text(encoding="ascii")
        block = re.search(r"\$Retryable = @\(([^)]*)\)", text).group(1)
        retryable = set(re.findall(r"'([A-Za-z_]+)'", block))
        engine_src = (Path(pg.__file__)).read_text(encoding="utf-8")
        emitted = set(re.findall(r'(?:Hold\(|require\([^;]*?,\s*)"([A-Z0-9_]+)"', engine_src, re.S))
        os_errors = {c.__name__ for c in (PermissionError, OSError, FileExistsError,
                                          BlockingIOError, TimeoutError, InterruptedError)}
        self.assertTrue(retryable)
        self.assertEqual(retryable - emitted - os_errors, set())
        self.assertIn("ADOPTED_HOUR_NOT_COMMITTED", retryable)
        self.assertNotIn("UNCOMMITTED_HOUR_QUARANTINED", text)
        for never_retry in ("NONCANONICAL_HOUR_FILE", "RUN_COPY_SOURCE_DRIFT",
                            "TRUSTED_SESSION_HEAD_MISMATCH", "SKIPPED_OR_DUPLICATE_HOUR"):
            self.assertIn(never_retry, emitted)
            self.assertNotIn(never_retry, retryable)
        self.assertIn("'uncommitted_hour_pending'", text)


if __name__ == "__main__":
    unittest.main()
