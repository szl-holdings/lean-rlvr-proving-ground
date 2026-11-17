# SPDX-License-Identifier: Apache-2.0
"""Synthetic API/security/snapshot/finite-cut controls. Not production qualification."""
from dataclasses import replace
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from assurance_demo import source, claim
from assurance_demo_server import make_demo, running_demo
from assurance_surface import (Anchor, AssuranceApp, AssuranceService,
                               Context, ReadOnlyMemory, minimum_cuts, states_for)
import support_memory as sm


CTX = Context("research-controller", "research")


class SurfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = [1000]
        self.demo = make_demo(Path(self.temp.name)/"demo", clock=lambda: self.now[0], ttl=60)
        self.service = self.demo.service
        self.app = AssuranceApp(self.service)

    def tearDown(self):
        self.temp.cleanup()

    def call(self, path="/api/snapshot", query="", ctx=CTX, method="GET", **extra):
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query,
               "wsgi.input": io.BytesIO(), "szl.assurance.context": ctx, **extra}
        response = {}
        def start(status, headers):
            response.update(status=int(status.split()[0]), headers=dict(headers))
        response["body"] = b"".join(self.app(env, start))
        return response

    def snapshot(self):
        return self.service.snapshot(CTX)

    def append(self, events):
        memory = sm.SupportMemory(self.demo.ledger)
        head = memory.apply(events, expected_head=memory.head(), principal=CTX.principal,
                             authorize=lambda *args: True)
        memory.close()
        self.demo.anchor_box[0] = Anchor(head, self.now[0], "b"*40)
        return head

    def test_valid_snapshot_and_content_identity(self):
        v = self.snapshot()
        checksum = v.pop("snapshot_sha256")
        self.assertEqual(checksum, sm.digest(v))
        self.assertEqual(v["visible_object_count"], 6)
        self.assertEqual(v["data_class"], "SYNTHETIC_DEMO")
        self.assertFalse(any(v["capabilities"].values()))

    def test_missing_identity_denied(self):
        self.assertEqual(self.call(ctx=None)["status"], 401)

    def test_header_cannot_supply_identity(self):
        self.assertEqual(self.call(ctx=None, HTTP_X_PRINCIPAL="research-controller")["status"], 401)

    def test_wrong_tenant_denied(self):
        self.assertEqual(self.call(ctx=Context("research-controller", "other"))["status"], 403)

    def test_query_cannot_supply_clock_or_tenant(self):
        for key in ["tenant", "now", "principal", "policy", "database", "head"]:
            with self.subTest(key=key):
                self.assertEqual(self.call(query=key+"=research")["status"], 422)

    def test_post_denied_even_with_identity(self):
        self.assertEqual(self.call(method="POST")["status"], 405)

    def test_no_arbitrary_file_routes(self):
        for path in ["/../support_memory.py", "/synthetic-ledger.sqlite", "/api/execute", "/assets/../ledger"]:
            self.assertEqual(self.call(path=path)["status"], 404)

    def test_static_assets_exact_allowlist(self):
        for path in ["/", "/assurance.css", "/assurance.mjs"]:
            self.assertEqual(self.call(path=path)["status"], 200)

    def test_no_store_and_security_headers(self):
        headers = self.call()["headers"]
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_stale_anchor_is_unavailable(self):
        self.now[0] = 1060
        r = self.call()
        self.assertEqual(r["status"], 503)
        self.assertEqual(json.loads(r["body"])["reason"], "STALE_ANCHOR")
        self.assertNotIn(b"objects", r["body"])

    def test_future_anchor_is_unavailable(self):
        self.now[0] = 999
        self.assertEqual(json.loads(self.call()["body"])["reason"], "CLOCK_UNCERTAIN")

    def test_stale_client_head_is_rejected(self):
        self.assertEqual(self.call(HTTP_IF_MATCH="0"*64)["status"], 409)

    def test_scenario_requires_head(self):
        self.assertEqual(self.call(path="/api/scenario", query="withdraw=A")["status"], 428)

    def test_cuts_requires_head(self):
        self.assertEqual(self.call(path="/api/cuts", query="target=either")["status"], 428)

    def test_hypothetical_withdrawal_preserves_bytes(self):
        before = self.demo.ledger.read_bytes()
        head = self.snapshot()["head"]
        v = self.service.snapshot(CTX, expected_head=head, withdraw=("A",))
        state = {r["id"]: r["scenario_state"] for r in v["objects"]}
        self.assertEqual(state["only_A"], "UNSUPPORTED")
        self.assertEqual(state["either"], "SUPPORTED")
        self.assertEqual(state["both"], "UNSUPPORTED")
        self.assertEqual(state["downstream"], "SUPPORTED")
        self.assertEqual(before, self.demo.ledger.read_bytes())

    def test_or_support_needs_both_withdrawn(self):
        v = self.service.snapshot(CTX, expected_head=self.snapshot()["head"], target="either")
        self.assertEqual(v["scenario"]["cut_sets"]["sets"], [["A", "B"]])
        self.assertTrue(v["scenario"]["cut_sets"]["search_complete"])

    def test_and_support_fails_on_either_withdrawal(self):
        v = self.service.snapshot(CTX, expected_head=self.snapshot()["head"], target="both")
        self.assertEqual(v["scenario"]["cut_sets"]["sets"], [["A"], ["B"]])

    def test_target_parameter_restricted(self):
        for q in ["", "target=", "target=either&target=both", "target=either&now=1"]:
            self.assertEqual(self.call(path="/api/cuts", query=q, HTTP_IF_MATCH=self.snapshot()["head"])["status"], 422)

    def test_unknown_source_does_not_reveal_metadata(self):
        r = self.call(path="/api/scenario", query="withdraw=secret-target", HTTP_IF_MATCH=self.snapshot()["head"])
        self.assertEqual(r["status"], 404)
        self.assertNotIn(b"secret-target", r["body"])

    def test_claim_cannot_be_withdrawn_through_source_scenario(self):
        r = self.call(path="/api/scenario", query="withdraw=either", HTTP_IF_MATCH=self.snapshot()["head"])
        self.assertEqual(r["status"], 404)

    def test_duplicate_withdrawal_rejected(self):
        r = self.call(path="/api/scenario", query="withdraw=A&withdraw=A", HTTP_IF_MATCH=self.snapshot()["head"])
        self.assertEqual(r["status"], 422)

    def test_anchor_database_drift_rejected(self):
        self.demo.anchor_box[0] = replace(self.demo.anchor_box[0], head="f"*64)
        self.assertEqual(json.loads(self.call()["body"])["reason"], "LEDGER_ANCHOR_MISMATCH")

    def test_withdrawal_at_next_read_propagates(self):
        old = self.snapshot()["head"]
        self.append([{"op":"withdraw","tenant":"research","id":"A","reason":"REVOKED"}])
        self.assertEqual(self.call(HTTP_IF_MATCH=old)["status"], 409)
        state = {r["id"]:r["state"] for r in self.snapshot()["objects"]}
        self.assertEqual(state["only_A"], "UNSUPPORTED")
        self.assertEqual(state["either"], "SUPPORTED")

    def test_api_opens_ledger_read_only(self):
        m = ReadOnlyMemory(self.demo.ledger)
        try:
            self.assertRaises(sqlite3.OperationalError, m.db.execute, "DELETE FROM events")
        finally:
            m.close()

    def test_missing_ledger_not_created(self):
        self.service.ledger = Path(self.temp.name)/"missing.sqlite"
        self.assertEqual(self.call()["status"], 503)
        self.assertFalse(self.service.ledger.exists())

    def test_denied_object_not_returned_in_dependency_terms(self):
        self.service.policy = lambda ctx, key, op: key != "A"
        v = self.snapshot()
        self.assertNotIn('"A"', json.dumps(v))
        state = {r["id"]:r for r in v["objects"]}
        self.assertEqual(state["only_A"]["state"], "UNAVAILABLE")
        self.assertEqual(state["only_A"]["supports"], [])

    def test_cuts_do_not_reveal_denied_dependency(self):
        self.service.policy = lambda ctx, key, op: key != "A"
        r = self.call(path="/api/cuts", query="target=either", HTTP_IF_MATCH=self.snapshot()["head"])
        self.assertEqual(r["status"], 403)
        self.assertNotIn(b'"A"', r["body"])

    def test_truthy_policy_is_not_authorization(self):
        self.service.policy = lambda *args: "yes"
        self.assertEqual(self.call()["status"], 403)

    def test_anchor_change_during_read_rejected(self):
        first = self.demo.anchor_box[0]
        n = [0]
        def anchor():
            n[0] += 1
            return first if n[0] == 1 else replace(first, policy_revision="c"*40)
        self.service.anchor = anchor
        self.assertEqual(self.call()["status"], 409)

    def test_clock_regression_rejected(self):
        times = iter([1001,1000])
        self.service.clock = lambda: next(times)
        self.assertEqual(json.loads(self.call()["body"])["reason"], "CLOCK_UNCERTAIN")

    def test_expiry_propagation_and_lease(self):
        self.append([source("brief", expires_at=1005)])
        self.assertEqual(self.snapshot()["valid_until"], 1005)
        self.now[0] = 1005
        self.assertEqual(next(x for x in self.snapshot()["objects"] if x["id"]=="brief")["state"], "EXPIRED")

    def test_core_replay_matches_reference_for_all_source_subsets(self):
        for removed in [(),("A",),("B",),("A","B")]:
            with tempfile.TemporaryDirectory() as temp:
                d = make_demo(Path(temp)/"d", clock=lambda:1000)
                m = sm.SupportMemory(d.ledger)
                if removed:
                    m.apply([{"op":"withdraw","tenant":"research","id":x,"reason":"REVOKED"} for x in removed], expected_head=m.head(), principal="p", authorize=lambda *a:True)
                events,_ = m._events();nodes,gone=sm._reduce(events)
                reference = m.handles(tenant="research", principal="p", now=1000, authorize=lambda *a:True)
                self.assertEqual(states_for(nodes,gone,1000),{x["id"]:x["support_state"] for x in reference["handles"]})
                m.close()

    def test_minimum_cut_budget_is_disclosed(self):
        m=ReadOnlyMemory(self.demo.ledger);events,_=m._events();m.close();nodes,gone=sm._reduce(events)
        v=minimum_cuts(nodes,gone,1000,"either",max_checks=1)
        self.assertEqual(v["state"],"BOUNDED_PARTIAL");self.assertFalse(v["search_complete"])

    def test_cut_width_bound_is_disclosed(self):
        m=ReadOnlyMemory(self.demo.ledger);events,_=m._events();m.close();nodes,gone=sm._reduce(events)
        v=minimum_cuts(nodes,gone,1000,"either",max_width=1)
        self.assertFalse(v["search_complete"]);self.assertEqual(v["sets"],[])

    def test_no_raw_content_or_publication_authority(self):
        v = self.snapshot()
        self.assertFalse(any(v["capabilities"].values()))
        self.assertFalse(any(v["qualifications"].values()))
        self.assertNotIn("content",v["objects"][0])

    def test_no_query_on_static_asset(self):
        self.assertEqual(self.call(path="/",query="token=anything")["status"],422)

    def test_oversized_query_rejected(self):
        self.assertEqual(self.call(query="x="+"a"*2049)["status"],422)

    def test_boolean_clock_rejected(self):
        self.service.clock=lambda:True
        self.assertEqual(self.call()["status"],503)

    def test_graph_budget_fail_closed(self):
        self.append([source(f"s{i}",expires_at=2000) for i in range(64)])
        self.append([source(f"t{i}",expires_at=2000) for i in range(59)])
        self.assertEqual(json.loads(self.call()["body"])["reason"],"GRAPH_BUDGET")

    def test_tampered_db_not_served(self):
        db=sqlite3.connect(self.demo.ledger)
        db.execute("UPDATE events SET hash=? WHERE seq=1",("f"*64,));db.commit();db.close()
        self.assertEqual(self.call()["status"],503)

    def test_retained_head_detects_truncated_history(self):
        db=sqlite3.connect(self.demo.ledger)
        db.execute("DELETE FROM events WHERE seq=6");db.commit();db.close()
        self.assertEqual(self.call()["status"],409)

    def test_service_requires_reviewed_ttl(self):
        for ttl in [True,0,301]:
            self.assertRaises(ValueError,AssuranceService,self.demo.ledger,self.service.anchor,self.service.policy,self.service.clock,ttl_seconds=ttl)

    def test_faulty_policy_returns_unavailable_without_traceback(self):
        def faulty(*args):
            raise RuntimeError("private provider details")
        self.service.policy=faulty
        response=self.call()
        self.assertEqual(response["status"],503)
        self.assertNotIn(b"private",response["body"])

    def test_cut_pruning_is_inside_search_budget(self):
        events=[source("s"+str(i),expires_at=2000) for i in range(8)]
        events += [claim("c",[["s"+str(i) for i in range(8)]])]
        nodes,gone=sm._reduce(events)
        result=minimum_cuts(nodes,gone,1000,"c",max_checks=10)
        self.assertLessEqual(result["candidates_considered"],10)
        self.assertFalse(result["search_complete"])

    def test_object_revocation_during_read_denies_response(self):
        count = [0]
        def policy(ctx, key, operation):
            if key == "A" and operation == "view":
                count[0] += 1
                return count[0] == 1
            return True
        self.service.policy = policy
        response = self.call()
        self.assertEqual(response["status"], 403)
        self.assertNotIn(b'"objects"', response["body"])

    def test_expiry_during_render_denies_response(self):
        times = iter([1000, 1000, 1030])
        self.service.clock = lambda: next(times)
        self.assertEqual(json.loads(self.call()["body"])["reason"], "VIEW_EXPIRED_DURING_READ")

    def test_anchor_change_at_final_read_denied(self):
        first = self.demo.anchor_box[0]
        count = [0]
        def anchor():
            count[0] += 1
            return first if count[0] < 3 else replace(first, policy_revision="c"*40)
        self.service.anchor = anchor
        self.assertEqual(self.call()["status"], 409)

    def test_large_payload_is_rejected_before_json_loading(self):
        db=sqlite3.connect(self.demo.ledger)
        db.execute("UPDATE events SET payload=? WHERE seq=1",("x"*(4*1024*1024+1),))
        db.commit();db.close()
        self.assertEqual(json.loads(self.call()["body"])["reason"],"LEDGER_READ_BUDGET")


