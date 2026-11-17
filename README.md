# lean-rlvr-proving-ground

**Lean-compile-as-reward RLVR environment for the SZL proving ground — the self-generating corpus flywheel.**

Estate artifact, fail-closed. Merge to protected mains is owner-gated. Nothing in this repo authorizes a launch.

## Current assurance boundary: review references, not training approval

`PROOF_ACCEPTED` is the legacy verdict name for **elaboration plus exactly one
axiom report bound to the requested declaration**. Missing, unrelated, duplicate
or malformed reports are rejected. The receipt binds the trusted statement,
spliced source, attempt, referee implementation and build output by SHA-256.
This is not independent proof replay, semantic validation of an informal claim,
or permission to train, publish or execute a model.

`admission.admit` now requires an exact, separately trusted `expected_chain_head`
and the controller-owned statement registry. It validates the entire hash chain,
source identities, statement binding, toolchain, successful lake lane and allowed
axioms before staging a new immutable **REVIEW_REQUIRED** reference generation.
Legacy receipts missing those fields must be replayed. Fast-lane observations
never enter this corpus. An empty eligible set is unavailable, not a pass.
The references point to attempt receipts, not proof bodies; a separate replayable
proof store is still required before training-data promotion.

**Untrusted Lean must run in an OS-isolated, credential-free worker.** A temporary
directory is not a security sandbox, and parsing a printed report is not resistant
to arbitrary metaprograms forging output. Independent checking and trusted
statement comparison remain separate required controls. This patch does not
qualify the referee as a hostile-code execution service.

For Flagship55, use the reviewed source/assumption/negative-control records as
curriculum candidates only. Keep axioms as assumptions, conjectures as open or
refuted-as-stated claims, and examples as examples. Preserve the locked-eight
membership and exact theorem hypotheses. Do not change running Flagship54 or
admit the private Brain graph to gradients. No budget or launch gate is changed.

See Lean's official [proof-validation guidance](https://lean-lang.org/doc/reference/latest/ValidatingProofs/).

## What this is

The recorded frontier pattern, built: **generate → Lean kernel referees → train only on accepted traces.** A model attempts proofs of the proving-ground atlas probes; the local elaboration/report observation — not an LLM judge — supplies the provisional reward:

| attempt class | verdict | reward |
| --- | --- | --- |
| sorry-free lake-build-accepted proof, allowed axioms only | PROOF_ACCEPTED | **1.0** |
| explicit ABSTAIN on a CONJECTURE-class probe | ABSTAIN | **0.5** (honesty-shaped partial; Conjectures 1–3 are the anchors) |
| explicit ABSTAIN on a formalizable probe | ABSTAIN | 0.1 |
| sorry left in, build error, native_decide | SORRY_PRESENT / BUILD_ERROR / NATIVE_DECIDE | 0.0 |
| new axiom declared or smuggled | AXIOM_SMUGGLED | 0.0, **flagged, never silent** |

Allowed axiom base: propext, Classical.choice, Quot.sound. Anything else is disclosed and rejected.

## Pipeline

1. **referee.py** — splices an attempt into the probe's pinned-toolchain Lean statement and runs two check lanes:
   - fast: single-file kernel compile (core-only proofs, cold-cache seconds) — the RL rollout lane;
   - lake: "lake build" in a generated sandbox package — **the kernel-referee acceptance lane**.
2. **rewards.py** — the honesty-shaped reward table above.
3. **chains.py** — append-only, hash-chained attempt receipts (chains/attempts.jsonl); every entry carries its sha256 and the previous entry's sha256. Tamper-evident. (Khipu/DSSE signature attachment is a recorded follow-up.)
4. **admission.py** — stages only target-bound lake-lane observation references after complete chain validation. These are REVIEW_REQUIRED references, not proof bodies or a training-approved corpus. `stage_review.py` provides the pinned offline caller.
5. **grpo_adapter.py** — bounded text-only provisional reward adapter. Full-batch validation preserves one reward per completion; conversation-shaped trainer outputs need an explicit upstream text adapter.
6. **selftest.py** — fail-closed referee self-test (accepted / bluff-sorry / build-error / abstain-anchor / axiom-smuggle); writes a measured receipt; CI runs it.

## Probes

- probes/atlas/proving-ground.json — verbatim snapshot of the 30-formula atlas from the SZLHOLDINGS/formula-proving-ground HF dataset (classes SYMBOLIC / DIMENSIONAL / EMPIRICAL / DEFINITIONAL / CONJECTURE; Conjectures are ABSTAIN anchors, never bluff targets).
- probes/Probes.lean — v0 hand-formalized core-only fragments (Egyptian Horus-Eye sum, Kraft inequality, RS(10,6) Singleton arithmetic fragment), sorry-free and kernel-checked by lake build in CI.
- The repo is itself a core-only Lake package (NO Mathlib dependency): kernel checks run cold in seconds on any CPU/GPU node.

## Hard-math research / Putnam challenge catalog (evaluation-only)

