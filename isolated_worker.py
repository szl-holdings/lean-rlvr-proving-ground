#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""OS-isolated, credential-free Lean worker for untrusted rollouts.

`referee.py` runs Lean in a temporary directory, which is not a sandbox. This
module runs the same splice and axiom-report contract inside a bubblewrap
(`bwrap`) sandbox:

- every namespace unshared (no network, private PID/IPC/UTS/user/cgroup);
- `--clearenv`: no tokens, no HOME, no SSH agent, no proxy variables;
- read-only toolchain (and, for the Mathlib lane, a read-only pre-built Mathlib
  workspace); the only writable path is a per-attempt tmpfs-backed work dir;
- rlimits on CPU seconds, file size, open files and core dumps, plus a
  wall-clock timeout and `--die-with-parent`.

It fails closed. If bwrap is missing or the sandbox cannot start, the attempt
is not run unsandboxed: the receipt says BUILD_ERROR with
`isolated-worker-unavailable` and the reward is 0.

Two lanes:

- `core`: core Lean only, the same as the referee fast lane.
- `mathlib`: `import Mathlib` statements (for example lutar-lean
  `benchmark/estate_pinned_v1.jsonl` targets) checked against a pre-built,
  pinned Mathlib workspace mounted read-only. `lake` is never run inside the
  sandbox. LEAN_PATH is computed by the controller from the workspace layout.

Attempts may not contain metaprogramming or output-producing commands
(`#eval`, `run_cmd`, `elab`, `trace`, `set_option`, `import` ...), because the
axiom check still reads Lean's printed `#print axioms` report. Observations
from this worker carry `training_authority: NONE` and never enter
`admission.py` (that stays lake-lane only).
"""
from __future__ import annotations

import hashlib
import os
import re
import resource
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import referee
from referee import V

LANES = ("core", "mathlib")
VALIDATION_LEVEL = "ISOLATED_ELABORATION_WITH_TARGET_AXIOM_REPORT"
WALL_TIMEOUT_S = {"core": 120, "mathlib": 600}
CPU_LIMIT_S = {"core": 120, "mathlib": 600}
LEAN_MEMORY_MB = {"core": 2048, "mathlib": 8192}
FILE_SIZE_LIMIT = 64 * 1024 * 1024
OPEN_FILES_LIMIT = 1024
MAX_PREAMBLE_BYTES = 4096

# Anything that runs code, prints, or changes elaboration settings. The axiom
# check reads printed output, so attempts must not be able to print.
METAPROGRAM_RE = re.compile(
    r"(#eval|#print|#exit|#check|#reduce|#synth|#guard_msgs|\brun_cmd\b|\brun_tac\b"
    r"|\brun_elab\b|\bby_elab\b|\belab\b|\belab_rules\b|\bmacro\b|\bmacro_rules\b"
    r"|\bsyntax\b|\bnotation\b|\binfix[lr]?\b|\bprefix\b|\bpostfix\b"
    r"|\binitialize\b|\bbuiltin_initialize\b|\bunsafe\b|\bimplemented_by\b|@\[\s*extern"
    r"|\bextern\b|\bIO\b|\bdbg_trace\b|\bdbgTrace\b|\btrace\b|\btrace_state\b"
    r"|\blogInfo\b|\blogWarning\b|\blogError\b|\bset_option\b|\bimport\b"
    r"|\bopen\s+private\b|\battribute\b|\bderiving\s+instance\b)"
)
PREAMBLE_LINE_RE = re.compile(r"^(?:import [A-Z][A-Za-z0-9_.]*|open [A-Za-z0-9_. ]+|)$")


class WorkerUnavailable(RuntimeError):
    """The sandbox could not be established; nothing was executed."""


def _sha(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _elan_env() -> dict:
    """Minimal env for resolving the toolchain; never pass an empty ELAN_HOME."""
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "/nonexistent")}
    if os.environ.get("ELAN_HOME"):
        env["ELAN_HOME"] = os.environ["ELAN_HOME"]
    return env


def toolchain_prefix() -> Path:
    """Resolve the real toolchain directory (outside the sandbox)."""
    lean = shutil.which("lean")
    if lean is None:
        raise WorkerUnavailable("lean not found")
    # Resolve from this repo so elan honours the pinned lean-toolchain file.
    proc = subprocess.run([lean, "--print-prefix"], capture_output=True, text=True,
                          timeout=60, cwd=str(Path(__file__).resolve().parent), env=_elan_env())
    prefix = Path(proc.stdout.strip())
    if proc.returncode != 0 or not (prefix / "bin" / "lean").is_file():
        raise WorkerUnavailable("lean toolchain prefix unavailable")
    return prefix.resolve()


def mathlib_lean_path(workspace: Path) -> list[str]:
    """Sandbox-side LEAN_PATH entries for a pre-built Mathlib workspace."""
    workspace = Path(workspace)
    entries = []
    pkgs = workspace / ".lake" / "packages"
    if not (pkgs / "mathlib" / ".lake" / "build" / "lib" / "lean" / "Mathlib.olean").is_file():
        raise WorkerUnavailable("mathlib workspace has no built Mathlib.olean")
    for pkg in sorted(pkgs.iterdir()):
        lib = pkg / ".lake" / "build" / "lib" / "lean"
        if lib.is_dir():
            entries.append("/mathlib/.lake/packages/" + pkg.name + "/.lake/build/lib/lean")
    return entries


def _system_binds() -> list[str]:
    """Read-only /usr plus the host's /lib*, /bin layout (symlinked or real)."""
    argv = ["--ro-bind", "/usr", "/usr"]
    for path in ("/lib", "/lib64", "/lib32", "/bin"):
        if os.path.islink(path):
            argv += ["--symlink", os.readlink(path), path]
        elif os.path.isdir(path):
            argv += ["--ro-bind", path, path]
    return argv