class NetworkTests(unittest.TestCase):
    def test_real_http_assets_snapshot_scenario_and_stale_response(self):
        with tempfile.TemporaryDirectory() as temp:
            now=[1000]
            with running_demo(Path(temp)/"net",clock=lambda:now[0],ttl=60) as demo:
                with urlopen(demo.base_url, timeout=3) as response:
                    self.assertIn(b"Support Boundary Console",response.read())
                with urlopen(demo.base_url+"api/snapshot",timeout=3) as response:
                    first=json.load(response)
                request=Request(demo.base_url+"api/scenario?withdraw=A",headers={"If-Match":first["head"]})
                with urlopen(request,timeout=3) as response:
                    scenario=json.load(response)
                self.assertEqual(next(x for x in scenario["objects"] if x["id"]=="either")["scenario_state"],"SUPPORTED")
                now[0]=1060
                with self.assertRaises(HTTPError) as exc:
                    urlopen(demo.base_url+"api/snapshot",timeout=3)
                self.assertEqual(exc.exception.code,503)
                self.assertEqual(json.load(exc.exception)["reason"],"STALE_ANCHOR")

    def test_demo_host_rebinding_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with running_demo(Path(temp)/"net") as demo:
                request=Request(demo.base_url+"api/snapshot",headers={"Host":"untrusted.example"})
                with self.assertRaises(HTTPError) as exc:
                    urlopen(request,timeout=3)
                self.assertEqual(exc.exception.code,403)

