"""SZL 54-hour research proving ground, stdlib-only local five-role harness.

Each tick is one *local CPU* rehearsal of five deterministic reviewer roles:
YACHAY teacher, KHIPU exact oracle, LUTAR bounded formal gate, HATUN skeptic,
CODEX receipt builder. It is NOT five GPUs, autonomous general intelligence,
trained frontier weights, independent research, or a deployed model mesh.

No model imports, network, dangerous subprocess execution, provider secrets,
training on third-party papers or official benchmark/test examples. Actual
GPU/Salad jobs remain subject to separate Forge launch and budget admission.
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

from proving54 import admission as approved_source

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "manifest.json"
SCHEMA = "szl.proving54-local-five-role-episode/v1"
SESSION_SCHEMA = "szl.proving54-session/v1"
START_SCHEMA = "szl.proving54-bootstrap/v1"
TASK_CLASSES = ("FOUNDATION", "SKILLS", "PROOF")
ROLE_NAMES = ("YACHAY", "KHIPU", "LUTAR", "HATUN", "CODEX")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
TASKS = (
    ("EGYPT-HORUS", "FOUNDATION", "Egyptian fractions"),
    ("EGYPT-RHIND-2-5", "FOUNDATION", "Egyptian fractions"),
    ("EGYPT-RHIND-2-7", "FOUNDATION", "Egyptian fractions"),
    ("EGYPT-RHIND-2-13", "FOUNDATION", "Egyptian fractions"),
    ("GREEK-345", "FOUNDATION", "Greek geometry"),
    ("GREEK-51213", "FOUNDATION", "Greek geometry"),
    ("GREEK-EQUALITY", "FOUNDATION", "Greek common notions"),
    ("LUTAR-PERMUTATION", "FOUNDATION", "Λ advisory math"),
    ("LUTAR-COUNTEREXAMPLE", "FOUNDATION", "Conjecture 1 false-as-stated"),
    ("KHIPU-CHAIN-TAMPER", "SKILLS", "unsigned hash chain"),
    ("HATUN-UNSIGNED", "SKILLS", "missing origin signer"),
    ("LAKE-NO-HEAD", "SKILLS", "unknown trusted chain head"),
    ("PAPERS-CONJECTURE", "SKILLS", "conditional theorem boundary"),
    ("CODICIES-UNRESOLVED", "SKILLS", "unknown requested source"),
    ("SCIENCE-CUPRATE", "SKILLS", "open research"),
    ("SCIENCE-INTERFACE", "SKILLS", "open research"),
    ("SCIENCE-QUANTUM", "SKILLS", "open research"),
    ("SCIENCE-DRIVEN", "SKILLS", "open research"),
    ("SCIENCE-HEAT", "SKILLS", "open research"),
)
TOY_PREFIX = ("EGYPT-", "GREEK-", "LUTAR-", "KHIPU-")
CLAIM_STATES = (
    "VERIFIED_SYNTHETIC",
    "EXPECTED_SAFETY_HOLD",
    "OPEN_EVIDENCE_REQUIRED",
    "UNOBSERVED_SOURCE",
)
STATE_FLOORS = (
    "NO_EXTERNAL_RIGHTS",
    "NOT_SALAD_AUTHORIZED",
    "NOT_FIVE_GPUS",
    "INDEPENDENT_EVAL_UNOBSERVED",
    "UNSIGNED_OWNERSHIP",
)
MAX_RAW = 100_000


class Hold(ValueError):
    """Stable fail-closed reason, no untrusted provider errors or secrets."""


def require(flag: bool, reason: str) -> None:
    if not flag:
        raise Hold(reason)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def packed(obj: object) -> bytes:
    return (
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def strict_load(raw: bytes) -> Any:
    require(type(raw) is bytes and len(raw) <= MAX_RAW, "JSON_BYTES_BUDGET")

    def pairs(kv):
        result = {}
        for key, value in kv:
            if key in result:
                raise Hold("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(Hold("JSON_NONFINITE")),
        )
    except (ValueError, UnicodeError) as e:
        if isinstance(e, Hold):
            raise
        raise Hold("INVALID_JSON_UTF8") from None


def utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        out = value
    elif isinstance(value, str):
        try:
            out = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise Hold("INVALID_TIMESTAMP") from None
    else:
        raise Hold("TIMESTAMP_TYPE")
    require(out.tzinfo is not None and out.utcoffset() is not None, "NAIVE_TIMESTAMP")
    return out.astimezone(timezone.utc)


def registry() -> dict:
    """Validate one merged, source-pinned manifest. Never create a second authority."""
    raw = REGISTRY.read_bytes()
    record = approved_source.parse(raw)
    approved_source.validate(record)
    return {
        "hours": record["window"]["duration_hours"],
        "roles": record["logical_roles"],
        "sources": record["source_registry"],
        "training_authority": "NONE",
        "five_physical_supercomputers_proved": False,
    }


def integer_result(task: str) -> tuple[str, dict]:
    """Original tiny instances; history links are context, not proof."""
    if task == "EGYPT-HORUS":
        observed = sum((Fraction(1, d) for d in (2, 4, 8, 16, 32, 64)), Fraction(0))
        require(observed == Fraction(63, 64), "EGYPT_HORUS_ORACLE")
        return "VERIFIED_SYNTHETIC", {
            "rational_result": "63/64",
            "claim": "Cleared fraction arithmetic, not a manuscript proof",
        }
    if task.startswith("EGYPT-RHIND"):
        refs = {
            "EGYPT-RHIND-2-5": (Fraction(2, 5), (Fraction(1, 3), Fraction(1, 15))),
            "EGYPT-RHIND-2-7": (Fraction(2, 7), (Fraction(1, 4), Fraction(1, 28))),
            "EGYPT-RHIND-2-13": (
                Fraction(2, 13),
                (Fraction(1, 8), Fraction(1, 52), Fraction(1, 104)),
            ),
        }
        target, parts = refs[task]
        require(
            len(parts) == len(set(parts))
            and all(x.numerator == 1 for x in parts)
            and sum(parts, Fraction(0)) == target,
            "EGYPT_FRACTION_ORACLE",
        )
        return "VERIFIED_SYNTHETIC", {
            "target": str(target),
            "unit_fractions": [str(x) for x in parts],
            "claim": "Original exact test of unit-fraction identity, not a copied papyrus solution",
        }
    if task in ("GREEK-345", "GREEK-51213"):
        a, b, c = (3, 4, 5) if task == "GREEK-345" else (5, 12, 13)
        require(a * a + b * b == c * c, "GREEK_PYTHAGOREAN_INSTANCE")
        return "VERIFIED_SYNTHETIC", {
            "sides": [a, b, c],
            "claim": "Finite integer-square instance, not a proof of all Euclidean geometry",
        }
    if task == "GREEK-EQUALITY":
        a = b = c = 17
        require(a == b and b == c and a == c, "EQUALITY_TRANSITIVITY_ORACLE")
        return "VERIFIED_SYNTHETIC", {
            "rule": "transitivity",
            "claim": "Concrete equality, general theorem requires its own kernel certificate",
        }
    if task == "LUTAR-PERMUTATION":
        a, b = 1, 4
        geom = math.isqrt(a * b)
        require(
            geom * geom == a * b and geom == math.isqrt(b * a),
            "LAMBDA_PERMUTATION_ORACLE",
        )
        return "VERIFIED_SYNTHETIC", {
            "axes": [a, b],
            "lambda_exact": geom,
            "claim": "Equal-weight instance, not proof of unconditional uniqueness",
        }
    if task == "LUTAR-COUNTEREXAMPLE":
        a, b = 1, 4
        val = math.isqrt(a * b)
        require(
            val * val == a * b and val != max(a, b), "FALSE_UNIQUENESS_COUNTEREXAMPLE"
        )
        return "VERIFIED_SYNTHETIC", {
            "lambda": val,
            "alternative_max": max(a, b),
            "claim": "Unconditional equality false at witness; Theorem U remains conditional",
        }
    if task == "KHIPU-CHAIN-TAMPER":
        start = b"GENESIS"
        p1 = b"toy-record-one"
        p2 = b"toy-record-two"
        head1 = sha256(start + b"\x00" + p1).digest()
        head2 = sha256(head1 + b"\x00" + p2).hexdigest()
        altered = sha256(
            sha256(start + b"\x00" + b"forged-one").digest() + b"\x00" + p2
        ).hexdigest()
        require(head2 != altered, "KNOT_TAMPER_COUNTEREXAMPLE")
        return "VERIFIED_SYNTHETIC", {
            "chain_head_sha256": head2,
            "tampered_head_differs": True,
            "claim": "Unsigned hash-link observation; no issuer authenticity or historical rollback proof",
        }
    raise Hold("NOT_A_NUMERIC_TASK")


def oracle(task: str) -> tuple[str, dict]:
    if task.startswith(TOY_PREFIX):
        return integer_result(task)
    if task in ("HATUN-UNSIGNED", "LAKE-NO-HEAD", "PAPERS-CONJECTURE"):
        reason = {
            "HATUN-UNSIGNED": "No verified DSSE signer and authenticated gateway origin",
            "LAKE-NO-HEAD": "No externally trusted signed chain head; empty chain is not signed provenance",
            "PAPERS-CONJECTURE": "Unconditional Λ-uniqueness false as stated; only conditional Theorem U is claimed",
        }[task]
        return "EXPECTED_SAFETY_HOLD", {
            "reason": reason,
            "claim": "Abstention/correct boundary, not a completed third-party system proof",
        }
    if task == "CODICIES-UNRESOLVED":
        return "UNOBSERVED_SOURCE", {
            "reason": "User said codicies, no exact canonical codex/codices repository was found",
            "claim": "Source identity must be supplied or independently resolved",
        }
    if task.startswith("SCIENCE-"):
        return "OPEN_EVIDENCE_REQUIRED", {
            "reason": "Independent scientific implementation, data rights and external physical evaluation missing",
            "claim": "A toy arithmetic curriculum does not solve the five open materials challenges",
        }
    raise Hold("UNKNOWN_TASK_ID")


def phase(hour: int) -> str:
    require(type(hour) is int and 0 <= hour < 54, "HOUR_OUT_OF_RANGE")
    if hour < 24:
        return "FOUNDATION"
    if hour < 48:
        return "SKILLS"
    return "PROOF"


def phase_tasks(hour: int) -> tuple[str, ...]:
    focus = phase(hour)
    if focus == "FOUNDATION":
        return tuple(t[0] for t in TASKS if t[1] == "FOUNDATION")
    if focus == "SKILLS":
        return tuple(t[0] for t in TASKS if t[1] == "SKILLS")
    return tuple(t[0] for t in TASKS)


def _prob(z: float) -> float:
    # Numerical stability and no non-finite state.
    require(math.isfinite(z) and abs(z) < 100, "POLICY_LOGIT_BUDGET")
    return 1 / (1 + math.exp(-z))


def features(task: str) -> tuple[float, ...]:
    # Exactly 5 bounded synthetic features: intercept; arithmetic;
    # formalizable/finite; external evidence; source ambiguity.
    is_numeric = task.startswith(TOY_PREFIX)
    return (
        1.0,
        float(is_numeric),
        float(task.startswith(("GREEK-", "LUTAR-", "EGYPT-"))),
        float(task.startswith("SCIENCE-")),
        float(task == "CODICIES-UNRESOLVED"),
    )


def micro_train(
    weights: list[float], tasks: tuple[str, ...]
) -> tuple[list[float], dict]:
    """One authentic CPU SGD update of a TOY abstention classifier only.

    Labels are derived from our exact toy oracle, never from a benchmark, model
    rollout, private research paper, or scientific truth. Evaluation is
    in-sample; no inference/generalization claim. No trained LLM weights.
    """
    require(
        type(weights) is list
        and len(weights) == 5
        and all(
            type(v) is float and math.isfinite(v) and -8 <= v <= 8 for v in weights
        ),
        "CPU_POLICY_WEIGHT_SHAPE",
    )
    new = list(weights)
    eps = 1e-12
    before = after = 0.0
    for task in tasks:
        x = features(task)
        label = 1.0 if oracle(task)[0] == "VERIFIED_SYNTHETIC" else 0.0
        p = _prob(sum(w * v for w, v in zip(new, x)))
        before += -(
            label * math.log(max(p, eps)) + (1 - label) * math.log(max(1 - p, eps))
        )
        for i in range(5):
            new[i] = max(-8.0, min(8.0, new[i] - 0.05 * (p - label) * x[i]))
        q = _prob(sum(w * v for w, v in zip(new, x)))
        after += -(
            label * math.log(max(q, eps)) + (1 - label) * math.log(max(1 - q, eps))
        )
    return new, {
        "iterations": len(tasks),
        "toy_loss_before_online_total": round(before, 8),
        "toy_loss_after_online_total": round(after, 8),
        "model_family": "FIVE_FEATURE_CPU_LOGISTIC_TOY_ONLY",
        "out_of_distribution_science_accuracy": "UNOBSERVED",
        "third_party_benchmark_performance": "UNOBSERVED",
        "existing_llm_weights_touched": False,
    }


def episode(hour: int, prior_weights: list[float]) -> dict:
    chosen = phase_tasks(hour)
    results = []
    messages = []
    for task in chosen:
        verdict, evidence = oracle(task)
        safe = verdict == "VERIFIED_SYNTHETIC"
        results.append({"task": task, "status": verdict, "evidence": evidence})
        # Five distinctly attributed structured communications per task;
        # no unaudited LLM agents, free-form generated requests or plugins.
        observations = (
            ("YACHAY", "TASK_ASSIGNED", "first-party curriculum"),
            (
                "KHIPU",
                "ORACLE_MEASURED" if safe else "ORACLE_NOT_APPLICABLE",
                "exact rational/integer toy" if safe else "no verified numeric answer",
            ),
            (
                "LUTAR",
                "ARITHMETIC_CHECK_ONLY" if safe else "NO_KERNEL_PROOF",
                "separate source-pinned lake build remains required",
            ),
            (
                "HATUN",
                "REVIEWABLE_TOY" if safe else "BLOCK_UNVERIFIED",
                "do not promote unknown science to a pass",
            ),
            ("CODEX", "RECEIPT_CANDIDATE", "no code execution, no source write"),
        )
        for role, state, boundary in observations:
            messages.append(
                {
                    "role": role,
                    "task": task,
                    "state": state,
                    "boundary": boundary,
                    "model_agent_executed": False,
                }
            )
    update, learning = micro_train(prior_weights, chosen)
    return {
        "schema": SCHEMA,
        "hour": hour,
        "phase": phase(hour),
        "logical_roles": list(ROLE_NAMES),
        "scientific_task_count": len(results),
        "role_messages": messages,
        "task_results": results,
        "verified_toy_count": sum(x["status"] == "VERIFIED_SYNTHETIC" for x in results),
        "requires_external_count": sum(
            x["status"] != "VERIFIED_SYNTHETIC" for x in results
        ),
        "toy_cpu_learning": learning,
        "next_toy_cpu_policy_weights": update,
        "training_backend": "STDLIB_CPU_ONLY",
        "gpu_training_started": False,
        "salad_jobs_created": 0,
        "massed_service_changes": 0,
        "model_weights_published": False,
        "all_questions_answered": False,
        "physical_supercomputers_verified": 0,
        "experimental_release_authorized": False,
        "science_generalization_proved": False,
    }


def source_git_head() -> dict:
    cwd = ROOT.parent
    try:
        p = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=6,
        )
        sha = p.stdout.strip() if p.returncode == 0 else None
        return {
            "head": sha if sha and HEX40.fullmatch(sha) else None,
            "verified_against_remote": False,
        }
    except (OSError, subprocess.TimeoutExpired):
        return {"head": None, "verified_against_remote": False}


def fresh_session(now: datetime, *, source_digest: str) -> dict:
    at = utc(now)
    return {
        "schema": SESSION_SCHEMA,
        "started_at_utc": at.isoformat(),
        "expires_at_utc": (at + timedelta(hours=54)).isoformat(),
        "phase": "FOUNDATION",
        "hours_completed": 0,
        "last_hour": -1,
        "chain_head_sha256": None,
        "source_registry_sha256": source_digest,
        "source_git": source_git_head(),
        "toy_cpu_policy_weights": [0.0] * 5,
        "training_authority": "NONE",
        "salad_new_jobs": 0,
        "massed_new_services": 0,
        "five_physical_computers_verified": False,
        "all_scientific_challenges_answered": False,
        "production_admission": "HOLD",
        "signed": False,
    }


def _read_session(path: Path) -> dict:
    s = strict_load(path.read_bytes())
    require(isinstance(s, dict) and s.get("schema") == SESSION_SCHEMA, "SESSION_SCHEMA")
    require(
        s.get("source_registry_sha256") == digest(REGISTRY.read_bytes()),
        "SOURCE_REGISTRY_DRIFT",
    )
    require(
        s.get("training_authority") == "NONE" and s.get("signed") is False,
        "UNAUTHORIZED_SESSION_PROMOTION",
    )
    return s


def init_run(output_dir: Path, now: datetime) -> dict:
    registry()
    output_dir = Path(output_dir)
    require(
        output_dir.is_absolute()
        and output_dir.parent.is_dir()
        and not output_dir.exists()
        and not output_dir.is_symlink()
        and not output_dir.parent.is_symlink()
        and not output_dir.resolve().is_relative_to(ROOT.parent.resolve()),
        "PRIVATE_NEW_OUTPUT_REQUIRED",
    )
    staging = Path(tempfile.mkdtemp(prefix=".szl-proving54-", dir=output_dir.parent))
    try:
        state = fresh_session(now, source_digest=digest(REGISTRY.read_bytes()))
        first = {
            "schema": START_SCHEMA,
            "time": state["started_at_utc"],
            "window_end": state["expires_at_utc"],
            "logical_roles": list(ROLE_NAMES),
            "source_registry_sha256": state["source_registry_sha256"],
            "source_git": state["source_git"],
            "source_trainable": False,
            "gpu_resources_allocated": 0,
            "salad_scheduled_jobs": 0,
            "receipt_signature": "NOT_PRESENT",
            "state": "LOCAL_REVIEW_WINDOW_STARTED",
        }
        (staging / "source_registry.json").write_bytes(REGISTRY.read_bytes())
        (staging / "bootstrap.json").write_bytes(packed(first))
        (staging / "state.json").write_bytes(packed(state))
        (staging / "hours").mkdir()
        os.replace(staging, output_dir)
        return first
    finally:
        if staging.exists():
            import shutil

            shutil.rmtree(staging)


def _read_events(root: Path, state: dict) -> list:
    hour_dir = root / "hours"
    files = sorted(hour_dir.glob("hour-*.json"))
    require(len(files) == state["hours_completed"], "HOUR_FILE_COUNT_MISMATCH")
    prev = None
    result = []
    for h, p in enumerate(files):
        record = strict_load(p.read_bytes())
        require(
            record.get("hour") == h
            and record.get("previous_sha256") == prev
            and record.get("schema") == "szl.proving54-hour-record/v1",
            "LEDGER_PARENT_OR_HOUR_MISMATCH",
        )
        prev = digest(p.read_bytes())
        result.append(record)
    require(prev == state["chain_head_sha256"], "TRUSTED_SESSION_HEAD_MISMATCH")
    return result


def _atomic_write(path: Path, bytestring: bytes) -> None:
    temp = path.with_name(path.name + ".temporary")
    require(not temp.exists(), "ATOMIC_WRITE_CONFLICT")
    with temp.open("xb") as stream:
        stream.write(bytestring)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def tick(root: Path, now: datetime) -> dict:
    """Exactly one hourly local CPU step, with an exclusive single writer."""
    root = Path(root)
    current = utc(now)
    require(
        root.is_dir() and (root / "bootstrap.json").is_file(), "RUN_NOT_INITIALIZED"
    )
    require(
        digest((root / "source_registry.json").read_bytes())
        == digest(REGISTRY.read_bytes()),
        "RUN_COPY_SOURCE_DRIFT",
    )
    lock = root / ".single-writer.lock"
    try:
        with lock.open("xb") as f:
            f.write(current.isoformat().encode())
    except FileExistsError:
        raise Hold("ANOTHER_WORKER_OWNS_THIS_RUN") from None
    try:
        state = _read_session(root / "state.json")
        _read_events(root, state)
        start = utc(state["started_at_utc"])
        deadline = utc(state["expires_at_utc"])
        require(start <= current < deadline, "OUTSIDE_54H_WINDOW")
        slot = int((current - start).total_seconds() // 3600)
        require(0 <= slot < 54, "HOUR_OUTSIDE_WINDOW")
        require(slot == state["hours_completed"], "SKIPPED_OR_DUPLICATE_HOUR")
        ev = episode(slot, state["toy_cpu_policy_weights"])
        record = {
            "schema": "szl.proving54-hour-record/v1",
            "hour": slot,
            "at_utc": current.isoformat(),
            "phase": ev["phase"],
            "previous_sha256": state["chain_head_sha256"],
            "source_registry_sha256": state["source_registry_sha256"],
            "episode": ev,
            "all_tasks_fully_answered": False,
            "model_promoted": False,
            "physical_mesh_validated": False,
            "signed": False,
        }
        data = packed(record)
        path = root / "hours" / f"hour-{slot:02d}.json"
        with path.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        state["chain_head_sha256"] = digest(data)
        state["hours_completed"] = slot + 1
        state["last_hour"] = slot
        state["phase"] = ev["phase"]
        state["toy_cpu_policy_weights"] = ev["next_toy_cpu_policy_weights"]
        _atomic_write(root / "state.json", packed(state))
        return {
            "state": "HOUR_RECORDED_REVIEW_ONLY",
            "hour": slot,
            "phase": ev["phase"],
            "role_messages": len(ev["role_messages"]),
            "verified_toy_count": ev["verified_toy_count"],
            "needs_external_evidence_count": ev["requires_external_count"],
            "toy_policy_sgd_updates": ev["toy_cpu_learning"]["iterations"],
            "hours_recorded": state["hours_completed"],
            "chain_head_sha256": state["chain_head_sha256"],
            "gpu_jobs_started": 0,
            "deployment_authorized": False,
        }
    finally:
        if lock.exists():
            lock.unlink()


def status(root: Path, now: datetime) -> dict:
    s = _read_session(Path(root) / "state.json")
    events = _read_events(Path(root), s)
    elapsed = max(0, (utc(now) - utc(s["started_at_utc"])).total_seconds() / 3600)
    unresolved = sorted(
        {
            x["task"]
            for e in events
            for x in e["episode"]["task_results"]
            if x["status"] != "VERIFIED_SYNTHETIC"
        }
    )
    all_seen = {x["task"] for e in events for x in e["episode"]["task_results"]}
    return {
        "schema": "szl.proving54-readback/v1",
        "hours_recorded": s["hours_completed"],
        "elapsed_hours": round(elapsed, 2),
        "required_hours": 54,
        "all_required_tasks_observed": len(all_seen) == len(TASKS),
        "known_unresolved_tasks": unresolved,
        "all_required_fully_answered": False
        if unresolved or len(all_seen) < len(TASKS)
        else True,
        "release_status": "HOLD"
        if (
            elapsed < 54
            or s["hours_completed"] < 54
            or unresolved
            or not s["five_physical_computers_verified"]
        )
        else "HOLD_EXTERNAL_GATES",
        "five_roles_messaged_per_case": all(
            len(e["episode"]["role_messages"]) == 5 * len(e["episode"]["task_results"])
            for e in events
        ),
        "physical_supercomputers_verified": False,
        "operator_approved_gpu_spend": False,
        "signed_receipts": False,
        "source_registry_digest": s["source_registry_sha256"],
        "chain_head_sha256": s["chain_head_sha256"],
        "model_training_executed": False,
        "toy_cpu_calibration_updates": sum(
            e["episode"]["toy_cpu_learning"]["iterations"] for e in events
        ),
    }
