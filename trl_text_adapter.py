"""Explicit conversation-to-text adapter for the Lean kernel reward (TRL GRPO).

``grpo_adapter.LeanKernelReward`` deliberately accepts only plain strings and
says conversation-shaped TRL completions need an explicit upstream adapter.
This is that adapter. It is strict, not forgiving:

* a completion is either a ``str`` or exactly one assistant message
  ``[{"role": "assistant", "content": str}]`` (TRL conversational format);
* any other shape rejects the WHOLE batch before a single referee call;
* an optional single fenced ``lean`` code block is unwrapped. Zero fences
  means the text is used as-is; two or more fences are ambiguous and get the
  explicit ``AMBIGUOUS_FENCE`` placeholder, which the referee scores 0.0
  (BUILD_ERROR) rather than picking one.

It adds no reward semantics, no sandbox, no independent proof checking and no
training authority. Untrusted Lean must still run in an OS-isolated,
credential-free worker (see README). TRL passes dataset columns as kwargs, so
the probe ids column is read from ``probe_ids`` (configurable).
"""
from __future__ import annotations

import re
from typing import Any, Callable, Sequence

MAX_COMPLETION_CHARS = 128 * 1024
_FENCE_RE = re.compile(r"```[ \t]*(?:lean4?|Lean4?)?[ \t]*\n(.*?)\n?```", re.S)
AMBIGUOUS_FENCE = "-- AMBIGUOUS_FENCE (adapter refused to choose between code blocks)\n  exact (by decide : False)"


def completion_text(comp: Any) -> str:
    """Return the model-authored text of one completion or raise ValueError."""
    if type(comp) is str:
        text = comp
    else:
        if type(comp) in (list, tuple):
            if len(comp) != 1:
                raise ValueError("COMPLETION_SEQUENCE_AMBIGUOUS")
            comp = comp[0]
        if type(comp) is not dict:
            raise ValueError("COMPLETION_SHAPE_INVALID")
        if comp.get("role") != "assistant":
            raise ValueError("COMPLETION_NOT_ASSISTANT")
        text = comp.get("content")
        if type(text) is not str:
            raise ValueError("COMPLETION_CONTENT_NOT_TEXT")
    if len(text) > MAX_COMPLETION_CHARS or "\x00" in text:
        raise ValueError("COMPLETION_TEXT_INVALID_OR_OVERSIZED")
    return text


def extract_attempt(text: str) -> str:
    """Unwrap exactly one fenced Lean block; never choose among several."""
    blocks = _FENCE_RE.findall(text)
    if not blocks:
        return text.strip("\n")
    if len(blocks) > 1:
        return AMBIGUOUS_FENCE
    return blocks[0].strip("\n")


class ConversationLeanReward:
    """TRL-compatible reward callback: ``reward(completions, **columns)``.

    ``inner`` is a ``grpo_adapter.LeanKernelReward`` (or any callable with the
    same ``(completions, probe_ids)`` contract). All shape checks finish before
    ``inner`` is called, so a malformed batch makes zero referee calls and zero
    ledger writes.
    """

    __name__ = "lean_kernel_reward"  # TRL logs reward functions by __name__

    def __init__(self, inner: Callable[..., Sequence[float]], probe_column: str = "probe_ids") -> None:
        if not callable(inner):
            raise ValueError("inner reward must be callable")
        if not isinstance(probe_column, str) or not probe_column:
            raise ValueError("probe_column must be a nonempty string")
        self.inner = inner
        self.probe_column = probe_column

    def __call__(self, completions, **kwargs):
        if type(completions) not in (list, tuple):
            raise ValueError("COMPLETIONS_MUST_BE_SEQUENCE")
        probe_ids = kwargs.get(self.probe_column)
        if type(probe_ids) not in (list, tuple) or len(probe_ids) != len(completions):
            raise ValueError("PROBE_IDS_MISSING_OR_MISALIGNED")
        attempts = [extract_attempt(completion_text(c)) for c in completions]
        rewards = list(self.inner(attempts, list(probe_ids)))
        if len(rewards) != len(completions):
            raise ValueError("INNER_REWARD_LENGTH_MISMATCH")
        return rewards