class ASGITests(unittest.TestCase):
    def request(self, adapter, path, *, headers=(), query=b"", root=""):
        import asyncio
        messages=[]
        async def send(value): messages.append(value)
        async def receive(): return {"type":"http.request","body":b"","more_body":False}
        asyncio.run(adapter({"type":"http","method":"GET","path":path,"root_path":root,
                             "query_string":query,"headers":headers},receive,send))
        return messages

    def test_existing_owner_mount_path(self):
        from assurance_asgi import AssuranceASGI
        with tempfile.TemporaryDirectory() as temp:
            demo=make_demo(Path(temp)/"a",clock=lambda:1000)
            messages=self.request(AssuranceASGI(demo.service,lambda scope:CTX),"/assurance/api/snapshot",root="/assurance")
            self.assertEqual(messages[0]["status"],200)
            self.assertEqual(json.loads(messages[1]["body"])["visible_object_count"],6)

    def test_asgi_identity_header_cannot_authorize(self):
        from assurance_asgi import AssuranceASGI
        with tempfile.TemporaryDirectory() as temp:
            demo=make_demo(Path(temp)/"a",clock=lambda:1000)
            messages=self.request(AssuranceASGI(demo.service,lambda scope:None),"/api/snapshot",headers=[(b"x-principal",b"research-controller")])
            self.assertEqual(messages[0]["status"],401)

    def test_asgi_duplicate_precondition_is_rejected(self):
        from assurance_asgi import AssuranceASGI
        with tempfile.TemporaryDirectory() as temp:
            demo=make_demo(Path(temp)/"a",clock=lambda:1000)
            head=demo.anchor_box[0].head.encode()
            messages=self.request(AssuranceASGI(demo.service,lambda scope:CTX),"/api/scenario",headers=[(b"if-match",head),(b"if-match",head)])
            self.assertEqual(messages[0]["status"],409)

    def test_asgi_resolver_exception_does_not_leak(self):
        from assurance_asgi import AssuranceASGI
        def faulty(scope): raise ValueError('private auth configuration')
        with tempfile.TemporaryDirectory() as temp:
            demo=make_demo(Path(temp)/"a",clock=lambda:1000)
            messages=self.request(AssuranceASGI(demo.service,faulty),"/api/snapshot")
            self.assertEqual(messages[0]["status"],401)
            self.assertNotIn(b'private',messages[1]["body"])


if __name__ == "__main__":
    unittest.main()
