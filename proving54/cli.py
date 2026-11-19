#!/usr/bin/env python3
"""54-hour local CPU proving-ground runner. No cloud/GPU control functions."""

from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from proving54 import engine


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_subparsers(dest="action", required=True)
    for action in ("init", "tick", "status", "doctor"):
        sub = choice.add_parser(action)
        if action != "doctor":
            sub.add_argument("--run", required=True, type=Path)
    args = parser.parse_args(argv)
    # Live CLI always uses the actual UTC clock. Synthetic time travel is
    # restricted to explicit unit-test calls of the pure engine functions.
    now = datetime.now(timezone.utc)
    try:
        if args.action == "doctor":
            cfg = engine.registry()
            out = {
                "source_registry_sha256": hashlib.sha256(
                    engine.REGISTRY.read_bytes()
                ).hexdigest(),
                "hours": cfg["hours"],
                "logical_role_count": len(cfg["roles"]),
                "source_pointers": len(cfg["sources"]),
                "gpu_compute_admitted": False,
                "cloud_mutations": 0,
                "result": "SOURCE_POLICY_VALID_NOT_DEPLOYED",
            }
        elif args.action == "init":
            out = engine.init_run(args.run, now)
        elif args.action == "tick":
            out = engine.tick(args.run, now)
        else:
            out = engine.status(args.run, now)
    except (engine.Hold, OSError, ValueError) as e:
        code = str(e) if isinstance(e, engine.Hold) else type(e).__name__
        out = {"result": "HOLD", "reason": code}
        if isinstance(e, engine.ReceiptNotCommitted):
            # The receipt is on disk; the next tick decides whether to adopt it.
            out["uncommitted_hour"] = e.hour
        print(json.dumps(out, sort_keys=True))
        return 2
    print(json.dumps(out, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
