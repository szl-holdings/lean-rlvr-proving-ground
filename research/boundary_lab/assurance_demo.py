"""Execute offline support, evaluator and fixed-verifier diagnostics in a new folder."""
from pathlib import Path
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
import platform
import boundary_lab as base
import evaluation_contract as ec
from support_memory import SupportMemory, ZERO
from verifier_search import run_search


def source(key, *, tenant="research", expires_at=2000):
    return {"op": "source", "id": key, "tenant": tenant, "revision": "a"*40,
            "content_sha256": sha256(key.encode()).hexdigest(), "expires_at": expires_at, "read_allowed": True}


def claim(key, supports):
    return {**source(key), "op":"claim", "supports":supports}


def memory_demo(path):
    m = SupportMemory(path)
    allow = lambda principal, tenant, operation: principal == "research-controller" and tenant == "research"
    first = m.apply([source("A"), source("B"), claim("only_A", [["A"]]),
                     claim("either", [["A"], ["B"]]), claim("both", [["A", "B"]]),
                     claim("downstream", [["either"]])], expected_head=ZERO,
                    principal="research-controller", authorize=allow)
    before = m.handles(tenant="research", principal="research-controller", now=1000, authorize=allow)
    second = m.apply([{"op":"withdraw","tenant":"research","id":"A","reason":"REVOKED"}],
                     expected_head=first, principal="research-controller", authorize=allow)
    after_one = m.handles(tenant="research", principal="research-controller", now=1000, authorize=allow)
    m.apply([{"op":"withdraw","tenant":"research","id":"B","reason":"SUPERSEDED"}, source("B-new")],
            expected_head=second, principal="research-controller", authorize=allow)
    after_both = m.handles(tenant="research", principal="research-controller", now=1000, authorize=allow)
    states = lambda view: {x["id"]:x["support_state"] for x in view["handles"]}
    assert states(after_one)["either"] == "SUPPORTED" and states(after_one)["only_A"] == "UNSUPPORTED"
    assert states(after_one)["both"] == "UNSUPPORTED" and states(after_one)["downstream"] == "SUPPORTED"
    assert states(after_both)["either"] == "UNSUPPORTED" and states(after_both)["B-new"] == "SUPPORTED"
    result = {"before": before, "after_A_revocation": after_one, "after_B_supersession": after_both,
              "history_event_count": m.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
              "history_deleted": False, "real_brain_data_loaded": False}
    m.close()
    return result


def fixture_cases():
    return [{"id":r["id"],"family":r["generator_family"],
             "expected":"SUPPORTED" if r["runtime_property_holds_in_this_finite_scenario"] else "UNSUPPORTED",
             "task_sha256":r["task_fingerprint"]} for r in base.make_cases()]


def grading_negative_control():
    plan = ec.frozen_plan(fixture_cases(), model_digest="1"*64, tokenizer_digest="2"*64,
                          grader_digest=sha256(Path(ec.__file__).read_bytes()).hexdigest())
    rows = [{"arm":a,"case_id":c["id"],"seed":s,"status":"OK","decision":"UNKNOWN",
             "input_tokens":100,"output_tokens":1,"model_digest":plan["model_digest"],
             "task_sha256":c["task_sha256"]} for a in ec.ARMS for c in plan["cases"] for s in plan["seeds"]]
    result = ec.score(plan, rows, expected_plan_sha256=ec.digest(plan))
    assert all(x["supported_answer_accuracy"] == 0 for x in result["arms"].values())
    incomplete = ec.score(plan, rows[:-1], expected_plan_sha256=ec.digest(plan))
    assert incomplete["arms"]["D"]["unsupported_acceptance_rate"] is None
    return {"synthetic_control_not_model_run":True,"always_unknown":result,"one_attempt_removed":incomplete}


def run(out):
    out.mkdir(parents=True, exist_ok=False)
    payloads = {"support-memory.json": memory_demo(out/"synthetic-support.sqlite"),
                "evaluation-negative-controls.json": grading_negative_control(),
                "verifier-search.json":run_search()}
    for name, value in payloads.items():
        (out/name).write_bytes(base.canonical(value))
    # Handles-only, review-required projection; no existing Brain/Hatun/Anatomy writer is touched.
    projection = {"schema":"szl.boundary-review-projection/v0.2", "status":"REVIEW_REQUIRED",
                  "evidence":[{"name":name,"sha256":sha256((out/name).read_bytes()).hexdigest()} for name in payloads],
                  "capabilities":{"execution":False,"training":False,"promotion":False},
                  "deployed_to":[],"raw_memory_content":False}
    (out/"review-projection.json").write_bytes(base.canonical(projection))
    receipt = {"schema":"szl.boundary-assurance-run/v0.2","observed_at_utc":datetime.now(timezone.utc).isoformat(),
               "python":platform.python_version(),"platform":platform.platform(),
               "source_sha256":{p.name:sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))},
               "outputs":{p.name:{"bytes":p.stat().st_size,"sha256":sha256(p.read_bytes()).hexdigest()} for p in sorted(out.glob('*')) if p.is_file()},
               "model_inference_calls":0,"training_runs":0,"production_mutations":0,"independent_validation":False}
    (out/"run-receipt.json").write_bytes(base.canonical(receipt))
    return receipt


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.out),indent=2))
