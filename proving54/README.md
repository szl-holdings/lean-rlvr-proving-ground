# SZL 54-Hour Five-Role Proving Ground — Source and Admission

**Research clock (window 2):** 2026-11-19T10:05:32Z → 2026-11-21T16:05:32Z.
**SOURCE/HARD-GATE STARTED; GPU TRAINING NOT ADMITTED.**

| Window | Source clock (UTC) | Status |
|---|---|---|
| 1 | 2026-11-18T05:05:32Z → 2026-11-20T11:05:32Z | **BLOCKED.** No run was initialized during its hour zero, so 0 of 54 hourly receipts exist. It was not backfilled, replayed or restarted on a shifted clock. Its manifest stays in history at `23c9478`. |
| 2 | 2026-11-19T10:05:32Z → 2026-11-21T16:05:32Z | **HOLD_SOURCE_PROPOSAL.** A run may start only during hour zero, `[start, start + 1h)`. |

Window 1 is recorded here, not erased. At `23c9478` the CLI's `init`
accepted any time and opened a fresh 54-hour session from that moment,
outside the manifest window. The session is now bound to
`admission.START`: `init` refuses any time outside hour zero
(`INITIALIZATION_OUTSIDE_SOURCE_HOUR_ZERO`), and `tick` refuses a session
whose recorded window or bootstrap time was moved
(`SESSION_WINDOW_NOT_BOUND_TO_SOURCE`,
`SESSION_BOOTSTRAP_NOT_IN_FIRST_CLOCK_HOUR`).

