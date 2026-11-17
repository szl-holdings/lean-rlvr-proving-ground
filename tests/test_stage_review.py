"""Pinned-file migration controls; synthetic receipts are not proof evidence."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import stage_review
from test_proof_boundary import STATEMENT, chained, observation


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class StageReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.row = chained(observation())
        self.ledger = self.root / "ledger.jsonl"
        self.registry = self.root / "registry.json"
        self.output = self.root / "generation"
        self.ledger.write_bytes((json.dumps(self.row) + "\n").encode())
        self.registry.write_bytes(json.dumps({"fixture": STATEMENT}).encode())

    def args(self):
        return ["--ledger", str(self.ledger), "--ledger-sha256", sha(self.ledger.read_bytes()),
                "--registry", str(self.registry), "--registry-sha256", sha(self.registry.read_bytes()),
                "--expected-chain-head", self.row["entry_sha256"], "--output", str(self.output)]

    def invoke(self, args=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = stage_review.main(self.args() if args is None else args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_valid_migration_is_review_only(self):
        code, out, _ = self.invoke()
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["training_authority"], "NONE")
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        self.assertFalse(result["proof_bodies_included"])

    def test_wrong_source_digest_fails_before_writing(self):
        args = self.args()
        args[args.index("--ledger-sha256") + 1] = "0" * 64
        self.assertEqual(self.invoke(args)[0], 2)
        self.assertFalse(self.output.exists())

    def test_changed_registry_bytes_fail_before_writing(self):
        args = self.args()
        self.registry.write_bytes(b"{}")
        self.assertEqual(self.invoke(args)[0], 2)
        self.assertFalse(self.output.exists())

    def test_wrong_external_anchor_is_not_recomputed(self):
        args = self.args()
        args[args.index("--expected-chain-head") + 1] = "0" * 64
        self.assertEqual(self.invoke(args)[0], 2)
        self.assertFalse(self.output.exists())

    def test_duplicate_registry_and_nonfinite_numbers_fail(self):
        for raw in (b'{"fixture":"one","fixture":"two"}', b'{"x":NaN}', b'{"x":1e999}'):
            self.registry.write_bytes(raw)
            self.assertEqual(self.invoke()[0], 2)
            self.assertFalse(self.output.exists())

    def test_blank_malformed_and_duplicate_ledger_rows_fail(self):
        for raw in (b"\n", b"not-json\n", b'{"x":1,"x":2}\n'):
            self.ledger.write_bytes(raw)
            self.assertEqual(self.invoke()[0], 2)
            self.assertFalse(self.output.exists())

    def test_file_and_line_byte_caps_fail(self):
        for name in ("MAX_LEDGER_BYTES", "MAX_LINE_BYTES", "MAX_REGISTRY_BYTES"):
            with patch.object(stage_review, name, 1):
                self.assertEqual(self.invoke()[0], 2)
                self.assertFalse(self.output.exists())

    def test_existing_generation_is_not_overwritten(self):
        self.assertEqual(self.invoke()[0], 0)
        before = {p.name: sha(p.read_bytes()) for p in self.output.iterdir()}
        self.assertEqual(self.invoke()[0], 2)
        self.assertEqual(before, {p.name: sha(p.read_bytes()) for p in self.output.iterdir()})

    def test_errors_do_not_echo_inputs_or_paths(self):
        self.ledger.write_bytes(b"PRIVATE_SENTINEL_NOT_JSON")
        code, out, err = self.invoke()
        self.assertEqual(code, 2)
        self.assertNotIn("PRIVATE_SENTINEL", out + err)
        self.assertNotIn(str(self.root), out + err)


if __name__ == "__main__":
    unittest.main()
