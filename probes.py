"""Probe registry: v0 formalized statements + atlas classes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ATLAS_PATH = ROOT / "probes" / "atlas" / "proving-ground.json"

# v0 hand-formalized core-only fragments of atlas probes (statements are
# the declaration header WITHOUT proof; the referee appends " := by").
FORMALIZED = {
    "TH_V18_04-egyptian-horus": ("theorem horus_cleared : 32 + 16 + 8 + 4 + 2 + 1 = 63", "SYMBOLIC"),
    "TH_V18_03-kraft": ("theorem kraft_cleared : 4 + 2 + 1 + 1 = 8", "SYMBOLIC"),
    "F18-reed-solomon-singleton": ("theorem rs_singleton_concrete : (10 - 6) + 1 = 5", "SYMBOLIC"),
}


def _atlas():
    if not ATLAS_PATH.exists():
        return {}
    d = json.loads(ATLAS_PATH.read_text(encoding="utf-8"))
    return {e["id"]: e for e in d.get("atlas", [])}


def probe_class(probe_id: str) -> str:
    a = _atlas()
    if probe_id in a:
        return a[probe_id].get("class", "")
    for pid, (_, cls) in FORMALIZED.items():
        if pid == probe_id:
            return cls
    return "SYMBOLIC"


def conjecture_anchor_id() -> str:
    a = _atlas()
    conj = [i for i, e in a.items() if e.get("class") == "CONJECTURE"]
    return conj[0] if conj else "conjecture-anchor-1"


def atlas_sha256() -> str:
    if not ATLAS_PATH.exists():
        return ""
    return hashlib.sha256(ATLAS_PATH.read_bytes()).hexdigest()
