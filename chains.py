"""Append-only, hash-chained attempt receipts.

Each attempt on a probe is appended to chains/attempts.jsonl. Every entry
carries the sha256 of its payload plus the sha256 of the previous entry,
making the chain tamper-evident (replacing or removing an entry breaks
every later link). Khipu/DSSE signature integration is a recorded
follow-up; the hash chain is the v0 integrity layer.
"""
import hashlib
import json
import time
from pathlib import Path

import referee

CHAINS_PATH = Path(__file__).resolve().parent / "chains" / "attempts.jsonl"


def _prev_sha() -> str:
    if not CHAINS_PATH.exists():
        return "GENESIS"
    lines = CHAINS_PATH.read_text().strip().splitlines()
    if not lines:
        return "GENESIS"
    return json.loads(lines[-1])["entry_sha256"]


def record(receipt: dict, probe_class: str) -> dict:
    CHAINS_PATH.parent.mkdir(exist_ok=True)
    import rewards
    entry = dict(receipt)
    entry["probe_class"] = probe_class
    entry["reward"] = rewards.reward(receipt["verdict"], probe_class)
    entry["recorded_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry["prev_sha256"] = _prev_sha()
    payload = json.dumps({k: entry[k] for k in sorted(entry)},
                         sort_keys=True).encode()
    entry["entry_sha256"] = hashlib.sha256(payload).hexdigest()
    with CHAINS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def verify() -> dict:
    """Fail-closed chain verification: every link must match."""
    if not CHAINS_PATH.exists():
        return {"ok": True, "entries": 0, "note": "no chain yet"}
    entries = [json.loads(l) for l in CHAINS_PATH.read_text().strip().splitlines() if l.strip()]
    prev = "GENESIS"
    for i, e in enumerate(entries):
        if e["prev_sha256"] != prev:
            return {"ok": False, "broken_at": i, "entries": len(entries)}
        payload = json.dumps({k: e[k] for k in sorted(e) if k != "entry_sha256"},
                             sort_keys=True).encode()
        if hashlib.sha256(payload).hexdigest() != e["entry_sha256"]:
            return {"ok": False, "broken_at": i, "entries": len(entries)}
        prev = e["entry_sha256"]
    return {"ok": True, "entries": len(entries)}
