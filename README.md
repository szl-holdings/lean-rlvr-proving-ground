# lean-rlvr-proving-ground

**Lean-compile-as-reward RLVR environment for the SZL proving ground — the self-generating corpus flywheel.**

Estate artifact, fail-closed. Merge to protected mains is owner-gated. Nothing in this repo authorizes a launch.

## What this is

The recorded frontier pattern, built: **generate → Lean kernel referees → train only on accepted traces.** A model attempts proofs of the proving-ground atlas probes; the Lean kernel — not an LLM judge, not a rubric — decides the reward:

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
4. **admission.py** — corpus-v2 admission gate: **only lake-lane PROOF_ACCEPTED proofs enter corpus v2** (kernel-referee rule, szl-forge PR #746); emits per-probe JSON + a manifest with a total-content sha256.
5. **grpo_adapter.py** — verl/TRL GRPO-compatible reward function: kernel compile IS the reward.
6. **selftest.py** — fail-closed referee self-test (accepted / bluff-sorry / build-error / abstain-anchor / axiom-smuggle); writes a measured receipt; CI runs it.

## Probes

- probes/atlas/proving-ground.json — verbatim snapshot of the 30-formula atlas from the SZLHOLDINGS/formula-proving-ground HF dataset (classes SYMBOLIC / DIMENSIONAL / EMPIRICAL / DEFINITIONAL / CONJECTURE; Conjectures are ABSTAIN anchors, never bluff targets).
- probes/Probes.lean — v0 hand-formalized core-only fragments (Egyptian Horus-Eye sum, Kraft inequality, RS(10,6) Singleton arithmetic fragment), sorry-free and kernel-checked by lake build in CI.
- The repo is itself a core-only Lake package (NO Mathlib dependency): kernel checks run cold in seconds on any CPU/GPU node.

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
