"""Proof-ground CPU-only and no-false-green tests; no network, GPU or providers."""

from __future__ import annotations
import contextlib
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

try:
    import resource
except ImportError:  # Windows
    resource = None

from proving54 import engine as pg

AT = pg.approved_source.START
REPO = Path(__file__).resolve().parents[1]
LOCK = ".single-writer.lock"
TEMP = "state.json.temporary"

# A second real process that takes the writer lock and then hangs at one
# point, so the parent can observe it alive and then kill it.
HANG_CHILD = r"""
import os, sys, time
from datetime import datetime
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from proving54 import engine
root, ready, when, point = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], sys.argv[5]
def hang(*args, **kwargs):
    ready.write_text(point)
    time.sleep(600)
if point == "episode":
    engine.episode = hang
else:
    os.replace = hang
engine.tick(root, datetime.fromisoformat(when))
"""

# A writer whose file writes past a byte limit fail with EFBIG, as a full
# disk would, while it holds the lock.
FSIZE_CHILD = r"""
import resource, signal, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from proving54 import engine
signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
limit = int(sys.argv[4])
resource.setrlimit(resource.RLIMIT_FSIZE, (limit, resource.getrlimit(resource.RLIMIT_FSIZE)[1]))
try:
    engine.tick(Path(sys.argv[2]), datetime.fromisoformat(sys.argv[3]))
except Exception as exc:
    print(str(exc) if isinstance(exc, engine.Hold) else type(exc).__name__)
    raise SystemExit(2)
print("RECORDED")
"""


def new_run(temp: str) -> Path:
    root = Path(temp) / "new"
    pg.init_run(root, AT)
    return root


def lose_state_commit(root: Path, when: datetime) -> None:
    """Record an hour, then put the prior state.json back: the receipt stays
    on disk and its commit is lost, as when a writer dies between the two."""
    before = (root / "state.json").read_bytes()
    pg.tick(root, when)
    (root / "state.json").write_bytes(before)


@contextlib.contextmanager
def replace_fails(times: int):
    """os.replace raises PermissionError `times` times, as on Windows when a
    reader holds state.json open without FILE_SHARE_DELETE."""
    real = os.replace
    calls = []

    def fake(src, dst, *args, **kwargs):
        calls.append(Path(dst).name)
        if len(calls) <= times:
            raise PermissionError(13, "simulated sharing violation", str(dst))
        return real(src, dst, *args, **kwargs)

    with mock.patch("os.replace", fake), mock.patch("time.sleep"):
        yield calls


def stop(child: subprocess.Popen) -> None:
    if child.returncode is None:
        child.kill()
        child.communicate(timeout=30)


def tick_after_writer_died(test: unittest.TestCase, root: Path, when: datetime) -> dict:
    """The OS drops a dead writer's lock when it is reaped. Windows documents
    that this can lag, so a few seconds are allowed; Linux needs none."""
    deadline = time.monotonic() + 5
    while True:
        try:
            return pg.tick(root, when)
        except pg.Hold as exc:
            if str(exc) != "ANOTHER_WORKER_OWNS_THIS_RUN" or time.monotonic() > deadline:
                test.fail(f"tick did not recover after the writer died: {exc}")
        time.sleep(0.05)


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


