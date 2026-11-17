#!/usr/bin/env python3
"""Migrate admission callers to explicitly pinned, offline review staging.

Read only local JSON/JSONL bytes. Never execute a proof, load a pickle, infer a
trusted anchor from the untrusted ledger, download a dependency or train a model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import admission

MAX_LEDGER_BYTES = 64 * 1024 * 1024
MAX_REGISTRY_BYTES = 4 * 1024 * 1024
MAX_LINE_BYTES = 256 * 1024
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError("non-finite JSON is not admitted")


def strict_json(raw):
    value = json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite)
    # Reject numeric overflow to Infinity as well as literal NaN/Infinity.
    json.dumps(value, allow_nan=False)
    return value


def pinned_bytes(path: Path, expected: str, maximum: int) -> bytes:
    if not isinstance(expected, str) or not HEX64.fullmatch(expected):
        raise ValueError("an explicit full SHA-256 is required")
    if path.is_symlink() or not path.is_file():
        raise ValueError("source must be a regular, non-symlink file")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("source bytes do not match the admitted snapshot")
    return raw


def stage(*, ledger: Path, ledger_sha256: str, registry: Path,
          registry_sha256: str, expected_chain_head: str, output: Path):
    raw = pinned_bytes(ledger, ledger_sha256, MAX_LEDGER_BYTES)
    statements = strict_json(pinned_bytes(registry, registry_sha256, MAX_REGISTRY_BYTES))
    if not isinstance(expected_chain_head, str) or not HEX64.fullmatch(expected_chain_head):
        raise ValueError("a separately trusted ledger head is required")
    lines = raw.splitlines()
    if not 1 <= len(lines) <= admission._MAX_ENTRIES:
        raise ValueError("ledger line count is outside the admitted limit")
    entries = []
    for line in lines:
        if not line.strip() or len(line) > MAX_LINE_BYTES:
            raise ValueError("blank or oversized ledger row")
        entries.append(strict_json(line))
    return admission.admit(entries, statements, expected_chain_head=expected_chain_head,
                           output_dir=output)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--ledger-sha256", required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--registry-sha256", required=True)
    parser.add_argument("--expected-chain-head", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = stage(**vars(args))
    except (ValueError, OSError, UnicodeError, RecursionError, TypeError) as exc:
        # Never echo the ledger, registry, private paths, or proof text on failure.
        print(json.dumps({"state": "BLOCKED", "error_type": type(exc).__name__,
                          "training_authority": "NONE"}), file=sys.stderr)
        return 2
    print(json.dumps(manifest, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
