"""Bounded Lean elaboration and target-bound axiom reporting.

The caller supplies a trusted statement registry. Unreviewed generated Lean
must run in an OS-isolated, credential-free worker: a temporary directory is
NOT a security sandbox. This module does not provide independent proof replay,
semantic equivalence with an informal claim, or production/training authority.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
ABSTAIN_MARKERS = ("--ABSTAIN", "-- ABSTAIN")
ABSTAIN_FORBIDDEN_RE = re.compile(r"\b(?:sorry|axiom|native_decide)\b", re.I)
SORRY_RE = re.compile(r"(?<![\w'])sorry(?![\w'])")
AXIOM_DECL_RE = re.compile(r"^\s*(?:private\s+|protected\s+|@\[[^\]]*\]\s*)*axiom\s+\w+", re.M)
NATIVE_DECIDE_RE = re.compile(r"\bnative_decide\b")
STMT_NAME_RE = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+)?(?:theorem|lemma|abbrev|def|instance|opaque)\s+([A-Za-z_][A-Za-z0-9_.!?']*)")
AXIOM_REPORT_RE = re.compile(
    r"'([^'\r\n]+)'\s+(?:does not depend on any axioms|depends on axioms:\s*\[([^\]]*)\])"
)
MAX_INPUT_BYTES = 128 * 1024
VALIDATION_LEVEL = "ELABORATION_WITH_TARGET_AXIOM_REPORT"


class V:
    PROOF_ACCEPTED = "PROOF_ACCEPTED"
    SORRY_PRESENT = "SORRY_PRESENT"
    BUILD_ERROR = "BUILD_ERROR"
    ABSTAIN = "ABSTAIN"
    AXIOM_SMUGGLED = "AXIOM_SMUGGLED"
    NATIVE_DECIDE = "NATIVE_DECIDE"


def _toolchain() -> str:
    return (Path(__file__).resolve().parent / "lean-toolchain").read_text(encoding="utf-8").strip()


def _thm_name(probe_id: str) -> str:
    return "probe_" + re.sub(r"[^A-Za-z0-9_]", "_", probe_id)


def _stmt_name(statement: str) -> str:
    for line in statement.splitlines():
        match = STMT_NAME_RE.match(line)
        if match:
            return match.group(1)
    return ""


def splice(probe_id: str, statement: str, attempt: str) -> str:
    """Append the attempt to a controller-owned declaration header."""
    name = _stmt_name(statement) or _thm_name(probe_id)
    body = "\n".join(("  " + line) if line.strip() else line for line in attempt.splitlines())
    # Do not interpolate arbitrary identifiers into a comment delimiter.
    return ("/- SZL proving-ground probe " + _thm_name(probe_id) + " -/\n"
            + statement + " := by\n" + body + "\n\n#print axioms " + name + "\n")


def _parse_axioms(output: str, target_name: str) -> set[str]:
    """Require exactly one explicit report for the requested declaration.

    A missing, malformed, unrelated or duplicated report is not evidence of
    an empty dependency set. This parser is not resistant to malicious Lean
    metaprograms forging output; independent checker isolation remains required.
    """
    matches = [m for m in AXIOM_REPORT_RE.finditer(output) if m.group(1) == target_name]
    if not target_name or len(matches) != 1:
        raise ValueError("target axiom report is missing or ambiguous")
    body = matches[0].group(2)
    if body is None or not body.strip():
        return set()
    values = [value.strip() for value in body.split(",")]
    if (any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.!?']*", value) for value in values)
            or len(set(values)) != len(values)):
        raise ValueError("target axiom report is malformed")
    return set(values)


def _run_fast(workdir: Path, leanfile: Path):
    proc = subprocess.run(["lean", "-j1", "-M2048", str(leanfile)], cwd=workdir,
                          capture_output=True, text=True, encoding="utf-8", timeout=600)
    return proc.returncode, proc.stdout + proc.stderr


def _run_lake(workdir: Path, leanfile: Path):
    pkg = workdir / "sandbox"
    pkg.mkdir()
    (pkg / "lean-toolchain").write_text(_toolchain() + "\n", encoding="utf-8")
    (pkg / "lakefile.lean").write_text(
        "import Lake\nopen Lake DSL\n\npackage sandbox where\n\n"
        "@[default_target]\nlean_lib Probe where\n  srcDir := \"src\"\n",
        encoding="utf-8")
    src = pkg / "src"
    src.mkdir()
    shutil.copyfile(leanfile, src / "Probe.lean")
    proc = subprocess.run(["lake", "build"], cwd=pkg, capture_output=True,
                          text=True, encoding="utf-8", timeout=900)
    return proc.returncode, proc.stdout + proc.stderr


def classify(probe_id, statement, attempt, mode="fast", workroot=None):
    """Return an observation receipt; expected build failures fail closed.

    PROOF_ACCEPTED preserves the legacy verdict name. Its precise assurance is
    VALIDATION_LEVEL, not independent checking or permission to train a model.
    """
    start = time.monotonic()
    if mode not in {"fast", "lake"}:
        raise ValueError("mode must be fast|lake")
    for value in (probe_id, statement, attempt):
        if not isinstance(value, str) or len(value.encode("utf-8")) > MAX_INPUT_BYTES:
            raise ValueError("probe inputs must be bounded UTF-8 strings")
    if not probe_id.strip() or not statement.strip():
        raise ValueError("probe identity and trusted statement are required")
    target = _stmt_name(statement)
    source = splice(probe_id, statement, attempt)
    flags = []
    verdict = None
    # An abstention is one standalone comment line, optionally with a
    # same-line explanation. A marker embedded in Lean code or a multiline
    # attempt must not short-circuit sorry/axiom/referee checks.
    directive = attempt.strip()
    marker = next(
        (m for m in ABSTAIN_MARKERS
         if "\n" not in directive and "\r" not in directive
         and (directive == m or directive.startswith(m + " "))),
        None,
    )
    if marker is not None:
        # Explanations containing forbidden proof tokens cannot earn credit.
        # Reject as malformed before invoking the Lean executor.
        if ABSTAIN_FORBIDDEN_RE.search(directive[len(marker):]):
            verdict, flags = V.BUILD_ERROR, ["abstain-explanation-forbidden-token"]
        else:
            verdict = V.ABSTAIN
            flags.append("abstain-marker:" + marker)
    if verdict is None and SORRY_RE.search(attempt):
        verdict, flags = V.SORRY_PRESENT, ["sorry"]
    if verdict is None and AXIOM_DECL_RE.search(attempt):
        verdict, flags = V.AXIOM_SMUGGLED, ["axiom-declaration"]
    if verdict is None and NATIVE_DECIDE_RE.search(attempt):
        verdict, flags = V.NATIVE_DECIDE, ["native_decide"]
    exit_code, output, axioms = None, "", set()
    evidence = "NOT_OBSERVED"
    if verdict is None and not target:
        verdict, flags = V.BUILD_ERROR, ["target-declaration-unavailable"]
    if verdict is None:
        workdir = None
        try:
            workdir = Path(tempfile.mkdtemp(prefix="szl_referee_", dir=workroot))
            (workdir / "lean-toolchain").write_text(_toolchain() + "\n", encoding="utf-8")
            leanfile = workdir / (_thm_name(probe_id) + ".lean")
            leanfile.write_text(source, encoding="utf-8", newline="\n")
            exit_code, output = (_run_fast if mode == "fast" else _run_lake)(workdir, leanfile)
            if exit_code != 0:
                verdict = V.BUILD_ERROR
            else:
                try:
                    axioms = _parse_axioms(output, target)
                except ValueError:
                    verdict, flags = V.BUILD_ERROR, ["target-axiom-evidence-unavailable"]
                else:
                    evidence = "TARGET_BOUND_REPORT"
                    unexpected = axioms - ALLOWED_AXIOMS
                    if unexpected:
                        verdict, flags = V.AXIOM_SMUGGLED, ["new-axioms:" + ",".join(sorted(unexpected))]
                    else:
                        verdict = V.PROOF_ACCEPTED
        except subprocess.TimeoutExpired:
            verdict, flags = V.BUILD_ERROR, ["build-timeout"]
        except (OSError, UnicodeError):
            verdict, flags = V.BUILD_ERROR, ["build-infrastructure-unavailable"]
        finally:
            if workdir is not None:
                shutil.rmtree(workdir, ignore_errors=True)
    return {
        "probe_id": probe_id, "verdict": verdict, "mode": mode,
        "build_exit_code": exit_code, "axioms": sorted(axioms), "flags": flags,
        "statement_declaration": target,
        "statement_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
        "attempt_sha256": hashlib.sha256(attempt.encode("utf-8")).hexdigest(),
        "spliced_source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "build_output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "referee_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "axiom_evidence": evidence, "validation_level": VALIDATION_LEVEL,
        "independent_checker": "NOT_RUN", "training_authority": "NONE",
        "toolchain": _toolchain(), "elapsed_s": round(time.monotonic() - start, 3),
        "build_tail": output[-400:] if verdict == V.BUILD_ERROR else "",
    }
