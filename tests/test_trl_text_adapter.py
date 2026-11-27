import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import trl_text_adapter as t  # noqa: E402


class Spy:
    def __init__(self):
        self.calls = []

    def __call__(self, completions, probe_ids):
        self.calls.append((list(completions), list(probe_ids)))
        return [1.0 for _ in completions]


def test_plain_string_passthrough():
    spy = Spy()
    r = t.ConversationLeanReward(spy)
    assert r(["rfl"], probe_ids=["p1"]) == [1.0]
    assert spy.calls == [(["rfl"], ["p1"])]


def test_conversation_and_single_fence_unwrapped():
    spy = Spy()
    r = t.ConversationLeanReward(spy)
    comp = [[{"role": "assistant", "content": "Proof:\n```lean\nsimp\n```\n"}]]
    r(comp, probe_ids=["p1"])
    assert spy.calls[0][0] == ["simp"]


def test_multiple_fences_are_not_guessed():
    assert t.extract_attempt("```lean\nrfl\n```\n```lean\nsimp\n```") == t.AMBIGUOUS_FENCE


@pytest.mark.parametrize("bad", [
    [[{"role": "user", "content": "x"}]],
    [[{"role": "assistant", "content": "a"}, {"role": "assistant", "content": "b"}]],
    [{"role": "assistant", "content": 3}],
    [7],
    ["a\x00b"],
])
def test_bad_shapes_reject_batch_before_any_call(bad):
    spy = Spy()
    r = t.ConversationLeanReward(spy)
    with pytest.raises(ValueError):
        r(["rfl"] + bad, probe_ids=["p"] * (1 + len(bad)))
    assert spy.calls == []


def test_misaligned_probe_ids_rejected():
    spy = Spy()
    with pytest.raises(ValueError):
        t.ConversationLeanReward(spy)(["rfl", "rfl"], probe_ids=["p"])
    assert spy.calls == []


def test_inner_length_mismatch_rejected():
    with pytest.raises(ValueError):
        t.ConversationLeanReward(lambda c, p: [1.0])(["a", "b"], probe_ids=["x", "y"])


@pytest.mark.skipif(shutil.which("lean") is None, reason="lean not installed")
def test_real_kernel_end_to_end(tmp_path, monkeypatch):
    import chains
    import grpo_adapter

    monkeypatch.setattr(chains, "CHAINS_PATH", tmp_path / "attempts.jsonl")
    registry = {
        "two": ("theorem two_eq : 1 + 1 = 2", "SYMBOLIC"),
        "conj": ("theorem conj_open : True", "CONJECTURE"),
    }
    reward = t.ConversationLeanReward(grpo_adapter.LeanKernelReward(registry, mode="fast"))
    comps = [
        [{"role": "assistant", "content": "```lean\nrfl\n```"}],
        [{"role": "assistant", "content": "sorry"}],
        [{"role": "assistant", "content": "-- ABSTAIN open conjecture"}],
    ]
    out = reward(comps, probe_ids=["two", "two", "conj"])
    assert out == [1.0, 0.0, 0.5]
    v = chains.verify()
    assert v["ok"] is True and v["entries"] == 3
