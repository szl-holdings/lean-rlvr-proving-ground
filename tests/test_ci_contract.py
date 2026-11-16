#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Test the real CI chain command against temporary synthetic chain files."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"


def command():
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"(?m)^      - name: Chain integrity check\n        run: (.+)$", text)
    if match is None:
        raise AssertionError("chain gate command is missing or no longer directly testable")
    parts = shlex.split(match.group(1))
    if len(parts) != 3 or parts[:2] != ["python3", "-c"]:
        raise AssertionError("expected a single Python chain gate")
    return parts[2]


def entry(payload, previous="GENESIS"):
    value = dict(payload, prev_sha256=previous)
    encoded = json.dumps(value, sort_keys=True).encode()
    value["entry_sha256"] = hashlib.sha256(encoded).hexdigest()
    return value


class CIContractTests(unittest.TestCase):
    def invoke(self, content=None):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture-chain.jsonl"
            if content is not None:
                path.write_text(content, encoding="utf-8", newline="\n")
            bootstrap = (
                "import sys; from pathlib import Path; import chains; "
                "chains.CHAINS_PATH = Path(sys.argv[1]); "
                "exec(compile(sys.argv[2], '<actual-ci-chain-gate>', 'exec'))"
            )
            return subprocess.run([sys.executable, "-B", "-c", bootstrap, str(path), command()],
                                  cwd=ROOT, capture_output=True, text=True, timeout=10)

    def test_valid_two_entry_chain_passes(self):
        first = entry({"fixture": "one"})
        second = entry({"fixture": "two"}, first["entry_sha256"])
        result = self.invoke("\n".join(map(json.dumps, [first, second])) + "\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("'entries': 2", result.stdout)

    def test_payload_tampering_fails_ci(self):
        row = entry({"fixture": "original"})
        row["fixture"] = "tampered"
        result = self.invoke(json.dumps(row) + "\n")
        self.assertNotEqual(result.returncode, 0, "a false verifier result must fail CI")
        self.assertIn("'ok': False", result.stdout)

    def test_broken_previous_link_fails_ci(self):
        row = entry({"fixture": "wrong-link"}, "not-genesis")
        result = self.invoke(json.dumps(row) + "\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("'ok': False", result.stdout)

    def test_reordered_entries_fail_ci(self):
        first = entry({"fixture": "one"})
        second = entry({"fixture": "two"}, first["entry_sha256"])
        result = self.invoke("\n".join(map(json.dumps, [second, first])) + "\n")
        self.assertNotEqual(result.returncode, 0)

    def test_malformed_input_fails_ci(self):
        self.assertNotEqual(self.invoke("not-json\n").returncode, 0)

    def test_missing_chain_retains_explicit_zero_entry_semantics(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0)
        self.assertIn("'entries': 0", result.stdout)
        self.assertIn("no chain yet", result.stdout)

    def test_actions_are_full_commit_pins(self):
        uses = re.findall(r"(?m)^\s*- uses: ([^\s#]+)", WORKFLOW.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(uses), 1)
        for action in uses:
            self.assertRegex(action, r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")

    def test_explicit_kernel_and_referee_checks_are_retained(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("run: lake build", text)
        self.assertIn("run: python3 selftest.py", text)
        self.assertNotIn("auto-build:", text)
        self.assertNotIn("continue-on-error", text)


if __name__ == "__main__":
    unittest.main()
