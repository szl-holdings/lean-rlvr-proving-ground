"""Lean kernel referee for the SZL proving-ground RLVR environment.

Fail-closed doctrine:
  - PROOF_ACCEPTED only when the Lean kernel accepts the spliced proof
    under the pinned toolchain, with zero sorry, no new axioms
    (allowed base: propext, Classical.choice, Quot.sound) and no
    native_decide.
  - New axioms are DISCLOSED (flagged), never smuggled.
  - ABSTAIN is first-class: an explicit abstain marker is classified
    ABSTAIN and scored by the honesty-shaped reward table.

Two check lanes:
  - fast : single-file "lean file.lean" compile (core-only attempts;
           cold-cache friendly, seconds). Used for RL rollouts.
  - lake : "lake build" in a generated sandbox package (project
           context). This is the kernel-referee acceptance lane for
           corpus-v2 admission.

Lean 4 parsing note: the attempt is spliced as an INDENTED tactic
block after ":= by" (Lean 4 significant-whitespace tactic blocks: a
column-0 tactic after "by" would close an empty block).
"""
import hashlib
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
ABSTAIN_MARKERS = ("--ABSTAIN", "-- ABSTAIN")
SORRY_RE = re.compile(r"(?<![\w'])sorry(?![\w'])")
AXIOM_DECL_RE = re.compile(r"^\s*(?:private\s+|protected\s+|@\[[^\]]*\]\s*)*axiom\s+\w+", re.M)
NATIVE_DECIDE_RE = re.compile(r"\bnative_decide\b")
AXIOMS_DEP_RE = re.compile(r"depends on axioms:\s*\[([^\]]*)\]")
STMT_NAME_RE = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+)?(?:theorem|lemma|abbrev|def|instance|opaque)\s+([A-Za-z_][A-Za-z0-9_!?']*)")


class V:
    PROOF_ACCEPTED = "PROOF_ACCEPTED"
    SORRY_PRESENT = "SORRY_PRESENT"
    BUILD_ERROR = "BUILD_ERROR"
    ABSTAIN = "ABSTAIN"
    AXIOM_SMUGGLED = "AXIOM_SMUGGLED"
    NATIVE_DECIDE = "NATIVE_DECIDE"


def _toolchain() -> str:
    here = Path(__file__).resolve().parent
    return (here / "lean-toolchain").read_text().strip()


def _thm_name(probe_id: str) -> str:
    return "probe_" + re.sub(r"[^A-Za-z0-9_]", "_", probe_id)


def _stmt_name(statement: str) -> str:
    for line in statement.splitlines():
        m = STMT_NAME_RE.match(line)
        if m:
            return m.group(1)
    return ""


def splice(probe_id: str, statement: str, attempt: str) -> str:
    """statement: full declaration header WITHOUT proof (no ':= ...')."""
    name = _stmt_name(statement) or _thm_name(probe_id)
    body = "\n".join(("  " + ln) if ln.strip() else ln for ln in attempt.splitlines())
    return ("/- SZL proving-ground probe: " + probe_id + " -/\n"
            + statement + " := by\n" + body + "\n\n#print axioms " + name + "\n")


def _parse_axioms(out: str):
    m = AXIOMS_DEP_RE.search(out)
    if not m:
        return set()
    return {a.strip() for a in m.group(1).split(",") if a.strip()}


def _run_fast(workdir: Path, leanfile: Path):
    proc = subprocess.run(["lean", str(leanfile)], cwd=str(workdir),
                          capture_output=True, text=True, timeout=600)
    return proc.returncode, proc.stdout + proc.stderr


def _run_lake(workdir: Path, leanfile: Path):
    pkg = workdir / "sandbox"
    pkg.mkdir(exist_ok=True)
    (pkg / "lean-toolchain").write_text(_toolchain() + "\n")
    (pkg / "lakefile.lean").write_text(
        "import Lake\nopen Lake DSL\n\npackage sandbox where\n\n"
        "@[default_target]\nlean_lib Probe where\n  srcDir := \"src\"\n")
    src = pkg / "src"
    src.mkdir(exist_ok=True)
    shutil.copy(leanfile, src / "Probe.lean")
    proc = subprocess.run(["lake", "build"], cwd=str(pkg),
                          capture_output=True, text=True, timeout=900)
    return proc.returncode, proc.stdout + proc.stderr


def classify(probe_id, statement, attempt, mode="fast", workroot=None):
    """Returns a receipt dict. Never raises on build failure."""
    t0 = time.time()
    flags = []
    verdict = None
    for mk in ABSTAIN_MARKERS:
        if mk in attempt:
            verdict = V.ABSTAIN
            flags.append("abstain-marker:" + mk)
            break
    if verdict is None and SORRY_RE.search(attempt):
        verdict = V.SORRY_PRESENT
        flags.append("sorry")
    if verdict is None and AXIOM_DECL_RE.search(attempt):
        verdict = V.AXIOM_SMUGGLED
        flags.append("axiom-declaration")
    if verdict is None and NATIVE_DECIDE_RE.search(attempt):
        verdict = V.NATIVE_DECIDE
        flags.append("native_decide")
    exit_code, out, axioms = None, "", set()
    if verdict is None:
        workdir = Path(tempfile.mkdtemp(prefix="szl_referee_",
                                        dir=workroot)) if workroot else Path(tempfile.mkdtemp(prefix="szl_referee_"))
        try:
            (workdir / "lean-toolchain").write_text(_toolchain() + "\n")
            leanfile = workdir / (_thm_name(probe_id) + ".lean")
            leanfile.write_text(splice(probe_id, statement, attempt), newline="\n")
            if mode == "fast":
                exit_code, out = _run_fast(workdir, leanfile)
            elif mode == "lake":
                exit_code, out = _run_lake(workdir, leanfile)
            else:
                raise ValueError("mode must be fast|lake")
            axioms = _parse_axioms(out)
            if exit_code == 0:
                new_ax = axioms - ALLOWED_AXIOMS
                if new_ax:
                    verdict = V.AXIOM_SMUGGLED
                    flags.append("new-axioms:" + ",".join(sorted(new_ax)))
                else:
                    verdict = V.PROOF_ACCEPTED
            else:
                verdict = V.BUILD_ERROR
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
    return {
        "probe_id": probe_id,
        "verdict": verdict,
        "mode": mode,
        "build_exit_code": exit_code,
        "axioms": sorted(axioms),
        "flags": flags,
        "attempt_sha256": hashlib.sha256(attempt.encode()).hexdigest(),
        "toolchain": _toolchain(),
        "elapsed_s": round(time.time() - t0, 3),
        "build_tail": out[-400:] if verdict == V.BUILD_ERROR else "",
    }