def sandbox_argv(lean_args: list[str], *, toolchain: Path, workdir: Path,
                 mathlib_workspace: Path | None = None, lean_path: list[str] | None = None,
                 program: str = "/toolchain/bin/lean") -> list[str]:
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        raise WorkerUnavailable("bwrap not installed")
    argv = [bwrap, "--unshare-all", "--die-with-parent", "--new-session", "--clearenv"]
    argv += _system_binds()
    argv += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
             "--ro-bind", str(toolchain), "/toolchain",
             "--bind", str(workdir), "/work"]
    if mathlib_workspace is not None:
        argv += ["--ro-bind", str(Path(mathlib_workspace).resolve()), "/mathlib"]
    env = {"PATH": "/toolchain/bin:/usr/bin", "HOME": "/work", "LANG": "C.UTF-8"}
    if lean_path:
        env["LEAN_PATH"] = ":".join(lean_path)
    for key, value in env.items():
        argv += ["--setenv", key, value]
    argv += ["--chdir", "/work", "--", program] + list(lean_args)
    return argv


def _limits(lane: str):
    cpu = CPU_LIMIT_S[lane]

    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_SIZE_LIMIT, FILE_SIZE_LIMIT))
        resource.setrlimit(resource.RLIMIT_NOFILE, (OPEN_FILES_LIMIT, OPEN_FILES_LIMIT))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return apply


