"""Synthetic controls: no Lean, GPU, training, or real ledger mutation."""
import unittest
from unittest.mock import patch

import grpo_adapter as ga

STATEMENT = "theorem target : True"
REGISTRY = {"one": (STATEMENT, "SYMBOLIC"), "two": (STATEMENT, "CONJECTURE")}


class RewardBatchTests(unittest.TestCase):
    def setUp(self):
        self.observe = patch.object(ga.referee, "classify", return_value={"verdict": "ABSTAIN"}).start()
        self.record = patch.object(ga.chains, "record", return_value={"reward": 0.5}).start()
        self.addCleanup(patch.stopall)
        self.reward = ga.LeanKernelReward(REGISTRY)

    def rejected(self, attempts, ids):
        with self.assertRaises(ValueError):
            self.reward(attempts, ids)
        self.observe.assert_not_called()
        self.record.assert_not_called()

    def test_missing_probe_id_rejects_instead_of_truncating(self):
        self.rejected(["trivial", "trivial"], ["one"])

    def test_extra_probe_id_rejects_instead_of_truncating(self):
        self.rejected(["trivial"], ["one", "two"])

    def test_late_unknown_probe_makes_no_partial_writes(self):
        self.rejected(["trivial", "trivial"], ["one", "unknown"])

    def test_late_bad_completion_makes_no_partial_writes(self):
        self.rejected(["trivial", {"role": "assistant", "content": "trivial"}], ["one", "two"])

    def test_empty_coverage_is_not_an_empty_success(self):
        self.rejected([], [])

    def test_unbounded_iterator_is_not_consumed(self):
        def forbidden():
            raise AssertionError("iterator must not be consumed")
            yield "trivial"
        self.rejected(forbidden(), ["one"])

    def test_strings_are_not_sample_sequences(self):
        self.rejected("trivial", "one")

    def test_batch_cap_precedes_side_effects(self):
        self.rejected(["trivial"] * (ga.MAX_BATCH_SIZE + 1), ["one"] * (ga.MAX_BATCH_SIZE + 1))

    def test_oversized_completion_precedes_side_effects(self):
        self.rejected(["x" * (ga.referee.MAX_INPUT_BYTES + 1)], ["one"])

    def test_repeated_probe_samples_are_preserved(self):
        self.assertEqual(self.reward(["trivial", "trivial"], ["one", "one"]), [0.5, 0.5])
        self.assertEqual(self.observe.call_count, 2)
        self.assertEqual(self.record.call_count, 2)

    def test_registry_is_detached_from_later_caller_mutation(self):
        registry = {"one": [STATEMENT, "SYMBOLIC"]}
        reward = ga.LeanKernelReward(registry)
        registry["one"][0] = "theorem wrong : False"
        registry.clear()
        reward(["trivial"], ["one"])
        self.assertEqual(self.observe.call_args.args[1], STATEMENT)
        with self.assertRaises(TypeError):
            reward.registry["one"] = ("wrong", "SYMBOLIC")

    def test_invalid_registry_and_mode_fail(self):
        for registry in ({}, {"one": "bad"}, {"one": (STATEMENT, "UNKNOWN")},
                         {"one": ("", "SYMBOLIC")}, {"one": ("not a declaration", "SYMBOLIC")}):
            with self.subTest(registry=registry), self.assertRaises(ValueError):
                ga.LeanKernelReward(registry)
        with self.assertRaises(ValueError):
            ga.LeanKernelReward(REGISTRY, mode="invalid")

    def test_operational_failure_is_not_silently_retried(self):
        self.observe.side_effect = RuntimeError("synthetic worker failure")
        with self.assertRaises(RuntimeError):
            self.reward(["trivial"], ["one"])
        self.assertEqual(self.observe.call_count, 1)
        self.record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
