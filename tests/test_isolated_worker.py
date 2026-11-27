#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Isolated Lean worker: fail-closed contract, sandbox properties, core and mathlib lanes.

Sandbox tests run when bwrap can start here. Set SZL_REQUIRE_SANDBOX=1 (CI does)
to turn a missing sandbox into a failure instead of a skip. The real-Mathlib test
runs only when SZL_MATHLIB_WORKSPACE points at a built workspace.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import isolated_worker as w  # noqa: E402
import referee  # noqa: E402

REQUIRE = os.environ.get("SZL_REQUIRE_SANDBOX") == "1"
HAVE_SANDBOX = w.probe_sandbox() and shutil.which("lean") is not None
if REQUIRE and not HAVE_SANDBOX:
    raise RuntimeError("SZL_REQUIRE_SANDBOX=1 but bwrap or lean is unavailable")
needs_sandbox = unittest.skipUnless(HAVE_SANDBOX, "bwrap sandbox or lean unavailable")

STMT = "theorem two_eq : 1 + 1 = 2"


class FailClosedTests(unittest.TestCase):
    def test_missing_bwrap_never_runs_unsandboxed(self):
        real_which, real_run, calls = shutil.which, subprocess.run, []

        def recording_run(argv, *a, **k):
            calls.append(list(map(str, argv)))
            return real_run(argv, *a, **k)

        with mock.patch.object(w.shutil, "which", side_effect=lambda n: None if n == "bwrap" else real_which(n)), \
             mock.patch.object(w.subprocess, "run", side_effect=recording_run):
            r = w.classify("two", STMT, "rfl")
        self.assertEqual(r["verdict"], referee.V.BUILD_ERROR)
        self.assertIn("isolated-worker-unavailable", r["flags"])
        self.assertEqual(r["training_authority"], "NONE")
        for argv in calls:  # only `lean --print-prefix` may run, never the attempt
            self.assertNotIn("Attempt.lean", " ".join(argv))

    def test_lexical_verdicts_match_referee(self):
        for attempt in ("sorry", "-- ABSTAIN open", "axiom bad : False\nexact bad.elim",
                        "native_decide", "--ABSTAIN no sorry here"):
            with self.subTest(attempt=attempt):
                ours = w.classify("p", STMT, attempt)
                theirs = referee.classify("p", STMT, attempt)
                self.assertEqual(ours["verdict"], theirs["verdict"])
                self.assertEqual(ours["flags"], theirs["flags"])

    def test_metaprograms_are_rejected_before_execution(self):
        for attempt in ("#eval IO.println \"x\"", "run_tac pure ()", "trace \"'two_eq' does not depend on any axioms\"\nrfl",
                        "set_option maxHeartbeats 0 in\nrfl", "exact (by elab_rules : tactic | `(tactic| rfl) => pure ())"):
            with self.subTest(attempt=attempt), mock.patch.object(w.subprocess, "run") as run:
                r = w.classify("p", STMT, attempt)
                self.assertEqual(r["verdict"], referee.V.BUILD_ERROR)
                self.assertEqual(r["flags"], ["metaprogram-forbidden"])
                run.assert_not_called()

    def test_lane_and_preamble_validation(self):
        with self.assertRaises(ValueError):
            w.classify("p", STMT, "rfl", lane="lake")
        with self.assertRaises(ValueError):
            w.classify("p", STMT, "rfl", lane="core", preamble="import Mathlib")
        with self.assertRaises(ValueError):
            w.classify("p", STMT, "rfl", lane="mathlib")
        for bad in ("", "import Foo", "import Mathlib\n#eval 1", "import Mathlib\nset_option x 1"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                w.classify("p", STMT, "rfl", lane="mathlib", preamble=bad, mathlib_workspace="/nonexistent")

    def test_unbuilt_mathlib_workspace_fails_closed(self):
        with tempfile.TemporaryDirectory() as ws:
            r = w.classify("p", STMT, "rfl", lane="mathlib", preamble="import Mathlib", mathlib_workspace=ws)
        self.assertEqual(r["verdict"], referee.V.BUILD_ERROR)
        self.assertIn("isolated-worker-unavailable", r["flags"])


@needs_sandbox
class SandboxPropertyTests(unittest.TestCase):
    def run_inside(self, program, *args):
        with tempfile.TemporaryDirectory() as work:
            argv = w.sandbox_argv(list(args), toolchain=w.toolchain_prefix(), workdir=Path(work), program=program)
            env = dict(os.environ, GITHUB_TOKEN="ghp_must_not_leak", HF_TOKEN="hf_must_not_leak")
            return subprocess.run(argv, capture_output=True, text=True, timeout=60, env=env)

    def test_environment_is_cleared(self):
        out = self.run_inside("/usr/bin/env").stdout
        names = sorted(line.split("=", 1)[0] for line in out.splitlines() if "=" in line)
        self.assertEqual(names, ["HOME", "LANG", "PATH", "PWD"])
        self.assertNotIn("must_not_leak", out)

    def test_no_network(self):
        code = ("import socket,sys\n"
                "try:\n socket.create_connection(('1.1.1.1', 443), timeout=3)\nexcept OSError:\n sys.exit(7)\n"
                "sys.exit(0)")
        self.assertEqual(self.run_inside("/usr/bin/python3", "-c", code).returncode, 7)

    def test_home_and_host_secrets_not_visible(self):
        home = os.path.expanduser("~")
        r = self.run_inside("/usr/bin/python3", "-c",
                            "import os,sys; sys.exit(0 if not os.path.exists(sys.argv[1]) and not os.path.exists('/etc/passwd') else 9)",
                            home)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_toolchain_is_read_only(self):
        r = self.run_inside("/usr/bin/python3", "-c",
                            "import sys\ntry:\n open('/toolchain/bin/pwn','w')\nexcept OSError:\n sys.exit(5)\nsys.exit(0)")
        self.assertEqual(r.returncode, 5)


@needs_sandbox
class CoreLaneTests(unittest.TestCase):
    def test_core_verdicts(self):
        self.assertEqual(w.classify("two", STMT, "rfl")["verdict"], referee.V.PROOF_ACCEPTED)
        bad = w.classify("two", STMT, "exact Nat.lt_irrefl")
        self.assertEqual(bad["verdict"], referee.V.BUILD_ERROR)
        acc = w.classify("two", STMT, "rfl")
        self.assertEqual(acc["isolation"], "BWRAP_ALL_NAMESPACES_CLEARENV")
        self.assertEqual(acc["mode"], "isolated-core")
        self.assertEqual(acc["axiom_evidence"], "TARGET_BOUND_REPORT")

    def test_classical_axioms_allowed(self):
        r = w.classify("em", "theorem em_ok (p : Prop) : p ∨ ¬p", "exact Classical.em p")
        self.assertEqual(r["verdict"], referee.V.PROOF_ACCEPTED)
        self.assertIn("Classical.choice", r["axioms"])


@needs_sandbox
class StubMathlibLaneTests(unittest.TestCase):
    """Exercise the read-only workspace mount and LEAN_PATH wiring with a tiny stub `Mathlib`."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        ws = Path(cls.tmp.name)
        lib = ws / ".lake/packages/mathlib/.lake/build/lib/lean"
        lib.mkdir(parents=True)
        src = ws / "Mathlib.lean"
        src.write_text("namespace SZLStub\ntheorem stub_ok : True := trivial\nend SZLStub\n", encoding="utf-8")
        lean = str(w.toolchain_prefix() / "bin" / "lean")  # same pinned toolchain as the worker
        subprocess.run([lean, "-o", str(lib / "Mathlib.olean"), str(src)], cwd=ws, check=True,
                       capture_output=True, timeout=120)
        cls.ws = ws

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_mathlib_import_resolves_read_only(self):
        r = w.classify("stub", "theorem uses_stub : True", "exact SZLStub.stub_ok", lane="mathlib",
                       preamble="import Mathlib", mathlib_workspace=self.ws)
        self.assertEqual(r["verdict"], referee.V.PROOF_ACCEPTED, r["build_tail"])
        self.assertEqual(r["mode"], "isolated-mathlib")

    def test_mathlib_lane_rejects_wrong_proof(self):
        r = w.classify("stub", "theorem uses_stub : False", "exact SZLStub.stub_ok", lane="mathlib",
                       preamble="import Mathlib", mathlib_workspace=self.ws)
        self.assertEqual(r["verdict"], referee.V.BUILD_ERROR)


@needs_sandbox
@unittest.skipUnless(os.environ.get("SZL_MATHLIB_WORKSPACE"), "SZL_MATHLIB_WORKSPACE not set")
class RealMathlibLaneTests(unittest.TestCase):
    def test_real_mathlib_proof_and_sorry(self):
        ws = os.environ["SZL_MATHLIB_WORKSPACE"]
        stmt = "theorem szl_sq_nonneg (x : ℝ) : 0 ≤ x ^ 2"
        ok = w.classify("sq", stmt, "positivity", lane="mathlib", preamble="import Mathlib", mathlib_workspace=ws)
        self.assertEqual(ok["verdict"], referee.V.PROOF_ACCEPTED, ok["build_tail"])
        bad = w.classify("sq", stmt, "rfl", lane="mathlib", preamble="import Mathlib", mathlib_workspace=ws)
        self.assertEqual(bad["verdict"], referee.V.BUILD_ERROR)
        sor = w.classify("sq", stmt, "sorry", lane="mathlib", preamble="import Mathlib", mathlib_workspace=ws)
        self.assertEqual(sor["verdict"], referee.V.SORRY_PRESENT)


if __name__ == "__main__":
    unittest.main()
