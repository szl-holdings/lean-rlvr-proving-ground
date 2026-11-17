# SPDX-License-Identifier: Apache-2.0
"""Deterministic differential tests against the admitted full replay oracle."""
from __future__ import annotations

import hashlib
import json
import random
import urllib.request
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import assurance_surface as surface
import support_memory as sm
from assurance_demo_server import make_demo, running_demo
from impact_delta import delta_states


class IncrementalBoundaryTests(unittest.TestCase):
    def test_no_request_is_copy_not_live_alias(self):
        nodes = {"A": {"op": "source", "read_allowed": True, "expires_at": 100}}
        original = {"A": "SUPPORTED"}
        result = delta_states(nodes, set(), 10, set(), original)
        self.assertEqual(result, original)
        self.assertIsNot(result, original)

    def test_source_only_and_baseline_coverage(self):
        nodes = {"A": {"op": "source", "read_allowed": True, "expires_at": 100},
                 "K": {"op": "claim", "read_allowed": True,
                       "expires_at": 100, "supports": [["A"]]}}
        before = surface.states_for(nodes, set(), 10)
        with self.assertRaisesRegex(ValueError, "SOURCE_ONLY"):
            delta_states(nodes, set(), 10, {"K"}, before)
        with self.assertRaisesRegex(ValueError, "SOURCE_ONLY"):
            delta_states(nodes, set(), 10, {"NO_SUCH_SOURCE"}, before)
        with self.assertRaisesRegex(ValueError, "BASELINE_COVERAGE"):
            delta_states(nodes, set(), 10, {"A"}, {"A": "SUPPORTED"})
        with self.assertRaisesRegex(ValueError, "CLOCK_DOMAIN"):
            delta_states(nodes, set(), True, {"A"}, before)
        with self.assertRaisesRegex(ValueError, "SET_REQUIRED"):
            delta_states(nodes, [], 10, {"A"}, before)

    def test_alternative_path_survives_one_withdrawal(self):
        events = [
            {"op": "source", "id": "A", "tenant": "lab", "revision": "a"*40,
             "content_sha256": "b"*64, "expires_at": 100, "read_allowed": True},
            {"op": "source", "id": "B", "tenant": "lab", "revision": "a"*40,
             "content_sha256": "b"*64, "expires_at": 100, "read_allowed": True},
            {"op": "claim", "id": "OR", "tenant": "lab", "revision": "a"*40,
             "content_sha256": "b"*64, "expires_at": 100, "read_allowed": True,
             "supports": [["A"], ["B"]]},
            {"op": "claim", "id": "AND", "tenant": "lab", "revision": "a"*40,
             "content_sha256": "b"*64, "expires_at": 100, "read_allowed": True,
             "supports": [["A", "B"]]},
            {"op": "claim", "id": "DOWNSTREAM", "tenant": "lab",
             "revision": "a"*40, "content_sha256": "b"*64,
             "expires_at": 100, "read_allowed": True, "supports": [["OR"]]}
        ]
        nodes, withdrawn = sm._reduce(events)
        before = surface.states_for(nodes, withdrawn, 10)
        changed = delta_states(nodes, withdrawn, 10, {"A"}, before)
        self.assertEqual(changed["OR"], "SUPPORTED")
        self.assertEqual(changed["DOWNSTREAM"], "SUPPORTED")
        self.assertEqual(changed["AND"], "UNSUPPORTED")
        self.assertEqual(changed, surface.states_for(nodes, {"A"}, 10))
        all_lost = delta_states(nodes, withdrawn, 10, {"A", "B"}, before)
        self.assertEqual(all_lost["OR"], "UNSUPPORTED")
        self.assertEqual(all_lost["DOWNSTREAM"], "UNSUPPORTED")
        self.assertEqual(all_lost, surface.states_for(nodes, {"A", "B"}, 10))
        self.assertEqual(before["A"], "SUPPORTED")
        self.assertEqual(withdrawn, set())

    def test_expiry_and_rights_precedence(self):
        nodes = {
            "expired": {"op": "source", "read_allowed": True, "expires_at": 5},
            "denied": {"op": "source", "read_allowed": False, "expires_at": 100},
            "claim": {"op": "claim", "read_allowed": True, "expires_at": 100,
                      "supports": [["expired"], ["denied"]]}
        }
        before = surface.states_for(nodes, set(), 10)
        changed = delta_states(nodes, set(), 10, {"expired", "denied"}, before)
        self.assertEqual(changed, surface.states_for(nodes, {"expired", "denied"}, 10))
        self.assertEqual(changed["expired"], "WITHDRAWN")
        self.assertEqual(changed["denied"], "WITHDRAWN")
        self.assertEqual(changed["claim"], "UNSUPPORTED")

    def test_validated_forward_dag_required(self):
        nodes = {
            "A": {"op": "source", "expires_at": 100, "read_allowed": True},
            "K": {"op": "claim", "supports": [["OTHER"]],
                  "expires_at": 100, "read_allowed": True}
        }
        with self.assertRaisesRegex(ValueError, "NOT_A_VALID_FORWARD_DAG"):
            delta_states(nodes, set(), 10, {"A"},
                         {"A": "SUPPORTED", "K": "SUPPORTED"})

    def test_bounded_replay_parity(self):
        rng = random.Random(0x51A0_2026)
        observations = 0
        for iteration in range(1200):
            count = rng.randrange(3, 27)
            events, ids = [], []
            for i in range(count):
                op = "source" if i < 2 or rng.randrange(4) == 0 else "claim"
                key = f"n{i}"
                row = {
                    "op": op, "id": key, "tenant": "research",
                    "revision": "a"*40,
                    "content_sha256": hashlib.sha256(key.encode()).hexdigest(),
                    "expires_at": rng.choice([0, 5, 10, 20, 100]),
                    "read_allowed": bool(rng.randrange(3))
                }
                if op == "claim":
                    row["supports"] = [
                        rng.sample(ids, rng.randrange(1, min(4, len(ids))+1))
                        for _ in range(rng.randrange(1, 4))
                    ]
                    # Uniqueness and support constraints must hold under _reduce.
                    dedup = {}
                    for term in row["supports"]:
                        dedup[tuple(sorted(term))] = term
                    row["supports"] = list(dedup.values())
                events.append(row)
                ids.append(key)
            previously = set(rng.sample(ids, rng.randrange(min(4, len(ids))+1)))
            for key in sorted(previously):
                events.append({"op": "withdraw", "tenant": "research",
                               "id": key, "reason": "REVOKED"})
            nodes, withdrawn = sm._reduce(events)
            sources = [k for k, v in nodes.items() if v["op"] == "source"]
            for now in [0, 5, 10, 20, 100]:
                before = surface.states_for(nodes, withdrawn, now)
                requested = set(rng.sample(sources, rng.randrange(min(4, len(sources))+1)))
                actual = delta_states(nodes, withdrawn, now, requested, before)
                full = surface.states_for(nodes, withdrawn | requested, now)
                self.assertEqual(actual, full, f"trial={iteration},time={now}")
                observations += 1
        self.assertEqual(observations, 6000)

    def test_http_path_consumes_incremental_results_without_writes(self):
        with tempfile.TemporaryDirectory() as d:
            demo = make_demo(Path(d)/"demo", clock=lambda: 1000, ttl=60)
            ctx = surface.Context("research-controller", "research")
            before = demo.ledger.read_bytes()
            with patch.object(surface, "delta_states", wraps=delta_states) as called:
                result = demo.service.snapshot(
                    ctx, expected_head=demo.anchor_box[0].head, withdraw=("A",)
                )
            self.assertEqual(called.call_count, 1)
            view = {n["id"]: n for n in result["objects"]}
            self.assertEqual(view["only_A"]["scenario_state"], "UNSUPPORTED")
            self.assertEqual(view["either"]["scenario_state"], "SUPPORTED")
            self.assertEqual(result["scenario"]["persistent_mutations"], 0)
            self.assertEqual(demo.ledger.read_bytes(), before)


    def test_real_http_scenario_parity_and_no_persistent_write(self):
        with tempfile.TemporaryDirectory() as d:
            with running_demo(Path(d)/"service", clock=lambda: 1000, ttl=60) as demo:
                original = demo.ledger.read_bytes()
                with urllib.request.urlopen(
                    demo.base_url + "api/snapshot", timeout=3
                ) as response:
                    baseline = json.load(response)
                request = urllib.request.Request(
                    demo.base_url + "api/scenario?withdraw=A",
                    headers={"If-Match": baseline["head"]}
                )
                with urllib.request.urlopen(request, timeout=3) as response:
                    scenario = json.load(response)
                rows = {x["id"]: x for x in scenario["objects"]}
                self.assertEqual(scenario["state"], "OBSERVED")
                self.assertEqual(scenario["scenario"]["withdraw"], ["A"])
                self.assertEqual(rows["only_A"]["scenario_state"], "UNSUPPORTED")
                self.assertEqual(rows["either"]["scenario_state"], "SUPPORTED")
                self.assertEqual(scenario["scenario"]["persistent_mutations"], 0)
                self.assertEqual(demo.ledger.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