def probe_sandbox() -> bool:
    """True only if bwrap can start an all-namespaces-unshared process here."""
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        return False
    try:
        proc = subprocess.run([bwrap, "--unshare-all", "--die-with-parent", "--clearenv"]
                              + _system_binds() + ["--", "/usr/bin/true"],
                              capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def _check_preamble(lane: str, preamble: str) -> str:
    if lane == "core":
        if preamble:
            raise ValueError("the core lane takes no preamble")
        return ""
    if not isinstance(preamble, str) or len(preamble.encode("utf-8")) > MAX_PREAMBLE_BYTES:
        raise ValueError("preamble must be a bounded string")
    lines = preamble.splitlines()
    if not lines or lines[0] != "import Mathlib" or any(not PREAMBLE_LINE_RE.match(l) for l in lines):
        raise ValueError("mathlib preamble must start with 'import Mathlib' and hold only import/open lines")
    return preamble.rstrip("\n") + "\n\n"


def classify(probe_id: str, statement: str, attempt: str, lane: str = "core", *,
             preamble: str = "", mathlib_workspace: str | os.PathLike | None = None,
             workroot: str | os.PathLike | None = None) -> dict:
    """Classify one attempt inside the sandbox. Returns a referee-shaped receipt."""
    start = time.monotonic()
    if lane not in LANES:
        raise ValueError("lane must be core|mathlib")
    for value in (probe_id, statement, attempt):
        if not isinstance(value, str) or len(value.encode("utf-8")) > referee.MAX_INPUT_BYTES:
            raise ValueError("probe inputs must be bounded UTF-8 strings")
    if not probe_id.strip() or not statement.strip():
        raise ValueError("probe identity and trusted statement are required")
    if lane == "mathlib" and mathlib_workspace is None:
        raise ValueError("the mathlib lane needs a pre-built mathlib workspace")
    header = _check_preamble(lane, preamble)
    target = referee._stmt_name(statement)
    source = header + referee.splice(probe_id, statement, attempt)
    flags: list[str] = []
    verdict = None

    # Same abstention and lexical contract as referee.classify.
    directive = attempt.strip()
    marker = next((m for m in referee.ABSTAIN_MARKERS
                   if "\n" not in directive and "\r" not in directive
                   and (directive == m or directive.startswith(m + " "))), None)
    if marker is not None:
        if referee.ABSTAIN_FORBIDDEN_RE.search(directive[len(marker):]):
            verdict, flags = V.BUILD_ERROR, ["abstain-explanation-forbidden-token"]
        else:
            verdict, flags = V.ABSTAIN, ["abstain-marker:" + marker]
    if verdict is None and referee.SORRY_RE.search(attempt):
        verdict, flags = V.SORRY_PRESENT, ["sorry"]
    if verdict is None and referee.AXIOM_DECL_RE.search(attempt):
        verdict, flags = V.AXIOM_SMUGGLED, ["axiom-declaration"]
    if verdict is None and referee.NATIVE_DECIDE_RE.search(attempt):
        verdict, flags = V.NATIVE_DECIDE, ["native_decide"]
    if verdict is None and METAPROGRAM_RE.search(attempt):
        verdict, flags = V.BUILD_ERROR, ["metaprogram-forbidden"]
    if verdict is None and not target:
        verdict, flags = V.BUILD_ERROR, ["target-declaration-unavailable"]

    exit_code, output, axioms = None, "", set()
    evidence, isolation = "NOT_OBSERVED", "NOT_RUN"
    if verdict is None:
        workdir = None
        try:
            toolchain = toolchain_prefix()
            lean_path = None
            if lane == "mathlib":
                lean_path = mathlib_lean_path(Path(mathlib_workspace))
                lean_path.append("/toolchain/lib/lean")
            workdir = Path(tempfile.mkdtemp(prefix="szl_isolated_", dir=workroot))
            (workdir / "Attempt.lean").write_text(source, encoding="utf-8", newline="\n")
            argv = sandbox_argv(["-j1", "-M" + str(LEAN_MEMORY_MB[lane]), "Attempt.lean"],
                                toolchain=toolchain, workdir=workdir,
                                mathlib_workspace=Path(mathlib_workspace) if lane == "mathlib" else None,
                                lean_path=lean_path)
            proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=WALL_TIMEOUT_S[lane],
                                  preexec_fn=_limits(lane), env={}, cwd=str(workdir))
            exit_code, output = proc.returncode, proc.stdout + proc.stderr
            isolation = "BWRAP_ALL_NAMESPACES_CLEARENV"
            if exit_code != 0:
                verdict = V.BUILD_ERROR
                if "bwrap:" in output:
                    flags = ["isolated-worker-unavailable"]
                    isolation = "FAILED_TO_START"
            else:
                try:
                    axioms = referee._parse_axioms(output, target)
                except ValueError:
                    verdict, flags = V.BUILD_ERROR, ["target-axiom-evidence-unavailable"]
                else:
                    evidence = "TARGET_BOUND_REPORT"
                    unexpected = axioms - referee.ALLOWED_AXIOMS
                    if unexpected:
                        verdict, flags = V.AXIOM_SMUGGLED, ["new-axioms:" + ",".join(sorted(unexpected))]
                    else:
                        verdict = V.PROOF_ACCEPTED
        except WorkerUnavailable as exc:
            verdict, flags = V.BUILD_ERROR, ["isolated-worker-unavailable", str(exc)]
        except subprocess.TimeoutExpired:
            verdict, flags = V.BUILD_ERROR, ["build-timeout"]
        except (OSError, UnicodeError):
            verdict, flags = V.BUILD_ERROR, ["build-infrastructure-unavailable"]
        finally:
            if workdir is not None:
                shutil.rmtree(workdir, ignore_errors=True)
    return {
        "probe_id": probe_id, "verdict": verdict, "mode": "isolated-" + lane,
        "build_exit_code": exit_code, "axioms": sorted(axioms), "flags": flags,
        "statement_declaration": target,
        "statement_sha256": _sha(statement), "attempt_sha256": _sha(attempt),
        "preamble_sha256": _sha(preamble), "spliced_source_sha256": _sha(source),
        "build_output_sha256": _sha(output),
        "referee_source_sha256": hashlib.sha256(Path(referee.__file__).read_bytes()).hexdigest(),
        "worker_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "axiom_evidence": evidence, "validation_level": VALIDATION_LEVEL,
        "isolation": isolation, "independent_checker": "NOT_RUN", "training_authority": "NONE",
        "toolchain": referee._toolchain(), "elapsed_s": round(time.monotonic() - start, 3),
        "build_tail": output[-400:] if verdict == V.BUILD_ERROR else "",
    }
