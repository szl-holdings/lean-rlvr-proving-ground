"""Pinned Putnam 2025 source-byte and theorem-header preflight.

Never runs untrusted Lean, the referee, a model or a training job. Matching a
public Git blob proves file identity, not mathematical truth or benchmark rights.
No private challenge text is printed or put into the published repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import challenge_index as index

SCHEMA = "szl.putnam2025.source-preflight/v1"
NAMES = tuple(f"putnam_2025_{group}{n}" for group in "ab" for n in range(1, 7))
MAX_LEAN_BYTES = 100_000
THEOREM = re.compile(r"\btheorem\s+([A-Za-z_][A-Za-z0-9_]*)\b")
SORRY = re.compile(r"\bsorry\b")
SOLUTION = re.compile(r"\b(?:noncomputable\s+)?abbrev\s+putnam_2025_[ab][1-6]_solution\b")
TRIVIAL = re.compile(r":\s*True\b")
AXIOM = re.compile(r"\b(?:axiom|native_decide)\b")


def require(cond: object, message: str):
    if not cond:
        raise index.Hold(message)


def scrub_noncode(text: str) -> str:
    """Remove strings, line comments and nested Lean block comments, for diagnostics only."""
    require(isinstance(text, str), "NOT_UTF8_TEXT")
    out = []
    i = 0
    depth = 0
    string = False
    while i < len(text):
        c = text[i]
        next2 = text[i:i+2]
        if depth:
            if next2 == "/-":
                depth += 1
                require(depth < 64, "NESTED_COMMENT_LIMIT")
                out.extend("  ")
                i += 2
                continue
            if next2 == "-/":
                depth -= 1
                out.extend("  ")
                i += 2
                continue
            out.append("\n" if c == "\n" else " ")
            i += 1
            continue
        if string:
            if c == "\\" and i+1 < len(text):
                out.extend("  ")
                i += 2
                continue
            if c == '"':
                string = False
            out.append("\n" if c == "\n" else " ")
            i += 1
            continue
        if next2 == "--":
            end = text.find("\n", i)
            if end == -1:
                out.extend(" " * (len(text)-i))
                i = len(text)
            else:
                out.extend(" " * (end-i))
                i = end
            continue
        if next2 == "/-":
            depth = 1
            out.extend("  ")
            i += 2
            continue
        if c == '"':
            string = True
            out.append(" ")
        else:
            out.append(c)
        i += 1
    require(depth == 0 and not string, "UNTERMINATED_COMMENT_OR_STRING")
    return "".join(out)


def git_blob_oid(blob: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(blob)).encode("ascii") + b"\0" + blob).hexdigest()


def check_one(name: str, raw: bytes, entry: dict) -> dict:
    """Require immutable source bytes and exactly the intended theorem declaration."""
    require(name in NAMES and isinstance(entry, dict) and entry.get("id") == name,
            "PROBLEM_IDENTITY")
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_LEAN_BYTES
            and type(entry.get("bytes")) is int and entry["bytes"] == len(raw),
            "SOURCE_BYTE_LENGTH")
    require(git_blob_oid(raw) == entry.get("git_blob_sha1"), "SOURCE_BLOB_MISMATCH")
    require(entry.get("evaluation_only") is True
            and entry.get("training_authority") is False
            and entry.get("truth_scope") == "SOLVED_COMPETITION_PROBLEM",
            "SOURCE_PROMOTION_FORBIDDEN")
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        raise index.Hold("SOURCE_NOT_UTF8") from None
    require("\0" not in text and "\r" not in text, "SOURCE_NONCANONICAL_BYTES")
    clean = scrub_noncode(text)
    theorems = THEOREM.findall(clean)
    require(theorems == [name], "THEOREM_TARGET_MISMATCH")
    match = THEOREM.search(clean)
    tail = clean[match.end():]
    ending = tail.find(":=")
    require(ending >= 0 and ending < 15000, "THEOREM_HEADER_UNBOUND")
    header = tail[:ending]
    require(bool(header.strip()), "EMPTY_TARGET_HEADER")
    if TRIVIAL.search(header):
        disposition = "Vacuous target: formalization review required"
        status = "TRIVIAL_TARGET_HOLD"
    else:
        disposition = "Statement equivalence not independently reviewed"
        status = "SOURCE_BYTES_ONLY"
    placeholder_count = len(SORRY.findall(clean))
    sol_count = len(SOLUTION.findall(clean))
    suspicious = len(AXIOM.findall(clean))
    if suspicious:
        status = "UNTRUSTED_AXIOM_OR_NATIVE_DECIDE_HOLD"
        disposition = "External axiom or native_decide marker requires expert review"
    return {
        "problem_id": name, "path": entry["path"], "source_commit": index.PUTNAM_SHA,
        "git_blob_sha1": entry["git_blob_sha1"], "source_bytes": len(raw),
        "source_sha256": index.sha256(raw),
        "theorem_name": name, "header_fragment_sha256": index.sha256(header.encode("utf-8")),
        "sorry_tokens_in_source": placeholder_count, "solution_abbrev_declarations": sol_count,
        "unsafe_code_markers": suspicious, "status": status,
        "formal_informal_equivalence": "NOT_INDEPENDENTLY_VERIFIED",
        "original_source_proof_executed": False,
        "student_attempt_supplied": False, "independent_proof_replayed": False,
        "qualified_score": "UNAVAILABLE", "interpretation": disposition,
    }


def evaluate(catalog: dict, source_dir: Path):
    index.validate(catalog)
    require(source_dir.is_dir() and not source_dir.is_symlink(), "SOURCE_DIRECTORY_NOT_REGULAR")
    expected = {row["id"]: row for row in catalog["entries"] if row["source"] == "putnambench"
                and row["id"] in NAMES}
    require(len(expected) == 12, "PUTNAM2025_COVERAGE_LOST")
    observed_names = {path.name for path in source_dir.glob("*.lean")}
    require(observed_names == {name + ".lean" for name in NAMES},
            "SOURCE_FILE_SET_CHANGED")
    records = []
    for name in NAMES:
        path = source_dir / (name + ".lean")
        require(path.is_file() and not path.is_symlink(), "SOURCE_LINK_OR_MISSING")
        require(not (hasattr(path, "is_junction") and path.is_junction()),
                "SOURCE_JUNCTION")
        with path.open("rb") as f:
            raw = f.read(MAX_LEAN_BYTES + 1)
        records.append(check_one(name, raw, expected[name]))
    return {
        "schema": SCHEMA, "source": "trishullab/PutnamBench",
        "source_commit": index.PUTNAM_SHA,
        "catalog_sha256": index.sha256(index.encoded(catalog)),
        "cases": len(records),
        "source_byte_integrity": "VERIFIED_GIT_BLOB_SHA1",
        "formalization_equivalence": "NOT_INDEPENDENTLY_VERIFIED",
        "student_model": "NOT_RUN", "teacher_guide_skeptic": "NOT_TRAINED_OR_RUN",
        "original_source_lean_execution": "NOT_RUN",
        "independent_proof_replay": "NOT_RUN", "qualified_math_accuracy": "UNAVAILABLE",
        "attempt_count": 0, "verified_proof_count": 0,
        "placeholder_tokens_in_sources": sum(x["sorry_tokens_in_source"] for x in records),
        "solution_abbreviations": sum(x["solution_abbrev_declarations"] for x in records),
        "heldout_contamination_review": "NOT_RUN",
        "rights_review": "NOT_RUN", "training_admission": False,
        "record_count": len(records), "records": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        require(args.catalog.is_file() and not args.catalog.is_symlink(),
                "CATALOG_UNAVAILABLE")
        catalog = index.strict_json(args.catalog.read_bytes())
        receipt = evaluate(catalog, args.source_dir)
        payload = index.encoded(receipt)
        index.write_once(args.output, payload)
        print(json.dumps({
            "state": "TWELVE_SOURCES_PINNED_NOT_SOLVED",
            "cases": receipt["cases"], "placeholders": receipt["placeholder_tokens_in_sources"],
            "solution_abbreviations": receipt["solution_abbreviations"],
            "trivial_formal_targets": sum(x["status"] == "TRIVIAL_TARGET_HOLD" for x in receipt["records"]),
            "receipt_sha256": index.sha256(args.output.read_bytes()),
            "model_test": "NOT_RUN", "math_accuracy": "UNAVAILABLE",
        }, sort_keys=True))
        return 0
    except (index.Hold, OSError) as e:
        print(json.dumps({"state": "HOLD", "reason":
                          str(e) if isinstance(e, index.Hold) else "FILESYSTEM_UNAVAILABLE"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
