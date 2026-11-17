"""Offline, fail-closed hard-math source index and non-qualifying challenge receipts.

There is no network, model invocation, Lean execution, training or publishing here.
Github tree inputs must be obtained from the pre-approved exact commits below.
Tree records are public *filenames and Git blob identities*, never problem text.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

SCHEMA = "szl.proving-ground.hard-problem-catalog/v1"
RESULT_SCHEMA = "szl.proving-ground.hard-problem-observation/v1"
PUTNAM_SHA = "a635813f5edf297d928f9bd5ef8324a26bdde09c"
CONJECTURE_SHA = "6751c0f043985ac6647db28a45a63afdf21acffe"
EXPECTED_ENTRIES_SHA256 = "977ae9e8e7b8ad6aed83085c0e789bf210c429b65932bf61749f8ca74b5c4091"
# The exact raw GitHub tree-response bytes are pinned separately from Git's
# commit/blob SHA-1. A different snapshot needs reviewed code and new evidence.
SOURCES = (
    ("putnambench", "trishullab/PutnamBench", PUTNAM_SHA,
     re.compile(r"lean4/src/(putnam_(?:19|20)[0-9]{2}_[ab][1-9][0-9]?)\.lean\Z"),
     "COMPETITION_THEOREM_FORMALIZATION", "SOLVED_COMPETITION_PROBLEM",
     "d7014b5682758e2af29c10c0752f8d1cc0e0af9a45672eeea1b9b1ce30c15e19"),
    ("formal_conjectures", "google-deepmind/formal-conjectures", CONJECTURE_SHA,
     re.compile(r"FormalConjectures/(.+)\.lean\Z"),
     "RESEARCH_CONJECTURE_FORMALIZATION", "MATHEMATICAL_STATUS_NOT_INDEPENDENTLY_VERIFIED",
     "2ae45d32624f701bf0f9412e163d4b81800f5eb3cb8bec9058396186b92f66ce"),
)
CAP_TREE = 8000
CAP_CATALOG = 4000
MAX_INPUT = 3_000_000
MAX_SUBMISSIONS = 256
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[a-z0-9:_-]{3,90}\Z")
ACTIONS = frozenset({"ABSTAIN", "CLAIM_PROOF", "CLAIM_REFUTATION", "EXPLORATORY", "NO_ANSWER"})
# Open-question descriptions are pointers, not an authoritative open-status snapshot.
RESEARCH_TARGETS = (
    ("riemann-hypothesis", "Riemann hypothesis"),
    ("p-vs-np", "P versus NP"),
    ("navier-stokes", "Navier-Stokes existence and smoothness"),
    ("birch-swinnerton-dyer", "Birch and Swinnerton-Dyer"),
    ("yang-mills-mass-gap", "Yang-Mills existence and mass gap"),
    ("hodge-conjecture", "Hodge conjecture"),
    ("collatz", "Collatz conjecture"),
    ("goldbach", "Strong Goldbach conjecture"),
    ("twin-primes", "Twin prime conjecture"),
    ("legendres-primes", "Legendre prime-gap conjecture"),
)


class Hold(ValueError):
    """Only fixed nonsecret failure reasons are emitted."""


def require(ok: object, reason: str) -> None:
    if not ok:
        raise Hold(reason)


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def encoded(obj: object) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True,
                       allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def strict_json(raw: bytes, cap: int = MAX_INPUT):
    require(isinstance(raw, bytes) and 0 < len(raw) <= cap, "INPUT_SIZE")
    # PowerShell 5's UTF-8 output includes a BOM; the hash still binds exact bytes.
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "DUPLICATE_JSON_MEMBER")
            out[key] = value
        return out
    def no_nan(_):
        raise Hold("NONFINITE_JSON")
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs,
                          parse_constant=no_nan)
    except (UnicodeError, ValueError) as err:
        if isinstance(err, Hold):
            raise
        raise Hold("INVALID_JSON") from None


def check_path(value: str, prefix: str) -> None:
    require(isinstance(value, str) and len(value.encode("utf-8")) < 240, "UNSAFE_PATH")
    p = PurePosixPath(value)
    require(not p.is_absolute() and str(p) == value and len(p.parts) > 2
            and p.parts[0] == prefix and "\\" not in value
            and all(part not in ("", ".", "..") for part in p.parts), "UNSAFE_PATH")


def extract_tree(raw: bytes, config: tuple):
    key, repo, ref, pattern, kind, truth, expected_raw_digest = config
    require(sha256(raw) == expected_raw_digest, "SOURCE_SNAPSHOT_DIGEST_CHANGED")
    tree = strict_json(raw)
    require(isinstance(tree, dict) and tree.get("truncated") is False
            and isinstance(tree.get("tree"), list) and 1 <= len(tree["tree"]) <= CAP_TREE,
            "TREE_INCOMPLETE_OR_CAPPED")
    require(isinstance(tree.get("sha"), str) and tree["sha"] == ref
            and HEX40.fullmatch(tree["sha"]), "TREE_IDENTITY_NOT_PINNED")
    source = {"key": key, "repository": repo, "requested_revision": ref,
              "returned_tree_sha": tree["sha"], "source_json_sha256": sha256(raw),
              "total_git_tree_entries": len(tree["tree"]),
              "materialized_problem_text": False,
              "rights_clearance": "NOT_PERFORMED", "provider": "GITHUB_PUBLIC"}
    rows = []
    seen = set()
    for entry in tree["tree"]:
        require(isinstance(entry, dict), "BAD_TREE_ENTRY")
        path = entry.get("path")
        if not isinstance(path, str):
            raise Hold("INVALID_TREE_PATH")
        match = pattern.fullmatch(path)
        if not match:
            continue
        check_path(path, "lean4" if key == "putnambench" else "FormalConjectures")
        require(entry.get("type") == "blob" and entry.get("mode") == "100644",
                "UNSAFE_BLOB_MODE")
        oid = entry.get("sha")
        size = entry.get("size")
        require(isinstance(oid, str) and HEX40.fullmatch(oid)
                and type(size) is int and 0 < size < 1_000_000,
                "INVALID_BLOB_IDENTITY")
        require(path not in seen, "DUPLICATE_PATH")
        seen.add(path)
        item_id = match.group(1) if key == "putnambench" else "fc-" + sha256(path.encode())[:24]
        rows.append({"id": item_id, "source": key, "path": path, "git_blob_sha1": oid,
                     "bytes": size, "task": kind, "truth_scope": truth,
                     "evaluation_only": True, "training_authority": False,
                     "problem_text_included": False})
    rows.sort(key=lambda row: row["path"])
    require(bool(rows) and len(rows) <= CAP_CATALOG, "INDEX_EMPTY_OR_CAPPED")
    source["indexed_count"] = len(rows)
    return source, rows


def build(putnam_raw: bytes, conjecture_raw: bytes):
    records = [extract_tree(raw, source) for raw, source in
               zip((putnam_raw, conjecture_raw), SOURCES, strict=True)]
    sources, lists = zip(*records, strict=True)
    combined = sorted((item for seq in lists for item in seq),
                      key=lambda item: (item["source"], item["path"]))
    require(len(combined) <= CAP_CATALOG, "INDEX_TOO_LARGE")
    board = [{"id": ref, "name": name, "source_url": "https://openqed.org/",
              "scope": "RESEARCH_TARGET_NOT_AN_INDEPENDENT_STATUS_CERTIFICATE",
              "statement_proved_here": False, "model_solved": False,
              "evaluation_only": True, "training_authority": False}
             for ref, name in RESEARCH_TARGETS]
    counts = {"putnambench_lean": len(lists[0]),
              "formal_conjectures_statement_files": len(lists[1]),
              "total_file_pointers": len(combined),
              "putnam_2025": sum(row["id"].startswith("putnam_2025_") for row in lists[0]),
              "curated_research_targets": len(board)}
    payload = {"schema": SCHEMA, "status": "INDEX_ONLY_NOT_A_MODEL_TEST",
               "source_revisions": list(sources), "counts": counts,
               "entries_sha256": sha256(encoded(combined)),
               "entries": combined, "research_target_board": board,
               "holds": {"dataset_rights_reviewed": False,
                         "informal_statement_equivalence_checked": False,
                         "heldout_decontamination_completed": False,
                         "model_weights_loaded": False, "formal_conjecture_status_verified": False,
                         "any_lean_code_executed": False, "training_admitted": False,
                         "training_started": False, "model_quality_evaluated": False,
                         "automated_promotion_allowed": False},
               "scope": "Pinned public source Git-tree metadata only; no statements, answers or proof terms"}
    validate(payload)
    return payload


def validate(catalog: dict):
    require(isinstance(catalog, dict) and catalog.get("schema") == SCHEMA,
            "CATALOG_SCHEMA")
    require(catalog.get("status") == "INDEX_ONLY_NOT_A_MODEL_TEST", "FALSE_STATUS")
    refs = catalog.get("source_revisions")
    require(isinstance(refs, list) and len(refs) == len(SOURCES), "SOURCE_COUNT")
    for actual, required in zip(refs, SOURCES, strict=True):
        require(isinstance(actual, dict)
                and actual.get("key") == required[0]
                and actual.get("repository") == required[1]
                and actual.get("requested_revision") == required[2]
                and isinstance(actual.get("returned_tree_sha"), str)
                and HEX40.fullmatch(actual["returned_tree_sha"])
                and actual.get("returned_tree_sha") == required[2]
                and actual.get("source_json_sha256") == required[6]
                and actual.get("materialized_problem_text") is False
                and actual.get("rights_clearance") == "NOT_PERFORMED", "SOURCE_BINDING")
    rows = catalog.get("entries")
    require(isinstance(rows, list) and 1 <= len(rows) <= CAP_CATALOG,
            "ENTRIES_EMPTY_OR_CAPPED")
    require(catalog.get("entries_sha256") == EXPECTED_ENTRIES_SHA256
            and sha256(encoded(rows)) == EXPECTED_ENTRIES_SHA256,
            "ENTRY_DIGEST_CHANGED_OR_UNPINNED")
    require(rows == sorted(rows, key=lambda row: (row["source"], row["path"])),
            "ORDER_DRIFT")
    ids, pathids = set(), set()
    counts = {"putnambench": 0, "formal_conjectures": 0}
    putnam_2025 = 0
    for item in rows:
        require(isinstance(item, dict) and item.get("source") in counts,
                "INVALID_ENTRY")
        source = next(v for v in SOURCES if v[0] == item["source"])
        path = item.get("path")
        require(isinstance(path, str) and source[3].fullmatch(path) is not None,
                "PATH_NOT_IN_SOURCE")
        check_path(path, "lean4" if source[0] == "putnambench" else "FormalConjectures")
        oid = item.get("git_blob_sha1")
        require(isinstance(oid, str) and HEX40.fullmatch(oid)
                and type(item.get("bytes")) is int and 0 < item["bytes"] < 1_000_000,
                "INVALID_FILE_IDENTITY")
        identity = source[3].fullmatch(path).group(1) if source[0] == "putnambench" else "fc-" + sha256(path.encode())[:24]
        require(item.get("id") == identity and item["id"] not in ids
                and (item["source"], path) not in pathids, "ENTRY_IDENTITY")
        require(item.get("evaluation_only") is True
                and item.get("training_authority") is False
                and item.get("problem_text_included") is False
                and item.get("task") == source[4]
                and item.get("truth_scope") == source[5], "PROBLEM_AUTHORITY")
        ids.add(item["id"])
        pathids.add((item["source"], path))
        counts[item["source"]] += 1
        putnam_2025 += int(item["id"].startswith("putnam_2025_"))
    summary = catalog.get("counts")
    require(isinstance(summary, dict)
            and summary.get("putnambench_lean") == counts["putnambench"]
            and summary.get("formal_conjectures_statement_files") == counts["formal_conjectures"]
            and summary.get("total_file_pointers") == len(rows)
            and summary.get("putnam_2025") == putnam_2025,
            "CATALOG_DENOMINATOR")
    require(all(ref.get("indexed_count") == counts[ref["key"]] for ref in refs),
            "SOURCE_COUNT_DRIFT")
    board = catalog.get("research_target_board")
    require(isinstance(board, list) and len(board) == len(RESEARCH_TARGETS),
            "RESEARCH_TARGET_COUNT")
    for item, expected in zip(board, RESEARCH_TARGETS, strict=True):
        require(item.get("id") == expected[0] and item.get("name") == expected[1]
                and item.get("source_url") == "https://openqed.org/"
                and item.get("scope") == "RESEARCH_TARGET_NOT_AN_INDEPENDENT_STATUS_CERTIFICATE"
                and item.get("statement_proved_here") is False
                and item.get("model_solved") is False
                and item.get("evaluation_only") is True
                and item.get("training_authority") is False,
                "OPEN_STATUS_MISREPRESENTED")
    holds = catalog.get("holds")
    require(isinstance(holds, dict) and len(holds) == 10
            and all(value is False for value in holds.values()), "UNAPPROVED_GATE")
    return {"state": "SOURCE_METADATA_INDEX_VERIFIED", **summary,
            "model_training": "NOT_RUN", "independent_proof_replay": "NOT_RUN"}


def observe(catalog: dict, raw: bytes):
    validate(catalog)
    result = strict_json(raw, cap=256_000)
    require(isinstance(result, dict) and result.get("schema") == "szl.proving-ground.challenge-submissions/v1",
            "SUBMISSIONS_SCHEMA")
    require(result.get("origin") in {"SYNTHETIC_CONTROL", "MODEL_RESPONSES_UNVERIFIED"},
            "SUBMISSION_ORIGIN")
    if result["origin"] == "MODEL_RESPONSES_UNVERIFIED":
        revision = result.get("model_revision")
        require(isinstance(revision, str) and HEX40.fullmatch(revision),
                "MODEL_NOT_IMMUTABLY_BOUND")
    else:
        require(result.get("model_revision") is None, "SYNTHETIC_CLAIMED_MODEL")
    submissions = result.get("submissions")
    require(isinstance(submissions, list) and 1 <= len(submissions) <= MAX_SUBMISSIONS,
            "SUBMISSION_BATCH_CAP")
    by_id = {x["id"]: x for x in catalog["entries"]}
    seen, observations = set(), []
    for row in submissions:
        require(isinstance(row, dict) and set(row) == {"id", "action", "text"}, "SUBMISSION_FIELDS")
        pid, action, content = row["id"], row["action"], row["text"]
        require(isinstance(pid, str) and pid in by_id and pid not in seen,
                "UNKNOWN_OR_DUPLICATE_PROBLEM")
        require(isinstance(action, str) and action in ACTIONS
                and isinstance(content, str)
                and len(content.encode("utf-8")) <= 16_384, "SUBMISSION_CONTENT")
        if action in {"NO_ANSWER", "ABSTAIN"}:
            require(not content, "ABSTENTION_MUST_NOT_CONTAIN_PROOF")
        if action == "CLAIM_PROOF":
            require(bool(content.strip()), "EMPTY_PROOF_CLAIM")
        seen.add(pid)
        status = {
            "NO_ANSWER": "UNOBSERVED_SOLVER_OUTPUT",
            "ABSTAIN": "ABSTENTION_RECORDED_NOT_SOLUTION",
            "CLAIM_PROOF": "UNVERIFIED_PROOF_CLAIM",
            "CLAIM_REFUTATION": "UNVERIFIED_REFUTATION_CLAIM",
            "EXPLORATORY": "EXPLORATORY_NOT_A_PROOF",
        }[action]
        if action == "CLAIM_PROOF" and re.search(r"\b(sorry|admit|native_decide)\b", content):
            status = "REJECTED_PLACEHOLDER_NOT_PROOF"
        observations.append({"id": pid, "source": by_id[pid]["source"],
                             "action": action, "status": status,
                             "content_sha256": sha256(content.encode("utf-8")),
                             "content_bytes": len(content.encode("utf-8")),
                             "independent_checker": "NOT_RUN",
                             "mathematical_result": "NOT_ESTABLISHED"})
    attempted = len(observations)
    abstained = sum(x["action"] == "ABSTAIN" for x in observations)
    claims = sum(x["action"] in {"CLAIM_PROOF", "CLAIM_REFUTATION"} for x in observations)
    source_counts = {key: sum(x["source"] == key for x in observations) for key in
                     ("putnambench", "formal_conjectures")}
    return {"schema": RESULT_SCHEMA, "source_catalog_sha256": sha256(encoded(catalog)),
            "origin": result["origin"], "model_revision": result.get("model_revision"),
            "measured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "attempts": attempted, "abstentions": abstained, "claims_not_verified": claims,
            "source_counts": source_counts,
            "reported_abstention_fraction": abstained / attempted if attempted else None,
            "independent_correctness": "UNAVAILABLE",
            "qualified_proofs": 0, "qualified_success_rate": "UNAVAILABLE",
            "training": "NOT_RUN", "artifacts_modified": False, "promotion_allowed": False,
            "observations": observations}


def write_once(path: Path, payload: bytes) -> None:
    require(path.is_absolute() and not path.exists() and not path.is_symlink(),
            "OUTPUT_EXISTS_OR_NONABSOLUTE")
    require(path.parent.is_dir() and not path.parent.is_symlink(), "OUTPUT_PARENT")
    # Exclusive creation: no existing writer state is overwritten.
    with path.open("xb") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    require(path.read_bytes() == payload, "OUTPUT_READBACK_FAILED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="op", required=True)
    b = subs.add_parser("build")
    b.add_argument("--putnam-tree", type=Path, required=True)
    b.add_argument("--conjectures-tree", type=Path, required=True)
    b.add_argument("--output", type=Path, required=True)
    v = subs.add_parser("validate")
    v.add_argument("--catalog", type=Path, required=True)
    e = subs.add_parser("observe")
    e.add_argument("--catalog", type=Path, required=True)
    e.add_argument("--submissions", type=Path, required=True)
    e.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.op == "build":
            obj = build(args.putnam_tree.read_bytes(), args.conjectures_tree.read_bytes())
            write_once(args.output, encoded(obj))
            response = {"state": "PUBLIC_POINTER_INDEX_WRITTEN",
                        "output_sha256": sha256(args.output.read_bytes()),
                        **obj["counts"], "proofs_executed": 0, "model_tests_run": 0}
        else:
            catalog = strict_json(args.catalog.read_bytes())
            if args.op == "validate":
                response = validate(catalog)
            else:
                measured = observe(catalog, args.submissions.read_bytes())
                write_once(args.output, encoded(measured))
                response = {"state": "SYNTHETIC_OR_MODEL_OUTPUT_CLASSIFIED_ONLY",
                            "receipt_sha256": sha256(args.output.read_bytes()),
                            "attempts": measured["attempts"],
                            "qualified_success_rate": measured["qualified_success_rate"],
                            "origin": measured["origin"]}
        print(json.dumps(response, sort_keys=True))
    except (Hold, OSError) as err:
        print(json.dumps({"state": "HOLD",
                          "reason": str(err) if isinstance(err, Hold) else "FILESYSTEM_UNAVAILABLE",
                          "actions_retried": False}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