The [source-bound hard-problem index](research/hard_problems/README.md) adds
**672 PutnamBench Lean-file references** (including the twelve Putnam 2025 A1–B6
identifiers), **1,861 Formal Conjectures source references**, and ten named
research challenges. Files are pinned to immutable upstream Git revisions;
no external theorem text, proof body, weights or untrusted Lean is executed.
**Putnam problems have published solutions; Formal Conjectures files are not
individually certified as unsolved.** This metadata catalog is not a model
accuracy result or a training corpus. The three-role Flagship55 Khipu teacher,
guide and skeptic remain proposed and untrained. The synthetic controls verify
that abstention is not a proof, a sorry-based claim is rejected and an unsupported
proof claim is UNVERIFIED. A separate [Putnam 2025 source preflight](research/hard_problems/PUTNAM2025_SOURCE_PREFLIGHT.md)
independently read back all 12 Lean formalization files and found 18 original
sorry placeholders and six solution abbreviations. That is source verification,
not model-quality evaluation or a mathematical proof. A [bounded local model
probe](research/hard_problems/LOCAL_MODEL_PROBE.md) adds immutable-source
prompts and an existing-Ollama-only inference path; the first live request hit
a metadata timeout. A second already-running on-host Ollama listener was
then independently observed; six Qwen3 4B Putnam responses were recorded
as **ABSTAIN** and [reconciled offline](research/hard_problems/LOCAL_SELECTIVE_REPLAY.md)
with explicit 0% answering coverage. Mathematical accuracy, selective risk,
Khipu/Goedel and Flagship55 benchmarks remain UNAVAILABLE. No autonomous
dataset admission, model restart or new GPU training run.

## Doctrine alignment

- Kernel-referee admission rule (flagship55 curriculum spec, merged): only lake-build-accepted proofs enter corpus v2.
- New axioms are disclosed, never smuggled (parity-guard verification plan).
- Honesty is a first-class signal: measured estate batteries (2026-11-13/14) showed abstention failures on unanswerable probes; the 0.5 abstain partial on conjecture-class is the honesty-shaping fix.
- **No launch in this repo.** Dockerfile.salad is a deployment *recipe* only; starting GPU training is an owner-cost decision (standing directive 2026-11-15: no payments, no asks).

## Local run

    lake build          # kernel-check the seed probes
    python selftest.py  # referee self-test, writes selftest-receipt.json

## Provenance

Estate-native (szl-holdings). Atlas provenance: SZLHOLDINGS/formula-proving-ground (HF dataset), content sha256 recorded in CI receipts. Built 2026-11-15 by the Vibe/dc lane under owner standing delegation.

## Pinned offline migration

Supply both exact file digests and the ledger head retained separately by the
trusted controller. Never calculate the trust anchor from an untrusted incoming
ledger and immediately treat it as authorization. The source files must be local
regular files containing bounded strict JSON/JSONL, without duplicate members,
non-finite numbers or blank ledger rows.

```sh
python stage_review.py --ledger ledger.jsonl --ledger-sha256 <exact-file-sha256> \
  --registry trusted-statements.json --registry-sha256 <exact-file-sha256> \
  --expected-chain-head <controller-retained-head-sha256> --output new-generation
```

Exit 0 means a review generation was staged, not that proof terms were replayed
or a model was trained. Exit 2 means blocked; failure output contains no input
bodies. Existing generations are never overwritten. Legacy receipts missing
required bindings must be replayed by an authorized worker, not patched into a
passing state. No legacy chain is rewritten by this command.

`LeanKernelReward` accepts concrete text/probe lists or tuples of equal nonzero
length, capped at 256 samples. It snapshots the trusted registry and validates
all input pairs before the first observer call or ledger write. Duplicate probe
IDs are allowed for repeated samples; mismatched lengths, unknown late IDs,
oversized text and nontext completions fail before any side effect. Operational
failure after a valid batch begins can leave completed receipts; reconcile the
existing single-writer ledger before retrying. No batch transaction or worker
isolation is claimed. The underlying chain requires external single-writer
coordination; this change does not create another writer or scheduler.


## Lutar A1–A5 numerical training curriculum (source-bound candidates)

The real canonical Lutar axiom predicates and geometric-mean definition, pinned
to `szl-holdings/lutar-lean@c2ca813fca00ecf58bcc5f505f2aa4237fbf2481`,
now have a **first-party synthetic chat/SFT curriculum** under
[`curriculum/`](./curriculum/README.md). It includes 160 deterministic training
examples and 80 disjoint, developer-authored diagnostic held-out examples,
with exact manifest file digests and numerical negative controls. Cases teach
A1–A5, refutation of unconditional Lambda uniqueness, nonuniform-weight
permutation limitations, and noncompensatory evidence holds. Python reproduces
every byte offline, and the existing CI validates the corpus and mathematical
fixtures without deploying or starting training.

This is a separate **numeric supervised curriculum**, not the Lean
`PROOF_ACCEPTED` referee/admission path. The datasets, optional exact-JSON
numeric reward, PR CI, and a structural Forge SFT validation **do not confer
training authority**, cryptographic signing, independent Lean checking, or
runtime/production readiness. The existing Forge launch contract still owns
reviewed rights, immutable Hub dataset/student pins, minimum corpus, sealed
holdout, cost approval, and any subsequent local training or HF publication.
