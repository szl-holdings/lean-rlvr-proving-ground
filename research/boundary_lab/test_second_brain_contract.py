# SPDX-License-Identifier: Apache-2.0
"""Offline safety of the optional cross-repository test runner itself."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from second_brain_contract import CHECKS, PINNED_SECOND_BRAIN, _repo_head


class OwnerMountPreflightTests(unittest.TestCase):
    def test_pinned_host_revision_is_exact(self):
        self.assertEqual(len(PINNED_SECOND_BRAIN), 40)
        self.assertEqual(PINNED_SECOND_BRAIN,
                         "e4c6031a4e6e111a9c79601eaf8e4d9f24a1b40a")

    def test_checks_are_unique_and_require_readonly(self):
        self.assertEqual(len(CHECKS), 10)
        self.assertEqual(len(set(CHECKS)), len(CHECKS))
        for must in ("forged_identity_denied", "stale_head_rejected",
                     "post_revoke_denied", "ledger_bytes_unchanged"):
            self.assertIn(must, CHECKS)

    def test_no_git_checkout_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "PINNED_OWNER_CHECKOUT_REQUIRED"):
                _repo_head(Path(d))

    def test_unrelated_git_head_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / ".git").mkdir()
            fake = type("Result", (), {"returncode": 0, "stdout": "b" * 40})
            with patch("second_brain_contract.subprocess.run", return_value=fake):
                with self.assertRaisesRegex(ValueError, "OWNER_REVISION_CHANGED"):
                    _repo_head(repo)

    def test_unobserved_git_head_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / ".git").mkdir()
            fake = type("Result", (), {"returncode": 1, "stdout": ""})
            with patch("second_brain_contract.subprocess.run", return_value=fake):
                with self.assertRaisesRegex(ValueError, "OWNER_SOURCE_UNOBSERVED"):
                    _repo_head(repo)

    def test_dirty_owner_checkout_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / ".git").mkdir()
            good = type("Result", (), {
                "returncode": 0, "stdout": PINNED_SECOND_BRAIN,
            })
            dirty = type("Result", (), {
                "returncode": 0, "stdout": " M second_brain/web.py",
            })
            with patch("second_brain_contract.subprocess.run",
                       side_effect=[good, dirty]):
                with self.assertRaisesRegex(ValueError, "OWNER_WORKTREE_NOT_PINNED"):
                    _repo_head(repo)

    def test_git_status_failure_is_unobserved(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / ".git").mkdir()
            good = type("Result", (), {
                "returncode": 0, "stdout": PINNED_SECOND_BRAIN,
            })
            failed = type("Result", (), {"returncode": 1, "stdout": ""})
            with patch("second_brain_contract.subprocess.run",
                       side_effect=[good, failed]):
                with self.assertRaisesRegex(ValueError, "OWNER_WORKTREE_NOT_PINNED"):
                    _repo_head(repo)


if __name__ == "__main__":
    unittest.main()