This extends, without changing its authority, the preexisting
[54-hour Ouroboros curriculum](https://github.com/szl-holdings/szl-gpu-bridge/blob/5d8f6034a84fe37a4116ff9d7cb4a35f7dcbe667/docs/OUROBOROS_CURRICULUM.md):
0–24 hours constitution/Lean, 24–48 hours code/formulas/papers, 48–54 hours
proof and evaluation. Five **logical reviewer seats** are YACHAY (teacher),
KHIPU (rational oracle/receipts), LUTAR (Lean proof referee), HATUN (skeptic,
data and signer), CODEX (code/receipt builder). They can exchange structured
evidence and abstentions, but are **not five verified independent physical
supercomputers or five autonomous LLMs**.

This repository owns the existing `referee.py` + `admission.py`, core-only
`lake build`, hash-chained `chains.py`, and reviewed proof references.
Neither this folder nor the hourly steward may replace those owners with an
unreviewed model-output scorer. An unsigned chain head is **not** a signature
or a trusted proof by itself. Generated Lean must never be executed outside
a separately admitted OS-isolated, credential-free worker.

## Verified source pointers, not indiscriminate corpus ingestion

The immutable `manifest.json` references 11 GitHub **source files at
specific commit and Git blob identities** spanning:

- `lean-rlvr-proving-ground`: exact Probes.lean seed, no extra axioms.
- `szl-gpu-bridge`: 54h schedule and separate Massed/Salad reservations.
- `szl-papers`: published paper index and explicit preprint/hypothesis status.
- `lutar-lean`: **conditional** Theorem U. The reported unconditional
  Λ uniqueness is **false as stated** under A1–A5; do not upgrade it.
- `hatun-mcp`: canonical governed gateway, no retired HF publisher.
- `szl-lake`: owner-controlled receipt store; external trust-head and
  signer checks distinct from SHA256 hash consistency.
- `szl-khipu`: exact rational/Lambda examples and advisory, not proven trust.
- `szl-formulas`: source cookbook software; quarantined executable
  serialization is never loaded.
- `szl-forge`: trainer, rights, independent data and GPU-budget admission.
- `szl-router`: source-only Salad/Massed coexistence advisor, not a scheduler.
- `a11oy`: separate governed product consumer with current public GPU path
  still subject to Access and source-fencing evidence.

All source bytes are **POINTER_ONLY_NO_GRADIENTS**. The pointer list does not
declare that every repository's contents are licensed for derivatives, that
private data is allowed, or that a paper's theorem statement is proven.

The phrase **“codicies”** has no confirmed distinct canonical SZL repository
in the sampled source and is retained as an **unresolved source identity**.
No invented codex is quietly inserted into the training set. The estate-wide
GitHub census and every repository's ownership still need separately
reviewed source, privacy, licensing and split policy.

## Historical mathematics and Lean/Lake

The first-party, exact, small arithmetic witnesses below are not copied from
ancient texts, nor are they proofs of the manuscripts' historiography:

- Egyptian unit fractions and the Horus-Eye 63/64 sum, inspired by
  [the Rhind Papyrus evidence](https://www.open.edu/openlearn/science-maths-technology/mathematics-statistics/egyptian-mathematics/content-section-1.1.1).
- Concrete 3–4–5 and 5–12–13 integer squares, plus equality transitivity,
  inspired by [Euclid's Elements, Book I](https://www.euclids-elements.org/elements/books/bookI/).
- A finite two-axis Lambda-versus-max counterexample (not the full Lutar
  conditional theorem, nor a solution to an open conjecture).
- Signed-governance skepticism: missing external chain head/signer,
  source rights and incompletely sampled Salad groups must remain HOLD.

`probes/Proving54.lean` adds **10** sorry-free, core-only exact statements
as an additional default Lake target pinned to Lean 4 v4.35.0.
`lake build` checks those exact statements, not new scientific claims,
full Euclidean geometry, all of Mathlib or a model's generated proof.
The main `lutar-lean` mathlib package is separately source-owned and must
not have its locked formula membership changed by this project.

## Five real materials challenges remain OPEN

The user previously requested five Discovered Materials open-problem tracks:
cuprate superconductivity; fabrication-to-electrical interface prediction;
quantum chemistry speed/accuracy; light-driven matter; and interfacial heat
transport. Their first-party synthetic Forge task generator exists as a
candidate, **not an independent scientific solution or a runnable approved
training job**. Those tasks must not be marked PASS merely because an
LLM produced plausible text or solved a toy arithmetic question.

The available model scorecard screenshot supplies capability ideas, not
lawful training material, scores verified for SZL, or hidden benchmark keys.
Real validation requires independent source-disjoint experiments, per-family
uncertainty, source copyright/license review, and actual methods/data.

## Local five-role rehearsal

This branch's `proving54/admission.py` reads only its reviewed manifest,
checks exact 54h source/role/schedule/capacity invariants, and runs **seven
original arithmetic sanity checks** with 35 structured messages exchanged
between five simulated reviewer seats. It is a pure Python, standard-library
exercise—**not LLM training, not remote agent communication, not a GPU job**.

    python proving54/admission.py
    python -m unittest discover -s tests -p 'test_proving54_admission.py'
    lake build

The source-only command deliberately returns `release_status: HOLD`
despite passing its little math oracles. The value `five_physical_computers_running:
false` remains part of its output even if every source test is green.
No sandbox code is loaded from an untrusted document or model completion.

## One-shot 54-hour local CPU curriculum rehearsal

The source-controlled `proving54/engine.py` and `proving54/cli.py`
implement a **single-writer, bounded, entirely offline CPU-only**
rehearsal on one already-authorized operator machine. A distinct logical
YACHAY/KHIPU/LUTAR/HATUN/CODEX message is emitted for each exact
first-party test task at every admitted clock hour. A five-feature
logistic abstention policy receives real standard-library SGD updates
from **synthetic oracle labels only**, with source and token-level
confidentiality barriers. This is deliberately not a frontier-model
training job, a physical GPU mesh, a scientific generalization result,
or permission for any gradient admission in Forge.

Unlike the historical brainstorm, this runner has **one manifest**:
`proving54/manifest.json` already signed off by protected GitHub
source checks. It imports and reuses `proving54/admission.py` to reject
modified source/rights/clock/worker assertions. It never creates a
second source-policy authority, scheduler or inference endpoint.

With a fresh, reviewed source checkout and an existing private parent
directory, a responsible operator may initiate exactly one rehearsal, and
only during hour zero of the manifest window.
The CLI reads the **actual UTC clock**; it has no `--clock` spoof
switch. The pure functions accept explicit timestamps for source unit
tests only. A local run path is exclusive; existing runs are never
overwritten:

    python proving54/cli.py doctor
    python proving54/cli.py init --run /private/new-54h-rehearsal
    python proving54/cli.py tick --run /private/new-54h-rehearsal
    python proving54/cli.py status --run /private/new-54h-rehearsal

An operator may call `tick` at most once per **consecutive elapsed
UTC hour**; skipped hours, duplicate hours, source-policy drift, broken
hash chains or a live single-writer lock cause HOLD. One missed hour
ends the run: every later `tick` returns `SKIPPED_OR_DUPLICATE_HOUR`, and
the gap is never filled in afterwards. Each receipt
includes source/previous hashes and exact named tasks, but an unsigned
SHA-256 chain is **not proof of author identity**. Success in its
38 regression tests (five are POSIX-only and skipped on Windows) does not
grant model deployment authority.

**Crash and failed-commit recovery.** Window 2 runs the source pinned at
`a76fe16`, which predates this section. Writers from `a76fe16` and from
this source do not exclude each other, so never run both against one run
directory. The single-writer lock is an operating-system lock on
`.single-writer.lock` (`fcntl.flock` on POSIX, `msvcrt.locking` on
Windows) that is released when its process dies, so a killed `tick` no
longer holds every later hour. A lock file left behind is reused or
removed by the next `tick`. Never delete it by hand: on POSIX that breaks
exclusion. `status` reports `single_writer_lock_file_present`, which shows
presence, not liveness.

Before it writes an hour receipt, `tick` checks every precondition and
stages the new `state.json`, holding with `STATE_COMMIT_NOT_STAGED` if it
cannot. After the receipt, only one `os.replace` can fail, and it is
retried five times over about 1.5 s while Windows reports a sharing
violation. A failure there returns `HOUR_RECEIPT_WRITTEN_NOT_COMMITTED`
(the CLI adds `uncommitted_hour`), and a torn write returns
`HOUR_RECEIPT_WRITE_FAILED`. A leftover `state.json.temporary` is moved to
`quarantine/` under the lock, never deleted; if it cannot be moved, `tick`
holds with `ATOMIC_WRITE_CONFLICT` before writing any receipt.

The next `tick` inside the window adopts one uncommitted next-hour file
only if all of these hold:

- it is byte for byte the receipt `tick` would have written for
  `hour == hours_completed`, `previous_sha256 == chain_head_sha256` and
  the session's source digest;
- its `at_utc` lies inside that hour's slot;
- its `at_utc` is no earlier than the run's bootstrap and no later than
  the adopting `tick`'s clock.

An adopted hour is recorded in `state.json` as `adopted_hours`. When the
adopted hour is the current one, `tick` returns
`UNCOMMITTED_HOUR_ADOPTED_REVIEW_ONLY`, and a hold that follows an
adoption carries `adopted_uncommitted_hour`. Any other such file is moved
to `quarantine/` and `tick` holds with `UNCOMMITTED_HOUR_FILE_QUARANTINED`,
or with `UNCOMMITTED_HOUR_FILE_NOT_ADOPTABLE` if the file cannot be moved.
`status` reports the file as `uncommitted_hour_file` instead of failing. No
tick changes the run outside its window, so a receipt left uncommitted in
the final hour can be adopted only by a retry inside that hour.

Adoption writes no receipt, and the no-skip, no-replay, no-backfill and
hour-zero-only rules are unchanged. Under a once-per-hour schedule, a kill
before the receipt is complete still costs that hour, and therefore the
run. Receipts are unsigned and carry no run identity, so a byte-exact file
planted by someone who can write the run directory looks the same as an
interrupted tick's receipt; that writer could already edit `state.json`.
CI runs on Linux and does not exercise the Windows lock path.

The private hourly steward scheduled outside GitHub may invoke this
*one-shot* command if the authorized device is connected and the
source, budget, training and rights gates still hold; it must never
create another cron/process-loop or skip the unknown state. The
proofing clock ends after 54 hours, but this CPU exercise cannot
silently turn the five **unsolved materials** questions into solved
results, nor certify five physical supercomputers from five roles.

**Training status: NONE.** **Public release: HOLD.**

## Salad + Massed physical pool: no phantom nodes

At the last authorized Massed provider readback recorded when window 1
was written (**2026-11-18 04:51 UTC**; not refreshed for window 2),
the two named nodes were Gate1 **Stopped** and CUDA **Running**. Four
provider instances were visible, **not five verified independent healthy
compute hosts**. The approved Salad watcher was in direct-HF fallback
and did not supply a fresh complete Salad resource census. Earlier desired
or running container counts cannot establish current trainer-process health.

Five compute roles can become five *physical* workers only with **five
distinct instance identities, fresh boot/model/disk/VRAM evidence,
exclusive owners, protected ports, checkpoint durability and a reviewed
per-resource cost cap**. This project does not start/restart Gate1,
create Salad paid replicas, move workloads, install SSH keys, alter
Cloudflare tunnel/Access, weaken role controls, or expose raw GPU ports.

Live training requires the existing Forge student/dataset rights and
immutable revision acceptance, independently sealed holdout, no collision
with Flagship54's stop owner, and the separately approved GPU budget.
Self-generated "dream" output is REVIEW_REQUIRED; only independently
verified and rights-clean traces may enter a later curated curriculum.
No continual-learning update can write into production weights.

## The user's “only pass once all is answered” rule

`PASS` requires **all** of the following, not merely a clock expiry:
54 distinct elapsed hourly receipts with no skipped/duplicated hours;
source and file pins; kernel proof statements and permitted axioms;
all required questions either independently proved or explicitly
refuted by certified counterexample with no unresolved required
obligations; five real independently verified resource identities;
authorized spend/trainer owner and checkpoint backups; source-disjoint
scientific evaluation; current authenticated serving and signer/receipt
authority; owner release approval. Unknown, withheld, non-computable,
independently unverified or actually open scientific targets remain
**HOLD**. Honest abstention can be rewarded for *training behavior* but
is not a mathematical solution or a production promotion.

The window-1 hourly steward (54 occurrences through November 20, 2026)
was disabled after its hour zero passed without a run. A window-2
scheduler lives outside this repository and may call only `init` during
hour zero and at most one `tick` per hour; scheduling alone does not prove
execution, and only the hour files on the operator machine count. No
scheduler can bypass any existing trainer, budget, GPU, publisher or
service-control gate.

**Current result: source policy and arithmetic proof staging; physical
five-node mesh, actual 54-hour GPU training, solved grand challenges,
published models and fully answered closure remain UNVERIFIED/HOLD.**
