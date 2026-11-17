"""Offline-source-bound local inference probe; not proof checking or model training.

Only calls an existing loopback Ollama service. Never executes generated Lean,
downloads models, starts servers, changes weights or sends cloud requests.
Store result in a never-before-used PRIVATE path; stdout is digest-only.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import socket
import urllib.request
import urllib.error

import challenge_index as index
import putnam25_preflight as preflight

SCHEMA = "szl.putnam2025.local-model-attempt/v1"
URL = "http://127.0.0.1:11434"
SELECTED = frozenset({"putnam_2025_a1", "putnam_2025_a6",
                      "putnam_2025_b1", "putnam_2025_b2",
                      "putnam_2025_b4", "putnam_2025_b5"})
FORBIDDEN = re.compile(r"\b(sorry|admit|native_decide|unsafe|run_tac)\b|\baxiom\s+[A-Za-z_]", re.I)
MAX_RESPONSE, MAX_PROMPT, MAX_PREDICT = 1_000_000, 16_000, 384


def require(ok, why):
    if not ok:
        raise index.Hold(why)


def encode(value):
    return index.encoded(value)


def local_json(method, route, body=None, timeout=6):
    require(method in {"GET", "POST"} and route in {"/api/tags", "/api/generate"},
            "FORBIDDEN_ENDPOINT")
    data = None if body is None else encode(body)
    request = urllib.request.Request(URL + route, data=data,
        headers={"Content-Type": "application/json"}, method=method)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise index.Hold("REDIRECT_FORBIDDEN")
    opener = urllib.request.build_opener(NoRedirect, urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        require(response.status == 200 and response.geturl() == URL + route,
                "REMOTE_OR_BAD_HTTP")
        raw = response.read(MAX_RESPONSE + 1)
        return index.strict_json(raw, cap=MAX_RESPONSE)


def current_models():
    response = local_json("GET", "/api/tags")
    require(isinstance(response, dict) and isinstance(response.get("models"), list),
            "MODEL_LIST_UNAVAILABLE")
    found = {}
    for item in response["models"]:
        require(isinstance(item, dict), "MODEL_LIST_INVALID")
        name, digest = item.get("name"), item.get("digest")
        require(isinstance(name, str) and name not in found
                and isinstance(digest, str) and index.HEX64.fullmatch(digest),
                "MODEL_REVISION_UNPINNED")
        found[name] = digest
    return found


def theorem_prompt(name, raw):
    require(name in SELECTED, "PROBLEM_NOT_SELECTED")
    try:
        original = raw.decode("utf-8")
    except UnicodeError:
        raise index.Hold("INPUT_NOT_UTF8") from None
    clean = preflight.scrub_noncode(original)
    matches = list(preflight.THEOREM.finditer(clean))
    require(len(matches) == 1 and matches[0].group(1) == name, "THEOREM_IDENTITY")
    match = matches[0]
    source_prefix_clean = clean[:match.start()]
    require(preflight.SORRY.search(source_prefix_clean) is None,
            "SOURCE_CONTAINS_REFERENCE_ANSWER_PLACEHOLDER")
    stop = clean.find(":=", match.end())
    require(0 < stop - match.end() < 12000, "THEOREM_HEADER_INVALID")
    target = original[match.start():stop]
    prefix = clean[:match.start()]  # Exclude commentary and possible solution hints.
    require(("theorem " + name) in target and len(target.encode("utf-8")) <= 9000,
            "MALFORMED_TARGET")
    prompt = (
        "Independent diagnostic Lean 4 attempt. Do not edit the immutable "
        "theorem or import axioms. Provide only tactic code placed immediately "
        "after ':= by', no markdown. Do not use sorry, admit, native_decide, "
        "unsafe or external files. If unable, return exactly '-- ABSTAIN'. "
        "No answer here will be accepted without independent checking.\n\n"
        "SOURCE CONTEXT:\n" + prefix +
        "\nFROZEN THEOREM:\n" + target + " := by\nYOUR TACTICS:\n"
    )
    require(len(prompt.encode("utf-8")) <= MAX_PROMPT, "PROMPT_BUDGET")
    return prompt, index.sha256(target.encode("utf-8"))


def private_output(path: Path):
    repo = Path(__file__).resolve().parents[2]
    require(path.is_absolute() and not path.resolve().is_relative_to(repo),
            "PRIVATE_OUTPUT_OUTSIDE_REPO_REQUIRED")


def plan(catalog, source, name, model, digest):
    index.validate(catalog)
    require(name in SELECTED and isinstance(model, str) and 0 < len(model) <= 160
            and isinstance(digest, str) and index.HEX64.fullmatch(digest),
            "PLAN_IDENTITIES")
    rows = {r["id"]: r for r in catalog["entries"]
            if r["source"] == "putnambench" and r["id"] in SELECTED}
    require(name in rows, "UNPINNED_PROBLEM")
    checked = preflight.check_one(name, source, rows[name])
    require(checked["status"] == "SOURCE_BYTES_ONLY"
            and checked["unsafe_code_markers"] == 0, "SOURCE_REVIEW_HOLD")
    prompt, target_digest = theorem_prompt(name, source)
    return {"schema": "szl.putnam2025.local-model-plan/v1",
            "state": "PREPARED_NOT_SENT", "source_commit": index.PUTNAM_SHA,
            "source_blob_sha1": checked["git_blob_sha1"], "source_sha256": checked["source_sha256"],
            "catalog_sha256": index.sha256(index.encoded(catalog)),
            "case_id": name, "model_alias": model, "model_digest_declared": digest,
            "model_digest_live_verified": False, "prompt": prompt,
            "prompt_sha256": index.sha256(prompt.encode("utf-8")),
            "theorem_header_sha256": target_digest,
            "options": {"temperature": 0, "seed": 749,
                        "num_predict": MAX_PREDICT, "num_ctx": 4096},
            "inference_attempted": False, "proof_checked": False,
            "quality_score": "UNAVAILABLE", "training_authority": False,
            "provider_mutation_count": 0}


def classify(text):
    require(isinstance(text, str) and len(text.encode("utf-8")) <= 65_536,
            "RESPONSE_TEXT_LIMIT")
    s = text.strip()
    if s == "-- ABSTAIN":
        return "ABSTAIN_RECORDED"
    if not s:
        return "NO_RESPONSE"
    if FORBIDDEN.search(s):
        return "REJECTED_UNSAFE_OR_PLACEHOLDER"
    if chr(96) * 3 in s or "<think>" in s:
        return "MANUAL_EXTRACTION_REQUIRED"
    return "UNVERIFIED_PROOF_TEXT"


def probe(catalog, source, name, model, digest, *,
          infer=local_json, tags=current_models):
    index.validate(catalog)
    require(isinstance(model, str) and 0 < len(model) <= 160, "MODEL_NAME")
    require(isinstance(digest, str) and index.HEX64.fullmatch(digest),
            "MODEL_DIGEST_REQUIRED")
    by_id = {row["id"]: row for row in catalog["entries"]
             if row["source"] == "putnambench" and row["id"] in SELECTED}
    require(name in by_id, "PROBLEM_OUTSIDE_PINNED_SET")
    checked = preflight.check_one(name, source, by_id[name])
    require(checked["status"] == "SOURCE_BYTES_ONLY"
            and checked["unsafe_code_markers"] == 0, "SOURCE_REVIEW_HOLD")
    prompt, target_digest = theorem_prompt(name, source)
    require(tags().get(model) == digest, "MODEL_DIGEST_CHANGED_BEFORE")
    options = {"temperature": 0, "seed": 749, "num_predict": MAX_PREDICT,
               "num_ctx": 4096}
    start = datetime.now(timezone.utc).isoformat()
    generated = infer("POST", "/api/generate",
                      {"model": model, "prompt": prompt, "stream": False,
                       "options": options}, 120)
    end = datetime.now(timezone.utc).isoformat()
    require(tags().get(model) == digest, "MODEL_DIGEST_CHANGED_AFTER")
    require(isinstance(generated, dict) and generated.get("model") == model,
            "MODEL_RESULT_MISMATCH")
    require(generated.get("done") is True, "INCOMPLETE_MODEL_RESPONSE")
    answer = generated.get("response")
    status = classify(answer)
    metrics = {}
    for name_metric in ("prompt_eval_count", "eval_count", "total_duration"):
        value = generated.get(name_metric)
        require(value is None or (type(value) is int and value >= 0),
                "INVALID_MODEL_METRIC")
        metrics[name_metric] = value
    return {
        "schema": SCHEMA, "origin": "REAL_LOCAL_INFERENCE_UNVERIFIED",
        "model_alias": model, "model_manifest_digest": digest,
        "run_started_utc": start, "run_finished_utc": end,
        "backend": "EXISTING_OLLAMA_LOOPBACK", "service_started": False,
        "model_downloaded": False, "source_repo": "trishullab/PutnamBench",
        "source_revision": index.PUTNAM_SHA,
        "catalog_sha256": index.sha256(index.encoded(catalog)),
        "case_id": checked["problem_id"], "source_blob_sha1": checked["git_blob_sha1"],
        "source_sha256": checked["source_sha256"], "target_header_sha256": target_digest,
        "prompt_sha256": index.sha256(prompt.encode("utf-8")), "prompt": prompt,
        "response_sha256": index.sha256(answer.encode("utf-8")), "response": answer,
        "classification": status, "options": options, "metrics": metrics,
        "independent_lean_checker": "NOT_RUN", "verified_proof": False,
        "statement_equivalence": "NOT_INDEPENDENTLY_REVIEWED",
        "benchmark_contamination_review": "NOT_RUN", "quality_score": "UNAVAILABLE",
        "model_retrained": False, "publication_authority": False,
        "training_authority": False, "provider_mutation_count": 0
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--problem", choices=sorted(SELECTED), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--plan-only", action="store_true",
                        help="prepare source-bound private prompt without Ollama request")
    a = parser.parse_args()
    try:
        private_output(a.out)
        require(a.source.name == a.problem + ".lean", "SOURCE_FILENAME_MISMATCH")
        require(all(p.is_file() and not p.is_symlink() for p in (a.catalog, a.source)),
                "MISSING_INPUT")
        catalog = index.strict_json(a.catalog.read_bytes())
        with a.source.open("rb") as f:
            raw = f.read(preflight.MAX_LEAN_BYTES + 1)
        if a.plan_only:
            prepared = plan(catalog, raw, a.problem, a.model, a.digest)
            payload = encode(prepared)
            index.write_once(a.out, payload)
            print(json.dumps({
                "status": "SOURCE_BOUND_PLAN_NOT_SENT",
                "case": prepared["case_id"],
                "source_sha256": prepared["source_sha256"],
                "prompt_sha256": prepared["prompt_sha256"],
                "receipt_sha256": index.sha256(payload),
                "inference_attempted": False,
                "model_digest_live_verified": False,
                "quality_score": "UNAVAILABLE"
            }, sort_keys=True))
            return 0
        result = probe(catalog, raw, a.problem, a.model, a.digest)
        payload = encode(result)
        index.write_once(a.out, payload)
        print(json.dumps({
            "status": "REAL_LOCAL_RESPONSE_OBSERVED_NOT_PROOF",
            "model": result["model_alias"], "case": result["case_id"],
            "classification": result["classification"],
            "response_sha256": result["response_sha256"],
            "receipt_sha256": index.sha256(payload),
            "prompt_tokens": result["metrics"]["prompt_eval_count"],
            "completion_tokens": result["metrics"]["eval_count"],
            "quality_score": result["quality_score"]
        }, sort_keys=True))
        return 0
    except (index.Hold, OSError, urllib.error.URLError, socket.timeout, TimeoutError) as exc:
        reason = str(exc) if isinstance(exc, index.Hold) else type(exc).__name__
        print(json.dumps({"status": "HOLD", "reason": reason,
                          "promoted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
