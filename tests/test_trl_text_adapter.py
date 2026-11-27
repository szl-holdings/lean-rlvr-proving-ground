#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Regressions for the explicit TRL conversation adapter (stdlib unittest; CI has no pytest)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import trl_text_adapter as t  # noqa: E402


class Spy:
    def __init__(self):
        self.calls = []

    def __call__(self, completions, probe_ids):
        self.calls.append((list(completions), list(probe_ids)))
        return [1.0 for _ in completions]


BAD_SHAPES = [
    [[{"role": "user", "content": "x"}]],
    [[{"role": "assistant", "content": "a"}, {"role": "assistant", "content": "b"}]],
    [{"role": "assistant", "content": 3}],
    [7],
    ["a\x00b"],
]


class TRLTextAdapterTests(unittest.TestCase):
    def test_plain_string_passthrough(self):
        spy = Spy()
        r = t.ConversationLeanReward(spy)
        self.assertEqual(r(["rfl"], probe_ids=["p1"]), [1.0])
        self.assertEqual(spy.calls, [(["rfl"], ["p1"])])

    def test_conversation_and_single_fence_unwrapped(self):
        spy = Spy()
        r = t.ConversationLeanReward(spy)
        comp = [[{"role": "assistant", "content": "Proof:\n```lean\nsimp\n```\n"}]]
        r(comp, probe_ids=["p1"])
        self.assertEqual(spy.calls[0][0], ["simp"])

    def test_multiple_fences_are_not_guessed(self):
        self.assertEqual(
            t.extract_attempt("```lean\nrfl\n```\n```lean\nsimp\n```"), t.AMBIGUOUS_FENCE
        )

    def test_bad_shapes_reject_batch_before_any_call(self):
        for bad in BAD_SHAPES:
            with self.subTest(bad=repr(bad)):
                spy = Spy()
                r = t.ConversationLeanReward(spy)
                with self.assertRaises(ValueError):
                    r(["rfl"] + bad, probe_ids=["p"] * (1 + len(bad)))
                self.assertEqual(spy.calls, [])

    def test_misaligned_probe_ids_rejected(self):
        spy = Spy()
        with self.assertRaises(ValueError):
            t.ConversationLeanReward(spy)(["rfl", "rfl"], probe_ids=["p"])
        self.assertEqual(spy.calls, [])

    def test_inner_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            t.ConversationLeanReward(lambda c, p: [1.0])(["a", "b"], probe_ids=["x", "y"])

    @unittest.skipIf(shutil.which("lean") is None, "lean not installed")
    def test_real_kernel_end_to_end(self):
        import chains
        import grpo_adapter

        original = chains.CHAINS_PATH
        with tempfile.TemporaryDirectory() as folder:
            chains.CHAINS_PATH = Path(folder) / "attempts.jsonl"
            try:
                registry = {
                    "two": ("theorem two_eq : 1 + 1 = 2", "SYMBOLIC"),
                    "conj": ("theorem conj_open : True", "CONJECTURE"),
                }
                reward = t.ConversationLeanReward(
                    grpo_adapter.LeanKernelReward(registry, mode="fast")
                )
                comps = [
                    [{"role": "assistant", "content": "```lean\nrfl\n```"}],
                    [{"role": "assistant", "content": "sorry"}],
                    [{"role": "assistant", "content": "-- ABSTAIN open conjecture"}],
                ]
                out = reward(comps, probe_ids=["two", "two", "conj"])
                self.assertEqual(out, [1.0, 0.0, 0.5])
                v = chains.verify()
                self.assertIs(v["ok"], True)
                self.assertEqual(v["entries"], 3)
            finally:
                chains.CHAINS_PATH = original


if __name__ == "__main__":
    unittest.main()
