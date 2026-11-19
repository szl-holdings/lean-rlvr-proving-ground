"""Proving54 five-role source-admission tests; no GPUs, credentials or network."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from proving54 import admission as pg

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "proving54" / "manifest.json"
NOW = pg.START + timedelta(seconds=28)


def fixture():
    return pg.parse(FILE.read_bytes())


class ManifestAndPhysics(unittest.TestCase):
    def test_provenance_and_five_roles_with_54_hour_window(self):
        m=fixture()
        pg.validate(m)
        self.assertEqual(len(m["source_registry"]), 11)
        self.assertEqual([r["id"] for r in m["logical_roles"]],list(pg.ROLE_IDS))
        self.assertEqual([(x["id"],x["start_hour"],x["end_hour"])
                          for x in m["phase_boundaries"]],list(pg.EXPECTED_PHASES))
        self.assertEqual((pg._utc(m["window"]["end_utc"])-pg.START),
                         timedelta(hours=54))
        self.assertFalse(m["physical_capacity"]["paid_compute_authorized"])
        self.assertFalse(m["physical_capacity"]["five_unique_host_liveness_proved"])

    def test_seven_exact_rational_and_integer_oracles(self):
        self.assertEqual(sum((Fraction(1,n) for n in (2,4,8,16,32,64)),
                             Fraction(0)),Fraction(63,64))
        self.assertEqual(Fraction(2,13),Fraction(1,8)+Fraction(1,52)+Fraction(1,104))
        toy=pg.exact_toy_math()
        self.assertEqual(len(toy),7)
        self.assertTrue(all(t["verified_concrete_arithmetic"] for t in toy))
        self.assertTrue(all(not t["historical_manuscript_proof"] for t in toy))
        self.assertTrue(all(not t["independent_scientific_evaluation"] for t in toy))

    def test_five_role_messages_distinct_from_five_supercomputers(self):
        flow=pg.five_role_rehearsal(pg.exact_toy_math())
        self.assertEqual(flow["role_messages"],35)
        self.assertEqual(flow["distinct_roles"],list(pg.ROLE_IDS))
        self.assertFalse(flow["five_physical_computers_running"])
        self.assertFalse(flow["gpu_training_started"])
        self.assertEqual(flow["cloud_writes"],0)

    def test_source_only_holds_before_and_after_54_hours(self):
        m=fixture()
        for clock in (NOW, pg.START+timedelta(hours=54),
                      pg.START+timedelta(days=3)):
            with self.subTest(clock=clock):
                result=pg.assess(m,now=clock)
                self.assertEqual(result["release_status"],"HOLD")
                self.assertFalse(result["all_answers_verified"])
                self.assertFalse(result["qualified_five_node_mesh"])
                self.assertFalse(result["model_weights_trained"])
                self.assertEqual(result["salad_replica_changes"],0)
                self.assertEqual(result["first_party_toy_examples_verified"],7)
        late=pg.assess(m,now=pg.START+timedelta(days=3))
        self.assertNotIn("54_HOUR_WINDOW_NOT_ELAPSED",late["unresolved"])
        self.assertIn("FIVE_GRAND_CHALLENGES_REQUIRE_EXTERNAL_SCIENTIFIC_PROOF",
                      late["unresolved"])

    def test_lutar_source_conditional_not_unconditional(self):
        m=fixture()
        ref=next(x for x in m["source_registry"]
                 if x["repo"]=="szl-holdings/lutar-lean")
        self.assertEqual(ref["path"],"Lutar/Uniqueness/TheoremU.lean")
        self.assertEqual(ref["rights"],"REVIEW_REQUIRED")
        self.assertEqual(ref["allowed_use"],"POINTER_ONLY_NO_GRADIENTS")
        self.assertIn("LUTAR-MAX-COUNTEREXAMPLE",
                      {x["id"] for x in pg.exact_toy_math()})

    def test_unknown_codicies_is_unresolved(self):
        m=fixture()
        self.assertEqual(m["unresolved_source_aliases"],["codicies"])
        self.assertIn("CODICIES_SOURCE_IDENTITY_UNRESOLVED",
                      pg.assess(m,now=NOW)["unresolved"])

    def test_swapping_pinned_github_blob_is_not_a_fix(self):
        m=fixture()
        m["source_registry"][0]["git_blob"]="0"*40
        with self.assertRaisesRegex(pg.Hold,"SOURCE_PIN_CHANGED"):
            pg.validate(m)

    def test_extra_credential_or_secret_field_fails_closed(self):
        for path in ("root","physical_capacity","source_registry"):
            m=fixture()
            if path=="root":m["token"]="not-a-real-token"
            elif path=="physical_capacity":m["physical_capacity"]["paid_compute_authorized"]=True
            else:m["source_registry"][0]["api_key"]="not-a-real-token"
            with self.subTest(where=path),self.assertRaises(pg.Hold):
                pg.validate(m)

    def test_training_rights_are_never_self_granted(self):
        m=fixture()
        m["source_registry"][-1]["rights"]="ADMITTED_FOR_TRAINING"
        with self.assertRaises(pg.Hold):
            pg.validate(m)
        m=fixture()
        m["source_governance"]["model_outputs_promoted_to_training"]=True
        with self.assertRaises(pg.Hold):
            pg.validate(m)
        m=fixture()
        m["output_policy"]["signed_receipts"]=True
        with self.assertRaises(pg.Hold):
            pg.validate(m)

    def test_fake_5_supercomputers_cannot_promote(self):
        m=fixture()
        m["physical_capacity"]["five_unique_host_liveness_proved"]=True
        with self.assertRaisesRegex(pg.Hold,"COMPUTE_BUDGET_OR_FIVE_NODE"):
            pg.validate(m)
        m=fixture()
        m["physical_capacity"]["new_gpu_replicas_allowed"]=5
        with self.assertRaises(pg.Hold):
            pg.validate(m)

    def test_absent_formal_hypotheses_cannot_truncate_phase(self):
        m=fixture()
        m["phase_boundaries"][-1]["end_hour"]=53
        with self.assertRaises(pg.Hold):
            pg.validate(m)
        m=fixture()
        m["logical_roles"].pop()
        with self.assertRaises(pg.Hold):
            pg.validate(m)
        m=fixture()
        m["window"]["end_utc"]=(pg.START+timedelta(hours=54,seconds=28)).isoformat()
        with self.assertRaises(pg.Hold):
            pg.validate(m)

    def test_unrun_earlier_window_clocks_cannot_be_readmitted(self):
        for start,end in (("2026-11-18T05:05:32Z","2026-11-20T11:05:32Z"),
                          ("2026-11-19T10:05:32Z","2026-11-21T16:05:32Z")):
            m=fixture()
            m["window"]["start_utc"]=start
            m["window"]["end_utc"]=end
            with self.subTest(start=start),self.assertRaisesRegex(pg.Hold,"EXACT_54H_WINDOW_REQUIRED"):
                pg.validate(m)

    def test_missing_science_domain_or_duplicate_rejected(self):
        m=fixture()
        m["scientific_open_challenges"].pop()
        with self.assertRaises(pg.Hold):
            pg.validate(m)
        m=fixture()
        m["scientific_open_challenges"][-1]=m["scientific_open_challenges"][0]
        with self.assertRaises(pg.Hold):
            pg.validate(m)

    def test_raw_json_duplicate_fields_and_nan_rejected(self):
        for raw in (b'{"schema":"one","schema":"two"}',b'{"x":NaN}',
                    b" "*100001):
            with self.subTest(raw_prefix=raw[:12]),self.assertRaises(pg.Hold):
                pg.parse(raw)

    def test_clock_cannot_be_naive(self):
        with self.assertRaises(pg.Hold):
            pg.assess(fixture(),now=datetime(2026,11,18,5,5))
        with self.assertRaises(pg.Hold):
            pg._utc("2026-11-18T05:05:32")

    def test_cli_reports_hold_without_launching_a_job(self):
        p=subprocess.run([sys.executable,str(ROOT/"proving54"/"admission.py"),
                          "--manifest",str(FILE)],capture_output=True,text=True,
                         timeout=8,check=False)
        self.assertEqual(p.returncode,0,p.stderr[:600])
        doc=json.loads(p.stdout)
        self.assertEqual(doc["release_status"],"HOLD")
        self.assertFalse(doc["model_weights_trained"])
        self.assertFalse(doc["qualified_five_node_mesh"])
        self.assertEqual(doc["provider_mutations"],0)

    def test_source_has_no_external_provider_or_model_loader(self):
        text=(ROOT/"proving54"/"admission.py").read_text(encoding="utf-8")
        for forbidden in ("import requests","urllib.request","import torch",
                          "import huggingface_hub","subprocess.run(",
                          "os.system(","salad_cloud_sdk","HfApi(","shutil.rmtree("):
            self.assertNotIn(forbidden,text)

if __name__=="__main__":
    unittest.main()
