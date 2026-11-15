"""GRPO/RLVR adapter: Lean-compile-as-reward.

Wrap a verl/TRL-style reward call: for each completion, splice the proof
attempt into its probe statement, run the referee, and return the
honesty-shaped scalar reward. Kernel-compile IS the reward signal: no
LLM judge, no rubric — the Lean kernel decides.

Usage (verl / TRL GRPOTrainer custom reward fn):
    from grpo_adapter import LeanKernelReward
    r = LeanKernelReward(probe_registry)
    rewards = r(completions=[attempt_text, ...], probe_ids=[...])
"""
import referee
import rewards
import chains


class LeanKernelReward:
    def __init__(self, registry, mode="fast"):
        """registry: {probe_id: (statement, probe_class)}"""
        self.registry = registry
        self.mode = mode

    def __call__(self, completions, probe_ids, **kwargs):
        out = []
        for attempt, pid in zip(completions, probe_ids):
            statement, probe_class = self.registry[pid]
            receipt = referee.classify(pid, statement, attempt, mode=self.mode)
            entry = chains.record(receipt, probe_class)
            out.append(entry["reward"])
        return out