class CommitRecoveryTests(unittest.TestCase):
    """CLK-2: a failed state commit must never strand an hour receipt."""

    def test_leftover_state_temp_is_quarantined_not_deleted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = new_run(temp)
            pg.tick(root, AT + timedelta(minutes=12))
            junk = b'{"left by": "a writer killed mid-commit"'
            (root / TEMP).write_bytes(junk)
            try:
                r = pg.tick(root, AT + timedelta(hours=1, minutes=2))
            except pg.Hold as exc:
                self.fail(f"a leftover temp file cost the hour: {exc}")
            self.assertEqual(r["hour"], 1)
            self.assertFalse((root / TEMP).exists())
            moved = sorted((root / "quarantine").iterdir())
            self.assertEqual([p.read_bytes() for p in moved], [junk])
            self.assertEqual(r["quarantined"], [f"quarantine/{moved[0].name}"])
            st = pg.status(root, AT + timedelta(hours=1, minutes=3))
            self.assertEqual(st["hours_recorded"], 2)
            self.assertFalse(st["state_temp_file_present"])
            self.assertEqual(st["quarantined_files"], [moved[0].name])

    def test_unmovable_state_temp_holds_before_any_hour_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = new_run(temp)
            pg.tick(root, AT + timedelta(minutes=12))
            junk = b"held open by another process"
            (root / TEMP).write_bytes(junk)
            real = os.rename

            def rename(src, dst, *args, **kwargs):
                if Path(src).name == TEMP:
                    raise PermissionError(13, "simulated sharing violation", str(src))
                return real(src, dst, *args, **kwargs)

            with mock.patch("os.rename", rename), mock.patch("time.sleep"):
                with self.assertRaisesRegex(pg.Hold, "ATOMIC_WRITE_CONFLICT"):
                    pg.tick(root, AT + timedelta(hours=1, minutes=2))
            self.assertEqual(
                sorted(p.name for p in (root / "hours").iterdir()), ["hour-00.json"]
            )
            self.assertEqual((root / TEMP).read_bytes(), junk)
            st = pg.status(root, AT + timedelta(hours=1, minutes=3))
            self.assertEqual(st["hours_recorded"], 1)

    def test_transient_replace_permission_error_is_retried(self):
        with tempfile.TemporaryDirectory() as temp:
            root = new_run(temp)
            with replace_fails(2) as calls:
                try:
                    r = pg.tick(root, AT + timedelta(minutes=12))
                except PermissionError:
                    self.fail("a transient PermissionError from os.replace was not retried")
            self.assertEqual(r["hour"], 0)
            self.assertEqual(calls, ["state.json"] * 3)
            self.assertFalse((root / TEMP).exists())
            self.assertEqual(
                pg.status(root, AT + timedelta(minutes=13))["hours_recorded"], 1
            )

    def test_failed_replace_holds_with_a_distinct_reason(self):
        with tempfile.TemporaryDirectory() as temp:
            root = new_run(temp)
            before = (root / "state.json").read_bytes()
            with replace_fails(10**6) as calls:
                with self.assertRaises(Exception) as caught:
                    pg.tick(root, AT + timedelta(minutes=12))
            self.assertEqual(str(caught.exception), "HOUR_RECEIPT_WRITTEN_NOT_COMMITTED")
            self.assertIsInstance(caught.exception, pg.Hold)
            self.assertEqual(caught.exception.hour, 0)
            self.assertEqual(len(calls), len(pg.REPLACE_RETRY_DELAYS) + 1)
            self.assertEqual((root / "state.json").read_bytes(), before)
            self.assertTrue((root / "hours" / "hour-00.json").is_file())
            self.assertFalse((root / TEMP).exists())
            self.assertFalse((root / LOCK).exists())
            st = pg.status(root, AT + timedelta(minutes=13))
            self.assertEqual(st["hours_recorded"], 0)
            self.assertEqual(st["uncommitted_hour_pending_roll_forward"], 0)

    def test_cli_names_a_written_but_uncommitted_receipt(self):
        from proving54 import cli

        fixed = AT + timedelta(minutes=12)

        class FixedClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed

        with tempfile.TemporaryDirectory() as temp:
            root = new_run(temp)
            out = io.StringIO()
            with replace_fails(10**6), mock.patch.object(
                cli, "datetime", FixedClock
            ), contextlib.redirect_stdout(out):
                code = cli.main(["tick", "--run", str(root)])
            self.assertEqual(code, 2)
            self.assertEqual(
                json.loads(out.getvalue()),
                {
                    "result": "HOLD",
                    "reason": "HOUR_RECEIPT_WRITTEN_NOT_COMMITTED",
                    "uncommitted_hour": 0,
                },
            )

    def test_uncommitted_receipt_rolls_forward_without_skip_or_backfill(self):
        cases = (
            (timedelta(minutes=40), "UNCOMMITTED_HOUR_ADOPTED_REVIEW_ONLY", 1),
            (timedelta(hours=1, minutes=5), "HOUR_RECORDED_REVIEW_ONLY", 2),
            (timedelta(hours=2, minutes=5), "SKIPPED_OR_DUPLICATE_HOUR", 1),
        )
        for later, outcome, committed in cases:
            with self.subTest(retry=str(later)), tempfile.TemporaryDirectory() as temp:
                root = new_run(temp)
                lose_state_commit(root, AT + timedelta(minutes=12))
                receipt = (root / "hours" / "hour-00.json").read_bytes()
                if outcome == "SKIPPED_OR_DUPLICATE_HOUR":
                    with self.assertRaisesRegex(pg.Hold, outcome):
                        pg.tick(root, AT + later)
                else:
                    try:
                        r = pg.tick(root, AT + later)
                    except pg.Hold as exc:
                        self.fail(f"uncommitted receipt was not rolled forward: {exc}")
                    self.assertEqual(r["state"], outcome)
                    self.assertEqual(r["adopted_uncommitted_hour"], 0)
                st = pg.status(root, AT + later)
                self.assertEqual(st["hours_recorded"], committed)
                self.assertIsNone(st["uncommitted_hour_pending_roll_forward"])
                names = sorted(p.name for p in (root / "hours").iterdir())
                self.assertEqual(names, [f"hour-{h:02d}.json" for h in range(committed)])
                self.assertEqual((root / "hours" / "hour-00.json").read_bytes(), receipt)
                head = (root / "hours" / names[-1]).read_bytes()
                self.assertEqual(st["chain_head_sha256"], pg.digest(head))

    def test_unadoptable_receipt_is_quarantined_never_deleted(self):
        def edit(field, value):
            def change(raw):
                record = pg.strict_load(raw)
                record[field] = value
                return pg.packed(record)

            return change

        def edit_episode(raw):
            record = pg.strict_load(raw)
            record["episode"]["verified_toy_count"] += 1
            return pg.packed(record)

        cases = {
            "wrong hour": edit("hour", 1),
            "wrong parent": edit("previous_sha256", "0" * 64),
            "before its slot": edit("at_utc", (AT - timedelta(seconds=1)).isoformat()),
            "after its slot": edit("at_utc", (AT + timedelta(hours=1)).isoformat()),
            "other source": edit("source_registry_sha256", "f" * 64),
            "edited episode": edit_episode,
            "torn write": lambda raw: raw[: len(raw) // 2],
        }
        for name, change in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as temp:
                root = new_run(temp)
                lose_state_commit(root, AT + timedelta(minutes=12))
                path = root / "hours" / "hour-00.json"
                bad = change(path.read_bytes())
                path.write_bytes(bad)
                state = (root / "state.json").read_bytes()
                with self.assertRaisesRegex(pg.Hold, "UNCOMMITTED_HOUR_FILE_NOT_ADOPTABLE"):
                    pg.status(root, AT + timedelta(minutes=30))
                with self.assertRaisesRegex(pg.Hold, "UNCOMMITTED_HOUR_FILE_QUARANTINED"):
                    pg.tick(root, AT + timedelta(minutes=30))
                self.assertEqual(list((root / "hours").iterdir()), [])
                self.assertEqual(
                    [p.read_bytes() for p in (root / "quarantine").iterdir()], [bad]
                )
                self.assertEqual((root / "state.json").read_bytes(), state)
                # Hour 0 was never committed; its own slot may still record it.
                self.assertEqual(pg.tick(root, AT + timedelta(minutes=31))["hour"], 0)

    def test_roll_forward_never_chooses_between_files(self):
        # Boundary guard: only one correctly named next-hour file is adoptable.
        cases = {
            "two uncommitted receipts": ("hour-00.json", "hour-01.json"),
            "misnamed receipt": ("hour-05.json",),
        }
        for name, names in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as temp:
                root = new_run(temp)
                lose_state_commit(root, AT + timedelta(minutes=12))
                receipt = (root / "hours" / "hour-00.json").read_bytes()
                (root / "hours" / "hour-00.json").unlink()
                for n in names:
                    (root / "hours" / n).write_bytes(receipt)
                with self.assertRaisesRegex(pg.Hold, "HOUR_FILE_COUNT_MISMATCH"):
                    pg.tick(root, AT + timedelta(minutes=30))
                self.assertEqual(
                    sorted(p.name for p in (root / "hours").iterdir()), sorted(names)
                )
                self.assertFalse((root / "quarantine").exists())


class WriterLockTests(unittest.TestCase):
    """CLK-3: the single-writer lock must not outlive its writer."""

    def hung_writer(self, root: Path, when: datetime, point: str) -> subprocess.Popen:
        ready = root.parent / f"ready-{point}"
        child = subprocess.Popen(
            [sys.executable, "-I", "-B", "-c", HANG_CHILD, str(REPO), str(root),
             str(ready), when.isoformat(), point],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self.addCleanup(stop, child)
        deadline = time.monotonic() + 60
        while not ready.exists():
            if child.poll() is not None:
                err = child.communicate()[1].decode(errors="replace")
                self.fail(f"writer exited before its hang point: {err}")
            if time.monotonic() > deadline:
                self.fail("writer never reached its hang point")
            time.sleep(0.02)
        return child

    def test_leftover_lock_file_does_not_block_a_tick(self):
        with tempfile.TemporaryDirectory() as temp:
            root = new_run(temp)
            # What a writer killed while holding the old O_EXCL lock left behind.
            (root / LOCK).write_bytes((AT + timedelta(minutes=5)).isoformat().encode())
            try:
                r = pg.tick(root, AT + timedelta(minutes=12))
            except pg.Hold as exc:
                self.fail(f"a stale lock file blocked the run: {exc}")
            self.assertEqual(r["hour"], 0)
            self.assertFalse((root / LOCK).exists())

    def test_live_writer_excludes_and_killed_writer_releases(self):
        with tempfile.TemporaryDirectory() as temp:
            root = new_run(temp)
            when = AT + timedelta(minutes=12)
            child = self.hung_writer(root, when, "episode")
            with self.assertRaisesRegex(pg.Hold, "ANOTHER_WORKER_OWNS_THIS_RUN"):
                pg.tick(root, when + timedelta(seconds=1))
            self.assertTrue(pg.status(root, when)["single_writer_lock_file_present"])
            stop(child)
            r = tick_after_writer_died(self, root, when + timedelta(seconds=2))
            self.assertEqual(r["hour"], 0)
            st = pg.status(root, when + timedelta(seconds=3))
            self.assertEqual(st["hours_recorded"], 1)
            self.assertFalse(st["single_writer_lock_file_present"])

    def test_writer_killed_mid_commit_recovers_next_hour(self):
        with tempfile.TemporaryDirectory() as temp:
            root = new_run(temp)
            stop(self.hung_writer(root, AT + timedelta(minutes=12), "replace"))
            receipt = (root / "hours" / "hour-00.json").read_bytes()
            later = AT + timedelta(hours=1, minutes=2)
            st = pg.status(root, later)
            self.assertEqual(st["hours_recorded"], 0)
            self.assertEqual(st["uncommitted_hour_pending_roll_forward"], 0)
            self.assertTrue(st["state_temp_file_present"])
            self.assertTrue(st["single_writer_lock_file_present"])
            r = tick_after_writer_died(self, root, later)
            self.assertEqual((r["hour"], r["adopted_uncommitted_hour"]), (1, 0))
            self.assertEqual(len(r["quarantined"]), 1)
            st = pg.status(root, later)
            self.assertEqual(st["hours_recorded"], 2)
            self.assertFalse(st["state_temp_file_present"])
            self.assertFalse(st["single_writer_lock_file_present"])
            self.assertEqual((root / "hours" / "hour-00.json").read_bytes(), receipt)

    def test_lock_cleanup_failure_cannot_mask_a_committed_hour(self):
        with tempfile.TemporaryDirectory() as temp:
            root = new_run(temp)
            real = os.unlink

            def unlink(path, *args, **kwargs):
                if Path(path).name == LOCK:
                    raise PermissionError(13, "simulated sharing violation", str(path))
                return real(path, *args, **kwargs)

            with mock.patch("os.unlink", unlink):
                try:
                    r = pg.tick(root, AT + timedelta(minutes=12))
                except OSError as exc:
                    self.fail(f"lock cleanup turned a committed hour into a HOLD: {exc!r}")
            self.assertEqual(r["hour"], 0)
            self.assertFalse(r["single_writer_lock_file_removed"])
            st = pg.status(root, AT + timedelta(minutes=13))
            self.assertEqual(st["hours_recorded"], 1)
            self.assertTrue(st["single_writer_lock_file_present"])
            r = pg.tick(root, AT + timedelta(hours=1, minutes=2))
            self.assertEqual(r["hour"], 1)
            self.assertTrue(r["single_writer_lock_file_removed"])

    def tick_with_file_limit(self, root: Path, when: datetime, limit: int) -> str:
        done = subprocess.run(
            [sys.executable, "-I", "-B", "-c", FSIZE_CHILD, str(REPO), str(root),
             when.isoformat(), str(limit)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(done.returncode, 2, done.stderr)
        return done.stdout.strip()

    @unittest.skipUnless(
        resource is not None and hasattr(signal, "SIGXFSZ"),
        "needs POSIX file-size limits",
    )
    def test_write_failure_while_locked_strands_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = new_run(temp)
            before = (root / "state.json").read_bytes()
            when = AT + timedelta(minutes=12)
            # 8 bytes: the old lock-content write and the state stage both fail.
            self.assertEqual(
                self.tick_with_file_limit(root, when, 8), "STATE_COMMIT_NOT_STAGED"
            )
            self.assertEqual(list((root / "hours").iterdir()), [])
            self.assertEqual((root / "state.json").read_bytes(), before)
            self.assertFalse((root / TEMP).exists())
            self.assertFalse((root / LOCK).exists())
            self.assertEqual(pg.tick(root, when + timedelta(seconds=5))["hour"], 0)

    @unittest.skipUnless(
        resource is not None and hasattr(signal, "SIGXFSZ"),
        "needs POSIX file-size limits",
    )
    def test_torn_receipt_is_quarantined_then_the_hour_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = new_run(temp)
            before = (root / "state.json").read_bytes()
            when = AT + timedelta(minutes=12)
            # 4096 bytes: state.json (under 1 KiB) stages, the receipt tears.
            self.assertEqual(
                self.tick_with_file_limit(root, when, 4096), "HOUR_RECEIPT_WRITE_FAILED"
            )
            torn = (root / "hours" / "hour-00.json").read_bytes()
            self.assertEqual(len(torn), 4096)
            self.assertEqual((root / "state.json").read_bytes(), before)
            self.assertFalse((root / TEMP).exists())
            self.assertFalse((root / LOCK).exists())
            with self.assertRaisesRegex(pg.Hold, "UNCOMMITTED_HOUR_FILE_NOT_ADOPTABLE"):
                pg.status(root, when)
            with self.assertRaisesRegex(pg.Hold, "UNCOMMITTED_HOUR_FILE_QUARANTINED"):
                pg.tick(root, when + timedelta(seconds=5))
            self.assertEqual(
                [p.read_bytes() for p in (root / "quarantine").iterdir()], [torn]
            )
            self.assertEqual(pg.tick(root, when + timedelta(seconds=6))["hour"], 0)


if __name__ == "__main__":
    unittest.main()
