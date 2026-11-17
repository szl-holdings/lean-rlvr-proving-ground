# SPDX-License-Identifier: Apache-2.0
"""Read-only Second Brain owner-mount contract test. NEVER a production identity.

This bounded harness imports the actual pinned Second Brain FastAPI app in one
test process, then mounts the admitted AssuranceASGI adapter with a synthetic,
in-process Context gate. There is no new production route or credential source.

The TestClient creates no public listener. All ledger records are synthetic.
An unauthenticated request, including requests with forged identity headers,
must stay denied. Actual owner authentication and external anchor custody are
separate release gates; a passing local test cannot authorize their deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

PINNED_SECOND_BRAIN = "e4c6031a4e6e111a9c79601eaf8e4d9f24a1b40a"
CHECKS = (
    "public_refinement_route_unchanged",
    "forged_identity_denied",
    "unsigned_unknown_tenant_denied",
    "synthetic_owner_snapshot",
    "source_A_withdrawn_B_alternative_survives",
    "stale_head_rejected",
    "stale_anchor_unavailable",
    "post_revoke_denied",
    "method_write_denied",
    "ledger_bytes_unchanged",
)


def _repo_head(path: Path) -> str:
    if not path.is_dir() or not (path / ".git").exists():
        raise ValueError("PINNED_OWNER_CHECKOUT_REQUIRED")
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    if result.returncode:
        raise ValueError("OWNER_SOURCE_UNOBSERVED")
    head = result.stdout.strip()
    if head != PINNED_SECOND_BRAIN:
        raise ValueError("OWNER_REVISION_CHANGED")
    dirty = subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain",
         "--untracked-files=all"],
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    if dirty.returncode or dirty.stdout.strip():
        raise ValueError("OWNER_WORKTREE_NOT_PINNED")
    return head


def _run(owner_checkout: Path) -> dict:
    _repo_head(owner_checkout)
    # Use exact on-disk checkout; never fall back to an unpinned installed app.
    sys.path.insert(0, str(owner_checkout))
    from fastapi.testclient import TestClient
    from second_brain.web import app as owner_app
    from assurance_asgi import AssuranceASGI
    from assurance_demo_server import make_demo
    from assurance_surface import Context

    old_routes = tuple(getattr(r, "path", None) for r in owner_app.routes)
    actor = [None]
    clock = [1000]
    done = []

    # Entire owner app is local to this test interpreter. No production import.
    with tempfile.TemporaryDirectory(prefix="szl-assurance-owner-contract-") as temp:
        demo = make_demo(Path(temp) / "synthetic", clock=lambda: clock[0], ttl=60)
        ledger_before = demo.ledger.read_bytes()
        with TestClient(owner_app) as client:
            public_before = client.get("/api/v1/refinement-memory")
            assert public_before.status_code in (200, 503)
            assert "HANDLES_ONLY" in public_before.text
            # The resolver is a closure controlled by the test runner, not HTTP.
            owner_app.mount(
                "/assurance", AssuranceASGI(demo.service, lambda scope: actor[0])
            )
            assert tuple(getattr(r, "path", None) for r in owner_app.routes[:-1]) == old_routes
            public_after = client.get("/api/v1/refinement-memory")
            assert public_after.status_code == public_before.status_code
            assert public_after.json() == public_before.json()
            done.append("public_refinement_route_unchanged")

            response = client.get(
                "/assurance/api/snapshot",
                headers={"X-Principal": "research-controller",
                         "X-SZL-Tenant": "research", "X-Authenticated": "true"},
            )
            assert response.status_code == 401
            assert "secret" not in response.text.lower()
            done.append("forged_identity_denied")

            actor[0] = Context("untrusted", "other-tenant")
            response = client.get("/assurance/api/snapshot")
            assert response.status_code == 403
            done.append("unsigned_unknown_tenant_denied")

            actor[0] = Context("research-controller", "research")
            response = client.get("/assurance/api/snapshot")
            assert response.status_code == 200, response.status_code
            snapshot = response.json()
            assert snapshot["data_class"] == "SYNTHETIC_DEMO"
            assert snapshot["capabilities"] == {
                "content_hydration": False, "execution": False,
                "training": False, "promotion": False,
            }
            assert snapshot["visible_object_count"] == 6
            done.append("synthetic_owner_snapshot")

            conditional = client.get(
                "/assurance/api/scenario?withdraw=A",
                headers={"If-Match": snapshot["head"]},
            )
            assert conditional.status_code == 200
            scenario = conditional.json()
            indexed = {r["id"]: r for r in scenario["objects"]}
            assert indexed["only_A"]["scenario_state"] == "UNSUPPORTED"
            assert indexed["either"]["scenario_state"] == "SUPPORTED"
            assert indexed["downstream"]["scenario_state"] == "SUPPORTED"
            assert scenario["scenario"]["persistent_mutations"] == 0
            done.append("source_A_withdrawn_B_alternative_survives")

            bad_head = client.get(
                "/assurance/api/scenario?withdraw=A",
                headers={"If-Match": "0" * 64},
            )
            assert bad_head.status_code == 409
            done.append("stale_head_rejected")

            clock[0] = 1060
            stale = client.get("/assurance/api/snapshot")
            assert stale.status_code == 503 and "STALE_ANCHOR" in stale.text
            done.append("stale_anchor_unavailable")
            clock[0] = 1000

            actor[0] = None
            denied_again = client.get("/assurance/api/snapshot")
            assert denied_again.status_code == 401
            done.append("post_revoke_denied")

            actor[0] = Context("research-controller", "research")
            write = client.post("/assurance/api/snapshot", json={"action": "write"})
            assert write.status_code == 405
            done.append("method_write_denied")

        assert demo.ledger.read_bytes() == ledger_before
        done.append("ledger_bytes_unchanged")

    assert tuple(done) == CHECKS, ("INCOMPLETE_CONTRACT", done)
    return {
        "schema": "szl.assurance.second-brain-owner-contract/v1",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "host_source_revision": PINNED_SECOND_BRAIN,
        "scope": "isolated TestClient against actual pinned public Second Brain app",
        "checks": done,
        "passed": len(done),
        "synthetic_identity": True,
        "external_anchor_proved": False,
        "production_identity_proved": False,
        "live_data_hydrated": False,
        "browser_rendered": False,
        "model_runs": 0,
        "network_listeners_created": 0,
        "production_deployments": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-checkout", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    owner = args.owner_checkout.resolve(strict=True)
    _repo_head(owner)
    # An existing output path implies another owner. Never overwrite receipts.
    if args.out.exists():
        raise ValueError("OUTPUT_ALREADY_EXISTS")
    report = _run(owner)
    encoded = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
    with args.out.open("xb") as f:
        f.write(encoded)
        f.flush()
        os.fsync(f.fileno())
    assert args.out.read_bytes() == encoded
    print(json.dumps({
        "status": "SYNTHETIC_OWNER_MOUNT_VERIFIED",
        "checks": len(CHECKS),
        "owner_revision": PINNED_SECOND_BRAIN,
        "receipt_sha256": hashlib.sha256(encoded).hexdigest(),
        "live_mount": False,
    }), flush=True)


if __name__ == "__main__":
    main()
