"""Text-only provisional reward adapter with full-batch input validation.

This adapter does not supply an OS sandbox or independent proof checking.
Run unreviewed completions only inside a separately governed, credential-free
worker. Conversation-shaped TRL completions require an explicit upstream text
adapter; they are not silently flattened here. No training launch occurs here.
"""
from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

import chains
import referee

MAX_BATCH_SIZE = 256
PROBE_CLASSES = frozenset({"SYMBOLIC", "DIMENSIONAL", "EMPIRICAL", "DEFINITIONAL", "CONJECTURE"})


def _bounded_text(value: object, *, nonempty: bool = False) -> bool:
    return (isinstance(value, str)
            and len(value.encode("utf-8")) <= referee.MAX_INPUT_BYTES
            and (not nonempty or bool(value.strip())))


class LeanKernelReward:
    """Preserve one reward per completion; reject bad batches before side effects.

    The registry is copied, so later caller mutation cannot rebind statements.
    Invalid inputs make zero referee calls and zero ledger writes. Operational
    failures during a valid batch may leave completed observation receipts;
    reconcile that ledger before retrying. This is not a batch transaction.
    The existing ledger still requires a single, externally coordinated writer.
    """

    def __init__(self, registry: Mapping, mode: str = "fast") -> None:
        if mode not in {"fast", "lake"}:
            raise ValueError("mode must be fast|lake")
        if not isinstance(registry, Mapping) or not registry:
            raise ValueError("a nonempty trusted statement registry is required")
        snapshot = {}
        for pid, binding in registry.items():
            if (not _bounded_text(pid, nonempty=True)
                    or not isinstance(binding, (tuple, list)) or len(binding) != 2):
                raise ValueError("invalid trusted registry binding")
            statement, probe_class = binding
            if (not _bounded_text(statement, nonempty=True)
                    or not referee._stmt_name(statement)
                    or not isinstance(probe_class, str) or probe_class not in PROBE_CLASSES):
                raise ValueError("invalid statement or probe class")
            snapshot[pid] = (statement, probe_class)
        self.registry = MappingProxyType(snapshot)
        self.mode = mode

    def __call__(self, completions, probe_ids, **kwargs):
        # Materialize only bounded concrete sequences, never an unbounded iterator.
        if not isinstance(completions, (list, tuple)) or not isinstance(probe_ids, (list, tuple)):
            raise ValueError("completions and probe_ids must be lists or tuples")
        if not 1 <= len(completions) <= MAX_BATCH_SIZE or len(completions) != len(probe_ids):
            raise ValueError("a nonempty bounded batch needs exactly one probe id per completion")
        bound = []
        for attempt, pid in zip(tuple(completions), tuple(probe_ids), strict=True):
            if (not _bounded_text(attempt) or not _bounded_text(pid, nonempty=True)
                    or pid not in self.registry):
                raise ValueError("invalid completion or unknown probe in batch")
            statement, probe_class = self.registry[pid]
            bound.append((pid, statement, attempt, probe_class))
        out = []
        for pid, statement, attempt, probe_class in bound:
            receipt = referee.classify(pid, statement, attempt, mode=self.mode)
            entry = chains.record(receipt, probe_class)
            out.append(entry["reward"])
        return out
